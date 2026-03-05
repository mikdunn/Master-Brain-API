from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table

from .benchmark import load_benchmark_cases, run_benchmark
from .chunking import chunk_documents
from .config import load_module_registry
from .indexing import IndexStore
from .ingest import ingest_directory
from .master_brain import DEFAULT_MASTER_BRAIN_ROOT, scaffold_master_brain_structure, write_master_module_registry
from .orchestrator import answer_query
from .resilience import QuarantineStore

app = typer.Typer(help="Math Logic Agent CLI")
console = Console()


def _build_progress_callback(progress: Progress, task_id: int, detail_task_id: int):
    discovered_changed = 0
    processed_changed = 0

    def _callback(event: dict[str, Any]) -> None:
        nonlocal discovered_changed, processed_changed

        kind = str(event.get("event", ""))
        if kind == "module_started":
            module_id = str(event.get("module_id", "module"))
            progress.update(detail_task_id, description=f"[magenta]Routine:[/magenta] module {module_id} started")
            return

        if kind == "module_completed":
            module_id = str(event.get("module_id", "module"))
            progress.update(detail_task_id, description=f"[magenta]Routine:[/magenta] module {module_id} complete")
            return

        if kind == "root_discovered":
            module_id = str(event.get("module_id", "module"))
            root = str(event.get("root", ""))
            changed_here = int(event.get("changed_files", 0))
            discovered_changed += changed_here
            progress.update(detail_task_id, description=f"[magenta]Subroutine:[/magenta] discover root {root}")
            if discovered_changed == 0:
                progress.update(task_id, description=f"[cyan]Scanning {module_id}[/cyan] (no changed files yet)")
                return
            progress.update(
                task_id,
                total=discovered_changed,
                completed=processed_changed,
                description=f"[cyan]Scanning {module_id}[/cyan] ({processed_changed}/{discovered_changed} changed files)",
            )
            return

        if kind == "file_processed":
            processed_changed += 1
            module_id = str(event.get("module_id", "module"))
            status = str(event.get("status", "processed"))
            path = str(event.get("path", ""))
            total = max(discovered_changed, processed_changed)
            progress.update(detail_task_id, description=f"[magenta]Subroutine:[/magenta] {status} {path}")
            progress.update(
                task_id,
                total=total,
                completed=processed_changed,
                description=f"[cyan]{module_id}[/cyan] {status} ({processed_changed}/{total} changed files)",
            )
            return

        if kind == "checkpoint_written":
            writes = int(event.get("checkpoint_writes", 0))
            processed = int(event.get("processed_changed_files", processed_changed))
            progress.update(
                detail_task_id,
                description=f"[magenta]Subroutine:[/magenta] checkpoint write #{writes} at {processed} processed files",
            )
            return

        if kind == "complete":
            changed_total = int(event.get("changed_files", discovered_changed))
            total = max(changed_total, processed_changed, 1)
            completed = changed_total if changed_total > 0 else total
            progress.update(task_id, total=total, completed=completed, description="[green]Build complete[/green]")
            progress.update(detail_task_id, description="[green]All routines complete[/green]")

    return _callback


def _sleep_with_countdown(progress: Progress, detail_task_id: int, interval_seconds: int, cycle: int) -> None:
    if interval_seconds <= 0:
        return
    for remaining in range(interval_seconds, 0, -1):
        progress.update(
            detail_task_id,
            description=f"[blue]Cycle {cycle} complete; next cycle in {remaining}s[/blue]",
        )
        time.sleep(1)


@app.command("build-index")
def build_index(
    input_dir: str = typer.Option(..., help="Directory containing textbook files."),
    index_path: str = typer.Option("data/index.pkl", help="Path to save serialized index."),
    max_chars: int = typer.Option(1200, help="Chunk size in characters."),
    overlap: int = typer.Option(150, help="Chunk overlap in characters."),
    incremental: bool = typer.Option(True, help="Incrementally update existing index if present."),
    cloud_rerank: bool = typer.Option(True, help="Enable cloud embedding reranking when API key is set."),
    ocr_fallback: bool = typer.Option(True, help="Enable OCR fallback for low-quality PDF text extraction."),
    quarantine_path: str = typer.Option("data/quarantine.json", help="Path to quarantine file for problematic inputs."),
    checkpoint_path: str = typer.Option("data/build_checkpoint.json", help="Path to progress checkpoint file."),
    show_progress: bool = typer.Option(True, help="Show a live progress bar while building."),
    no_progress_timeout_seconds: int = typer.Option(90, help="No-progress timeout per file in seconds (0 disables). Slow files with progress are allowed."),
) -> None:
    total_files = 0
    changed_files = 0
    reused_files = 0
    if incremental:
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
                transient=False,
            ) as progress:
                task_id = progress.add_task("[cyan]Scanning input directory...[/cyan]", total=None)
                detail_task_id = progress.add_task("[magenta]Routine: initialization[/magenta]", total=None)
                progress_callback = _build_progress_callback(progress, task_id, detail_task_id)
                store, summary = IndexStore.build_from_directory(
                    input_dir=input_dir,
                    index_path=index_path,
                    max_chars=max_chars,
                    overlap=overlap,
                    incremental=True,
                    cloud_rerank=cloud_rerank,
                    ocr_fallback=ocr_fallback,
                    quarantine_path=quarantine_path,
                    checkpoint_path=checkpoint_path,
                    no_progress_timeout_seconds=no_progress_timeout_seconds,
                    progress_callback=progress_callback,
                )
        else:
            store, summary = IndexStore.build_from_directory(
                input_dir=input_dir,
                index_path=index_path,
                max_chars=max_chars,
                overlap=overlap,
                incremental=True,
                cloud_rerank=cloud_rerank,
                ocr_fallback=ocr_fallback,
                quarantine_path=quarantine_path,
                checkpoint_path=checkpoint_path,
                no_progress_timeout_seconds=no_progress_timeout_seconds,
            )
        docs_ingested = summary.documents_ingested
        chunks_created = summary.chunks_created
        changed_files = summary.changed_files
        reused_files = summary.reused_files
        total_files = summary.total_files
    else:
        docs = ingest_directory(input_dir, enable_ocr_fallback=ocr_fallback)
        chunks = chunk_documents(docs, max_chars=max_chars, overlap=overlap)
        store = IndexStore(chunks=chunks, file_manifest={}, cloud_rerank=cloud_rerank)
        docs_ingested = len(docs)
        chunks_created = len(chunks)

    store.save(index_path)

    table = Table(title="Index Build Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Input directory", str(Path(input_dir).resolve()))
    table.add_row("Documents ingested", str(docs_ingested))
    table.add_row("Chunks created", str(chunks_created))
    table.add_row("Incremental", str(incremental))
    table.add_row("Failed files", str(summary.failed_files if incremental else 0))
    table.add_row("Quarantined", str(summary.quarantined_files if incremental else 0))
    if incremental:
        table.add_row("Files total", str(total_files))
        table.add_row("Files changed", str(changed_files))
        table.add_row("Files reused", str(reused_files))
        table.add_row("Checkpoint writes", str(summary.checkpoint_writes))
    table.add_row("Index output", str(Path(index_path).resolve()))
    console.print(table)


@app.command("watch-index")
def watch_index(
    input_dir: str = typer.Option(..., help="Directory containing textbook files."),
    index_path: str = typer.Option("data/index.pkl", help="Path to save serialized index."),
    interval_seconds: int = typer.Option(60, help="Polling interval in seconds."),
    max_chars: int = typer.Option(1200, help="Chunk size in characters."),
    overlap: int = typer.Option(150, help="Chunk overlap in characters."),
    cloud_rerank: bool = typer.Option(True, help="Enable cloud embedding reranking when API key is set."),
    ocr_fallback: bool = typer.Option(True, help="Enable OCR fallback for low-quality PDF text extraction."),
    quarantine_path: str = typer.Option("data/quarantine.json", help="Path to quarantine file for problematic inputs."),
    checkpoint_path: str = typer.Option("data/build_checkpoint.json", help="Path to progress checkpoint file."),
    show_progress: bool = typer.Option(True, help="Show a live progress bar while building each watch cycle."),
    no_progress_timeout_seconds: int = typer.Option(90, help="No-progress timeout per file in seconds (0 disables). Slow files with progress are allowed."),
) -> None:
    console.print("Starting incremental watch mode. Press Ctrl+C to stop.")
    try:
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
                transient=False,
            ) as progress:
                task_id = progress.add_task("[cyan]Watch cycle 1: scanning...[/cyan]", total=None)
                detail_task_id = progress.add_task("[magenta]Routine: initialization[/magenta]", total=None)
                cycle = 0
                while True:
                    cycle += 1
                    progress.update(task_id, total=None, completed=0, description=f"[cyan]Watch cycle {cycle}: scanning...[/cyan]")
                    progress.update(detail_task_id, description="[magenta]Routine: incremental rebuild[/magenta]")
                    progress_callback = _build_progress_callback(progress, task_id, detail_task_id)

                    store, summary = IndexStore.build_from_directory(
                        input_dir=input_dir,
                        index_path=index_path,
                        max_chars=max_chars,
                        overlap=overlap,
                        incremental=True,
                        cloud_rerank=cloud_rerank,
                        ocr_fallback=ocr_fallback,
                        quarantine_path=quarantine_path,
                        checkpoint_path=checkpoint_path,
                        no_progress_timeout_seconds=no_progress_timeout_seconds,
                        progress_callback=progress_callback,
                    )
                    if summary.changed_files > 0 or not Path(index_path).exists():
                        store.save(index_path)
                        console.print(
                            f"[watch] indexed files={summary.total_files} changed={summary.changed_files} "
                            f"reused={summary.reused_files} chunks={summary.chunks_created}"
                        )
                    _sleep_with_countdown(progress, detail_task_id, interval_seconds, cycle)
        else:
            while True:
                store, summary = IndexStore.build_from_directory(
                    input_dir=input_dir,
                    index_path=index_path,
                    max_chars=max_chars,
                    overlap=overlap,
                    incremental=True,
                    cloud_rerank=cloud_rerank,
                    ocr_fallback=ocr_fallback,
                    quarantine_path=quarantine_path,
                    checkpoint_path=checkpoint_path,
                    no_progress_timeout_seconds=no_progress_timeout_seconds,
                )
                if summary.changed_files > 0 or not Path(index_path).exists():
                    store.save(index_path)
                    console.print(
                        f"[watch] indexed files={summary.total_files} changed={summary.changed_files} "
                        f"reused={summary.reused_files} chunks={summary.chunks_created}"
                    )
                time.sleep(interval_seconds)
    except KeyboardInterrupt:
        console.print("Stopped watch mode.")


@app.command("ask")
def ask(
    query: str = typer.Argument(..., help="Your math query."),
    index_path: str = typer.Option("data/index.pkl", help="Serialized index path."),
    k: int = typer.Option(6, help="Top-k context chunks."),
    cloud_rerank: bool = typer.Option(True, help="Enable cloud embedding reranking when API key is set."),
) -> None:
    index = IndexStore.load(index_path, cloud_rerank=cloud_rerank)
    response = answer_query(index=index, query=query, k=k)

    console.rule(f"Mode: {response.mode}")
    if response.selected_modules:
        console.print(f"Modules: {', '.join(response.selected_modules)}")
    console.print(f"Confidence: {response.confidence_label} ({response.confidence:.2f})")
    console.print(response.answer)


@app.command("copilot-context")
def copilot_context(
    query: str = typer.Argument(..., help="Prompt to prep context for Copilot."),
    index_path: str = typer.Option("data/index.pkl", help="Serialized index path."),
    k: int = typer.Option(5, help="Top-k context chunks."),
    cloud_rerank: bool = typer.Option(True, help="Enable cloud embedding reranking when API key is set."),
    template_only: bool = typer.Option(True, help="Emit a mode-specific Copilot-ready prompt template."),
) -> None:
    index = IndexStore.load(index_path, cloud_rerank=cloud_rerank)
    response = answer_query(index=index, query=query, k=k)

    if template_only:
        console.print(response.prompt_template)
        return

    context_prompt = (
        f"Mode: {response.mode}\n"
        "Use the following grounded math context when answering. "
        "Prefer correctness over brevity.\n\n"
        + "\n\n".join(response.context)
    )
    console.print(context_prompt)


@app.command("benchmark")
def benchmark(
    dataset_path: str = typer.Option("benchmarks/sample_benchmark.jsonl", help="Path to benchmark JSONL dataset."),
    index_path: str = typer.Option("data/index.pkl", help="Serialized index path."),
    k: int = typer.Option(6, help="Top-k context chunks for retrieval benchmark."),
    cloud_rerank: bool = typer.Option(True, help="Enable cloud embedding reranking when API key is set."),
) -> None:
    index = IndexStore.load(index_path, cloud_rerank=cloud_rerank)
    cases = load_benchmark_cases(dataset_path)
    result = run_benchmark(index=index, cases=cases, k=k)

    table = Table(title="Benchmark Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Dataset", str(Path(dataset_path).resolve()))
    table.add_row("Total cases", str(result.total))
    table.add_row("Mode accuracy", f"{result.mode_accuracy:.2%}")
    table.add_row("Retrieval hit rate", f"{result.retrieval_hit_rate:.2%}")
    console.print(table)


@app.command("list-modules")
def list_modules(
    module_config: str = typer.Option("config/modules.toml", help="Path to module registry TOML."),
) -> None:
    registry = load_module_registry(module_config)
    table = Table(title="Module Registry")
    table.add_column("Module ID")
    table.add_column("Name")
    table.add_column("Enabled")
    table.add_column("Stage")
    table.add_column("Priority")
    table.add_column("Paths")

    for m in registry.modules:
        table.add_row(
            m.module_id,
            m.display_name,
            str(m.enabled),
            m.stage,
            str(m.priority),
            "; ".join(str(p) for p in m.paths),
        )
    console.print(table)


@app.command("build-brain")
def build_brain(
    module_config: str = typer.Option("config/modules.toml", help="Path to module registry TOML."),
    index_path: str = typer.Option("data/brain_index.pkl", help="Path to save serialized multi-module index."),
    max_chars: int = typer.Option(1200, help="Chunk size in characters."),
    overlap: int = typer.Option(150, help="Chunk overlap in characters."),
    incremental: bool = typer.Option(True, help="Incrementally update existing index if present."),
    cloud_rerank: bool = typer.Option(True, help="Enable cloud embedding reranking when API key is set."),
    ocr_fallback: bool = typer.Option(True, help="Enable OCR fallback for low-quality PDF text extraction."),
    quarantine_path: str = typer.Option("data/quarantine.json", help="Path to quarantine file for problematic inputs."),
    checkpoint_path: str = typer.Option("data/build_checkpoint.json", help="Path to progress checkpoint file."),
    checkpoint_every: int = typer.Option(200, help="Write checkpoint after this many changed files."),
    respect_quarantine: bool = typer.Option(True, help="Skip known-problem files already quarantined."),
    show_progress: bool = typer.Option(True, help="Show a live progress bar while building."),
    no_progress_timeout_seconds: int = typer.Option(90, help="No-progress timeout per file in seconds (0 disables). Slow files with progress are allowed."),
) -> None:
    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=False,
        ) as progress:
            task_id = progress.add_task("[cyan]Scanning modules...[/cyan]", total=None)
            detail_task_id = progress.add_task("[magenta]Routine: initialization[/magenta]", total=None)
            progress_callback = _build_progress_callback(progress, task_id, detail_task_id)
            store, summary = IndexStore.build_from_modules(
                module_config_path=module_config,
                index_path=index_path,
                max_chars=max_chars,
                overlap=overlap,
                incremental=incremental,
                cloud_rerank=cloud_rerank,
                ocr_fallback=ocr_fallback,
                quarantine_path=quarantine_path,
                checkpoint_path=checkpoint_path,
                checkpoint_every=checkpoint_every,
                respect_quarantine=respect_quarantine,
                no_progress_timeout_seconds=no_progress_timeout_seconds,
                progress_callback=progress_callback,
            )
    else:
        store, summary = IndexStore.build_from_modules(
            module_config_path=module_config,
            index_path=index_path,
            max_chars=max_chars,
            overlap=overlap,
            incremental=incremental,
            cloud_rerank=cloud_rerank,
            ocr_fallback=ocr_fallback,
            quarantine_path=quarantine_path,
            checkpoint_path=checkpoint_path,
            checkpoint_every=checkpoint_every,
            respect_quarantine=respect_quarantine,
                no_progress_timeout_seconds=no_progress_timeout_seconds,
        )
    store.save(index_path)

    table = Table(title="Brain Build Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Modules built", str(summary.modules_built))
    table.add_row("Files total", str(summary.total_files))
    table.add_row("Files changed", str(summary.changed_files))
    table.add_row("Files reused", str(summary.reused_files))
    table.add_row("Failed files", str(summary.failed_files))
    table.add_row("Quarantined", str(summary.quarantined_files))
    table.add_row("Documents ingested", str(summary.documents_ingested))
    table.add_row("Chunks created", str(summary.chunks_created))
    table.add_row("Checkpoint writes", str(summary.checkpoint_writes))
    table.add_row("Index output", str(Path(index_path).resolve()))
    console.print(table)


@app.command("init-master-structure")
def init_master_structure(
    master_root: str = typer.Option(str(DEFAULT_MASTER_BRAIN_ROOT), help="Root folder for the Master Brain corpus."),
    module_config: str = typer.Option("config/master_brain.toml", help="Path to write Master Brain module config."),
    overwrite_config: bool = typer.Option(True, help="Overwrite module config if it already exists."),
) -> None:
    scaffold = scaffold_master_brain_structure(master_root)
    config_path = write_master_module_registry(module_config, root=master_root, overwrite=overwrite_config)

    table = Table(title="Master Brain Structure Initialization")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Root", str(Path(master_root).resolve()))
    table.add_row("Directories in template", str(scaffold.total_directories))
    table.add_row("Directories created", str(scaffold.created_directories))
    table.add_row("Directories already present", str(scaffold.existing_directories))
    table.add_row("Module config", str(config_path.resolve()))
    console.print(table)


@app.command("build-master-brain")
def build_master_brain(
    master_root: str = typer.Option(str(DEFAULT_MASTER_BRAIN_ROOT), help="Root folder for the Master Brain corpus."),
    module_config: str = typer.Option("config/master_brain.toml", help="Path to module registry TOML."),
    index_path: str = typer.Option("data/master_brain_index.pkl", help="Path to save serialized Master Brain index."),
    max_chars: int = typer.Option(1200, help="Chunk size in characters."),
    overlap: int = typer.Option(150, help="Chunk overlap in characters."),
    incremental: bool = typer.Option(True, help="Incrementally update existing index if present."),
    cloud_rerank: bool = typer.Option(True, help="Enable cloud embedding reranking when API key is set."),
    ocr_fallback: bool = typer.Option(True, help="Enable OCR fallback for low-quality PDF text extraction."),
    quarantine_path: str = typer.Option("data/master_brain_quarantine.json", help="Path to quarantine file for problematic inputs."),
    checkpoint_path: str = typer.Option("data/master_brain_checkpoint.json", help="Path to progress checkpoint file."),
    checkpoint_every: int = typer.Option(200, help="Write checkpoint after this many changed files."),
    respect_quarantine: bool = typer.Option(True, help="Skip known-problem files already quarantined."),
    refresh_config: bool = typer.Option(True, help="Regenerate config from master_root before build."),
    show_progress: bool = typer.Option(
        False,
        help="Show a live progress bar while building.",
    ),
    no_progress_timeout_seconds: int = typer.Option(90, help="No-progress timeout per file in seconds (0 disables). Slow files with progress are allowed."),
) -> None:
    if refresh_config:
        write_master_module_registry(module_config, root=master_root, overwrite=True)

    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=False,
        ) as progress:
            task_id = progress.add_task("[cyan]Scanning modules...[/cyan]", total=None)
            detail_task_id = progress.add_task("[magenta]Routine: initialization[/magenta]", total=None)
            progress_callback = _build_progress_callback(progress, task_id, detail_task_id)
            store, summary = IndexStore.build_from_modules(
                module_config_path=module_config,
                index_path=index_path,
                max_chars=max_chars,
                overlap=overlap,
                incremental=incremental,
                cloud_rerank=cloud_rerank,
                ocr_fallback=ocr_fallback,
                quarantine_path=quarantine_path,
                checkpoint_path=checkpoint_path,
                checkpoint_every=checkpoint_every,
                respect_quarantine=respect_quarantine,
                no_progress_timeout_seconds=no_progress_timeout_seconds,
                progress_callback=progress_callback,
            )
    else:
        store, summary = IndexStore.build_from_modules(
            module_config_path=module_config,
            index_path=index_path,
            max_chars=max_chars,
            overlap=overlap,
            incremental=incremental,
            cloud_rerank=cloud_rerank,
            ocr_fallback=ocr_fallback,
            quarantine_path=quarantine_path,
            checkpoint_path=checkpoint_path,
            checkpoint_every=checkpoint_every,
            respect_quarantine=respect_quarantine,
            no_progress_timeout_seconds=no_progress_timeout_seconds,
        )
    store.save(index_path)

    table = Table(title="Master Brain Build Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Root", str(Path(master_root).resolve()))
    table.add_row("Modules built", str(summary.modules_built))
    table.add_row("Files total", str(summary.total_files))
    table.add_row("Files changed", str(summary.changed_files))
    table.add_row("Files reused", str(summary.reused_files))
    table.add_row("Failed files", str(summary.failed_files))
    table.add_row("Quarantined", str(summary.quarantined_files))
    table.add_row("Documents ingested", str(summary.documents_ingested))
    table.add_row("Chunks created", str(summary.chunks_created))
    table.add_row("Checkpoint writes", str(summary.checkpoint_writes))
    table.add_row("Index output", str(Path(index_path).resolve()))
    table.add_row("Quarantine file", str(Path(quarantine_path).resolve()))
    table.add_row("Checkpoint file", str(Path(checkpoint_path).resolve()))
    console.print(table)


@app.command("quarantine-list")
def quarantine_list(
    quarantine_path: str = typer.Option("data/quarantine.json", help="Path to quarantine file."),
) -> None:
    q = QuarantineStore(quarantine_path)
    table = Table(title="Quarantine Records")
    table.add_column("File Key")
    table.add_column("Module")
    table.add_column("Failures")
    table.add_column("Reason")

    if not q.records:
        console.print("No quarantined files found.")
        return

    for rec in q.records.values():
        table.add_row(rec.file_key, rec.module_id or "n/a", str(rec.fail_count), rec.reason[:120])
    console.print(table)


@app.command("quarantine-clear")
def quarantine_clear(
    quarantine_path: str = typer.Option("data/quarantine.json", help="Path to quarantine file."),
    module_id: str | None = typer.Option(None, help="Optional module ID to clear only one module."),
) -> None:
    q = QuarantineStore(quarantine_path)
    removed = q.clear(module_id=module_id)
    q.save()
    scope = module_id if module_id else "all modules"
    console.print(f"Cleared {removed} quarantine records for {scope}.")


if __name__ == "__main__":
    app()

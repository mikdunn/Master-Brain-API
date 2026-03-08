from __future__ import annotations

import pickle
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .bq_telemetry import BuildRunEvent, ChunkMetadataEvent, FileInventoryEvent, get_telemetry_service
from .chunking import chunk_documents
from .config import ModuleRegistry, Settings, load_module_registry
from .embeddings import OpenAIEmbedder
from .inheritance import load_inheritance_config
from .ingest import (
    discover_documents,
    file_signature,
    ingest_path_safe_with_timeout,
)
from .models import DocumentChunk
from .resilience import QuarantineStore, write_checkpoint
from .retrieval import HybridRetriever


@dataclass(slots=True)
class BuildSummary:
    total_files: int
    changed_files: int
    reused_files: int
    documents_ingested: int
    chunks_created: int
    modules_built: int = 1
    failed_files: int = 0
    quarantined_files: int = 0
    checkpoint_writes: int = 0


class IndexStore:
    def __init__(
        self,
        chunks: list[DocumentChunk],
        file_manifest: dict[str, str] | None = None,
        cloud_rerank: bool = True,
        module_aliases: dict[str, list[str]] | None = None,
        module_inheritance: dict[str, list[str]] | None = None,
    ) -> None:
        self.chunks = chunks
        self.file_manifest = file_manifest or {}
        self.module_aliases = module_aliases or {}
        self.module_inheritance = module_inheritance or {}

        settings = Settings.from_env()
        embedder = None
        if (
            cloud_rerank
            and settings.cloud_rerank_enabled
            and settings.openai_api_key
        ):
            embedder = OpenAIEmbedder(settings=settings)
        self.retriever = HybridRetriever(chunks, embedder=embedder)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("wb") as f:
            pickle.dump(
                {
                    "chunks": self.chunks,
                    "file_manifest": self.file_manifest,
                    "module_aliases": self.module_aliases,
                    "module_inheritance": self.module_inheritance,
                },
                f,
            )

    @classmethod
    def load(cls, path: str | Path, cloud_rerank: bool = True) -> "IndexStore":
        p = Path(path)
        with p.open("rb") as f:
            data = pickle.load(f)
        chunks = data["chunks"]
        file_manifest = data.get("file_manifest", {})
        module_aliases = data.get("module_aliases", {})
        module_inheritance = data.get("module_inheritance", {})
        return cls(
            chunks=chunks,
            file_manifest=file_manifest,
            cloud_rerank=cloud_rerank,
            module_aliases=module_aliases,
            module_inheritance=module_inheritance,
        )

    @staticmethod
    def _manifest_key(module_id: str, path: Path) -> str:
        return f"{module_id}::{path}"

    @staticmethod
    def _save_payload(
        path: str | Path,
        chunks: list[DocumentChunk],
        file_manifest: dict[str, str],
        module_aliases: dict[str, list[str]] | None = None,
        module_inheritance: dict[str, list[str]] | None = None,
    ) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("wb") as f:
            pickle.dump(
                {
                    "chunks": chunks,
                    "file_manifest": file_manifest,
                    "module_aliases": module_aliases or {},
                    "module_inheritance": module_inheritance or {},
                },
                f,
            )

    @classmethod
    def _ingest_changed_paths(
        cls,
        *,
        build_id: str,
        module_id: str,
        changed_paths: list[Path],
        enable_ocr_fallback: bool,
        max_chars: int,
        overlap: int,
        quarantine: QuarantineStore,
        respect_quarantine: bool,
        no_progress_timeout_seconds: int,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[list[DocumentChunk], int, int, int]:
        docs_total = 0
        failed = 0
        quarantined = 0
        chunks: list[DocumentChunk] = []
        settings = Settings.from_env()
        telemetry = get_telemetry_service(settings)
        for p in changed_paths:
            key = cls._manifest_key(module_id, p)
            if respect_quarantine and quarantine.is_quarantined(key):
                quarantined += 1
                telemetry.emit_file_inventory(
                    FileInventoryEvent(
                        build_id=build_id,
                        module_id=module_id,
                        file_path=str(p),
                        action="quarantined",
                        file_signature=file_signature(p),
                    )
                )
                if progress_callback is not None:
                    progress_callback(
                        {
                            "event": "file_processed",
                            "module_id": module_id,
                            "path": str(p),
                            "status": "quarantined",
                        }
                    )
                continue
            docs, err = ingest_path_safe_with_timeout(
                p,
                enable_ocr_fallback=enable_ocr_fallback,
                module_id=module_id,
                timeout_seconds=no_progress_timeout_seconds,
            )
            if err is not None:
                failed += 1
                quarantine.record_failure(
                    file_key=key,
                    path=str(p),
                    module_id=module_id,
                    reason=err,
                )
                telemetry.emit_file_inventory(
                    FileInventoryEvent(
                        build_id=build_id,
                        module_id=module_id,
                        file_path=str(p),
                        action="failed",
                        file_signature=file_signature(p),
                        error=err,
                    )
                )
                if progress_callback is not None:
                    progress_callback(
                        {
                            "event": "file_processed",
                            "module_id": module_id,
                            "path": str(p),
                            "status": "failed",
                        }
                    )
                continue
            docs_total += len(docs)
            created_chunks = 0
            if docs:
                file_chunks = chunk_documents(
                    docs,
                    max_chars=max_chars,
                    overlap=overlap,
                )
                created_chunks = len(file_chunks)
                chunks.extend(file_chunks)
                telemetry.emit_chunk_metadata(
                    [
                        ChunkMetadataEvent(build_id=build_id, chunk=c)
                        for c in file_chunks
                    ]
                )
            telemetry.emit_file_inventory(
                FileInventoryEvent(
                    build_id=build_id,
                    module_id=module_id,
                    file_path=str(p),
                    action="processed",
                    file_signature=file_signature(p),
                    chunk_count=created_chunks,
                )
            )
            if progress_callback is not None:
                progress_callback(
                    {
                        "event": "file_processed",
                        "module_id": module_id,
                        "path": str(p),
                        "status": "processed",
                    }
                )
        return chunks, docs_total, failed, quarantined

    @classmethod
    def build_from_directory(
        cls,
        input_dir: str | Path,
        index_path: str | Path,
        max_chars: int = 1200,
        overlap: int = 150,
        incremental: bool = True,
        cloud_rerank: bool = True,
        ocr_fallback: bool = True,
        quarantine_path: str | Path = "data/quarantine.json",
        checkpoint_path: str | Path | None = "data/build_checkpoint.json",
        respect_quarantine: bool = True,
        no_progress_timeout_seconds: int = 0,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple["IndexStore", BuildSummary]:
        build_id = str(uuid4())
        input_root = Path(input_dir)
        existing: IndexStore | None = None
        index_file = Path(index_path)
        if incremental and index_file.exists():
            existing = cls.load(index_file, cloud_rerank=cloud_rerank)

        old_manifest = existing.file_manifest if existing else {}
        old_by_source: dict[str, list[DocumentChunk]] = {}
        if existing:
            for c in existing.chunks:
                old_by_source.setdefault(c.source, []).append(c)
        quarantine = QuarantineStore(quarantine_path)

        files = discover_documents(input_root)
        module_id = Path(input_root).name.lower().replace(" ", "_")
        current_manifest = {
            cls._manifest_key(module_id, p): file_signature(p)
            for p in files
        }

        changed_paths = [
            p
            for p in files
            if old_manifest.get(cls._manifest_key(module_id, p))
            != current_manifest[cls._manifest_key(module_id, p)]
        ]
        reused_paths = [
            p
            for p in files
            if old_manifest.get(cls._manifest_key(module_id, p))
            == current_manifest[cls._manifest_key(module_id, p)]
            and str(p) in old_by_source
        ]
        if progress_callback is not None:
            progress_callback(
                {
                    "event": "root_discovered",
                    "module_id": module_id,
                    "root": str(input_root),
                    "total_files": len(files),
                    "changed_files": len(changed_paths),
                    "reused_files": len(reused_paths),
                }
            )

        (
            new_chunks,
            docs_ingested,
            failed_files,
            quarantined_files,
        ) = cls._ingest_changed_paths(
            build_id=build_id,
            module_id=module_id,
            changed_paths=changed_paths,
            enable_ocr_fallback=ocr_fallback,
            max_chars=max_chars,
            overlap=overlap,
            quarantine=quarantine,
            respect_quarantine=respect_quarantine,
            no_progress_timeout_seconds=no_progress_timeout_seconds,
            progress_callback=progress_callback,
        )

        kept_chunks: list[DocumentChunk] = []
        for p in reused_paths:
            kept_chunks.extend(old_by_source[str(p)])

        telemetry = get_telemetry_service(Settings.from_env())
        for p in reused_paths:
            telemetry.emit_file_inventory(
                FileInventoryEvent(
                    build_id=build_id,
                    module_id=module_id,
                    file_path=str(p),
                    action="unchanged",
                    file_signature=current_manifest.get(cls._manifest_key(module_id, p)),
                    chunk_count=len(old_by_source.get(str(p), [])),
                )
            )

        chunks = kept_chunks + new_chunks
        store = cls(
            chunks=chunks,
            file_manifest=current_manifest,
            cloud_rerank=cloud_rerank,
        )
        quarantine.save()
        checkpoint_writes = 0
        if checkpoint_path is not None:
            write_checkpoint(
                checkpoint_path,
                {
                    "kind": "single-module",
                    "module_id": module_id,
                    "status": "complete",
                    "total_files": len(files),
                    "changed_files": len(changed_paths),
                    "reused_files": len(reused_paths),
                    "failed_files": failed_files,
                    "quarantined_files": quarantined_files,
                },
            )
            checkpoint_writes = 1
            if progress_callback is not None:
                progress_callback(
                    {
                        "event": "checkpoint_written",
                        "processed_changed_files": len(changed_paths),
                        "checkpoint_writes": checkpoint_writes,
                    }
                )
        summary = BuildSummary(
            total_files=len(files),
            changed_files=len(changed_paths),
            reused_files=len(reused_paths),
            documents_ingested=docs_ingested,
            chunks_created=len(chunks),
            modules_built=1,
            failed_files=failed_files,
            quarantined_files=quarantined_files,
            checkpoint_writes=checkpoint_writes,
        )
        if progress_callback is not None:
            progress_callback(
                {
                    "event": "complete",
                    "changed_files": len(changed_paths),
                    "modules_built": 1,
                    "failed_files": failed_files,
                    "quarantined_files": quarantined_files,
                }
            )
        telemetry.emit_build_run(
            BuildRunEvent(
                build_id=build_id,
                build_type="single-module",
                status="complete",
                total_files=summary.total_files,
                changed_files=summary.changed_files,
                reused_files=summary.reused_files,
                documents_ingested=summary.documents_ingested,
                chunks_created=summary.chunks_created,
                modules_built=summary.modules_built,
                failed_files=summary.failed_files,
                quarantined_files=summary.quarantined_files,
                checkpoint_writes=summary.checkpoint_writes,
                index_path=str(index_path),
            )
        )
        return store, summary

    @classmethod
    def build_from_modules(
        cls,
        module_config_path: str | Path,
        index_path: str | Path,
        inheritance_config_path: str | Path = "config/inheritance.toml",
        max_chars: int = 1200,
        overlap: int = 150,
        incremental: bool = True,
        cloud_rerank: bool = True,
        ocr_fallback: bool = True,
        quarantine_path: str | Path = "data/quarantine.json",
        checkpoint_path: str | Path | None = "data/build_checkpoint.json",
        checkpoint_every: int = 200,
        respect_quarantine: bool = True,
        no_progress_timeout_seconds: int = 0,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple["IndexStore", BuildSummary]:
        build_id = str(uuid4())
        registry: ModuleRegistry = load_module_registry(module_config_path)

        # Persist these into the index so query-time routing can use
        # aliases for Master Brain module IDs (e.g., math_brain, cs_brain).
        module_aliases: dict[str, list[str]] = {
            m.module_id: list(m.aliases)
            for m in registry.enabled_modules
            if m.aliases
        }

        inheritance_cfg = load_inheritance_config(inheritance_config_path)
        module_inheritance: dict[str, list[str]] = {
            k: list(v)
            for k, v in inheritance_cfg.prereqs.items()
            if v
        }
        existing: IndexStore | None = None
        index_file = Path(index_path)
        if incremental and index_file.exists():
            existing = cls.load(index_file, cloud_rerank=cloud_rerank)

        old_manifest = existing.file_manifest if existing else {}
        old_by_source: dict[str, list[DocumentChunk]] = {}
        if existing:
            for c in existing.chunks:
                old_by_source.setdefault(c.source, []).append(c)

        current_manifest: dict[str, str] = {}
        all_new_chunks: list[DocumentChunk] = []
        all_kept_chunks: list[DocumentChunk] = []
        total_files = 0
        changed_files = 0
        reused_files = 0
        documents_ingested = 0
        modules_built = 0
        failed_files = 0
        quarantined_files = 0
        checkpoint_writes = 0
        processed_changed = 0
        quarantine = QuarantineStore(quarantine_path)

        for module in registry.enabled_modules:
            modules_built += 1
            if progress_callback is not None:
                progress_callback(
                    {
                        "event": "module_started",
                        "module_id": module.module_id,
                    }
                )
            for root in module.paths:
                if not root.exists():
                    continue
                files = discover_documents(root)
                total_files += len(files)

                for p in files:
                    key = cls._manifest_key(module.module_id, p)
                    current_manifest[key] = file_signature(p)

                changed_paths = [
                    p
                    for p in files
                    if old_manifest.get(cls._manifest_key(module.module_id, p))
                    != current_manifest[cls._manifest_key(module.module_id, p)]
                ]
                reused_paths = [
                    p
                    for p in files
                    if old_manifest.get(cls._manifest_key(module.module_id, p))
                    == current_manifest[cls._manifest_key(module.module_id, p)]
                    and str(p) in old_by_source
                ]

                changed_files += len(changed_paths)
                reused_files += len(reused_paths)
                if progress_callback is not None:
                    progress_callback(
                        {
                            "event": "root_discovered",
                            "module_id": module.module_id,
                            "root": str(root),
                            "total_files": len(files),
                            "changed_files": len(changed_paths),
                            "reused_files": len(reused_paths),
                        }
                    )

                (
                    new_chunks,
                    docs_count,
                    failed_count,
                    quarantined_count,
                ) = cls._ingest_changed_paths(
                    build_id=build_id,
                    module_id=module.module_id,
                    changed_paths=changed_paths,
                    enable_ocr_fallback=ocr_fallback,
                    max_chars=max_chars,
                    overlap=overlap,
                    quarantine=quarantine,
                    respect_quarantine=respect_quarantine,
                    no_progress_timeout_seconds=no_progress_timeout_seconds,
                    progress_callback=progress_callback,
                )
                documents_ingested += docs_count
                failed_files += failed_count
                quarantined_files += quarantined_count
                all_new_chunks.extend(new_chunks)
                processed_changed += len(changed_paths)

                for p in reused_paths:
                    all_kept_chunks.extend(old_by_source[str(p)])

                telemetry = get_telemetry_service(Settings.from_env())
                for p in reused_paths:
                    telemetry.emit_file_inventory(
                        FileInventoryEvent(
                            build_id=build_id,
                            module_id=module.module_id,
                            file_path=str(p),
                            action="unchanged",
                            file_signature=current_manifest.get(cls._manifest_key(module.module_id, p)),
                            chunk_count=len(old_by_source.get(str(p), [])),
                        )
                    )

                if (
                    checkpoint_path is not None
                    and processed_changed > 0
                    and processed_changed % max(checkpoint_every, 1) == 0
                ):
                    partial_chunks = all_kept_chunks + all_new_chunks
                    cls._save_payload(
                        index_path,
                        partial_chunks,
                        current_manifest,
                        module_aliases=module_aliases,
                        module_inheritance=module_inheritance,
                    )
                    write_checkpoint(
                        checkpoint_path,
                        {
                            "kind": "multi-module",
                            "status": "running",
                            "processed_changed_files": processed_changed,
                            "modules_built": modules_built,
                            "failed_files": failed_files,
                            "quarantined_files": quarantined_files,
                            "chunks_created": len(partial_chunks),
                        },
                    )
                    checkpoint_writes += 1
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "event": "checkpoint_written",
                                "processed_changed_files": processed_changed,
                                "checkpoint_writes": checkpoint_writes,
                            }
                        )
            if progress_callback is not None:
                progress_callback(
                    {
                        "event": "module_completed",
                        "module_id": module.module_id,
                    }
                )

        chunks = all_kept_chunks + all_new_chunks
        store = cls(
            chunks=chunks,
            file_manifest=current_manifest,
            cloud_rerank=cloud_rerank,
            module_aliases=module_aliases,
            module_inheritance=module_inheritance,
        )
        quarantine.save()
        if checkpoint_path is not None:
            write_checkpoint(
                checkpoint_path,
                {
                    "kind": "multi-module",
                    "status": "complete",
                    "processed_changed_files": processed_changed,
                    "modules_built": modules_built,
                    "failed_files": failed_files,
                    "quarantined_files": quarantined_files,
                    "chunks_created": len(chunks),
                },
            )
            checkpoint_writes += 1
            if progress_callback is not None:
                progress_callback(
                    {
                        "event": "checkpoint_written",
                        "processed_changed_files": processed_changed,
                        "checkpoint_writes": checkpoint_writes,
                    }
                )
        summary = BuildSummary(
            total_files=total_files,
            changed_files=changed_files,
            reused_files=reused_files,
            documents_ingested=documents_ingested,
            chunks_created=len(chunks),
            modules_built=modules_built,
            failed_files=failed_files,
            quarantined_files=quarantined_files,
            checkpoint_writes=checkpoint_writes,
        )
        if progress_callback is not None:
            progress_callback(
                {
                    "event": "complete",
                    "changed_files": changed_files,
                    "modules_built": modules_built,
                    "failed_files": failed_files,
                    "quarantined_files": quarantined_files,
                }
            )
        telemetry = get_telemetry_service(Settings.from_env())
        telemetry.emit_build_run(
            BuildRunEvent(
                build_id=build_id,
                build_type="multi-module",
                status="complete",
                total_files=summary.total_files,
                changed_files=summary.changed_files,
                reused_files=summary.reused_files,
                documents_ingested=summary.documents_ingested,
                chunks_created=summary.chunks_created,
                modules_built=summary.modules_built,
                failed_files=summary.failed_files,
                quarantined_files=summary.quarantined_files,
                checkpoint_writes=summary.checkpoint_writes,
                index_path=str(index_path),
            )
        )
        return store, summary

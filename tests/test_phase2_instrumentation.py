from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from math_logic_agent.chunking import chunk_documents
from math_logic_agent.indexing import IndexStore
from math_logic_agent.models import RawDocument
import math_logic_agent.indexing as indexing
import math_logic_agent.orchestrator as orchestrator


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_retrieve_hits_emits_retrieval_events(monkeypatch) -> None:
    docs = [
        RawDocument(
            text="Definition: singular value decomposition.",
            source="lin_alg.txt",
            module_id="math_core",
        ),
    ]
    index = IndexStore(chunk_documents(docs), cloud_rerank=False)

    captured: list[list[object]] = []
    fake = SimpleNamespace(emit_retrieval_hits=lambda events: captured.append(events) or len(events))

    monkeypatch.setattr(orchestrator, "get_telemetry_service", lambda _settings: fake)

    out = orchestrator.retrieve_hits(index=index, query="What is SVD?", k=3)

    assert out.hits
    assert captured
    assert len(captured[0]) == len(out.hits)


def test_build_from_directory_emits_build_and_file_events(monkeypatch, tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _write(docs_dir / "a.txt", "alpha beta gamma")
    _write(docs_dir / "b.txt", "delta epsilon")

    emitted_files: list[object] = []
    emitted_builds: list[object] = []
    emitted_chunks: list[list[object]] = []
    fake = SimpleNamespace(
        emit_file_inventory=lambda event: emitted_files.append(event) or True,
        emit_build_run=lambda event: emitted_builds.append(event) or True,
        emit_chunk_metadata=lambda events: emitted_chunks.append(events) or len(events),
    )

    monkeypatch.setattr(indexing, "get_telemetry_service", lambda _settings: fake)

    index_path = tmp_path / "idx.pkl"
    store, summary = IndexStore.build_from_directory(
        input_dir=docs_dir,
        index_path=index_path,
        incremental=True,
        cloud_rerank=False,
        checkpoint_path=None,
    )

    assert store is not None
    assert summary.total_files == 2
    assert emitted_builds
    assert emitted_files
    assert emitted_chunks

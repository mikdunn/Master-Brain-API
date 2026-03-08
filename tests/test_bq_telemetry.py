from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from math_logic_agent.bq_telemetry import (
    BigQueryTelemetryService,
    BuildRunEvent,
    ChunkMetadataEvent,
    FileInventoryEvent,
    RetrievalHitEvent,
    TelemetryEvent,
    reset_telemetry_service_for_tests,
)
from math_logic_agent.config import Settings
from math_logic_agent.models import DocumentChunk, RetrievedChunk


def _settings(**overrides) -> Settings:
    base = Settings(
        openai_api_key=None,
        perplexity_api_key=None,
        openai_embed_model="text-embedding-3-small",
        cloud_rerank_enabled=False,
        bridge_api_key=None,
        bridge_host="127.0.0.1",
        bridge_port=8787,
        bridge_default_index_path="data/master_brain_index.pkl",
    )
    return replace(base, **overrides)


def test_emit_returns_false_when_disabled() -> None:
    svc = BigQueryTelemetryService(_settings(bq_telemetry_enabled=False))
    ok = svc.emit_query_event(
        TelemetryEvent(
            endpoint="/v1/query",
            question="hello",
            mode="explanation",
            confidence=0.7,
            selected_modules=["math_core"],
            k=6,
            latency_ms=12,
            status_code=200,
            error=None,
        )
    )
    assert ok is False


def test_flush_batch_uses_client_when_available(monkeypatch) -> None:
    inserted: list[tuple[str, list[dict[str, object]]]] = []

    fake_client = SimpleNamespace(
        insert_rows_json=lambda table, rows, timeout=None: inserted.append((table, rows))
    )

    svc = BigQueryTelemetryService(
        _settings(
            bq_telemetry_enabled=True,
            bq_project_id="p1",
            bq_dataset_id="d1",
            bq_query_table="t1",
            bq_insert_timeout_seconds=1,
        )
    )
    monkeypatch.setattr(svc, "_get_client", lambda: fake_client)

    rows = [
        (
            "t1",
            {"event_id": "e1", "timestamp": "2026-01-01T00:00:00+00:00"},
        )
    ]
    svc._flush_batch(rows)

    assert inserted
    table, payload = inserted[0]
    assert table == "p1.d1.t1"
    assert payload == [rows[0][1]]


def test_emit_returns_false_when_queue_is_full(monkeypatch) -> None:
    svc = BigQueryTelemetryService(
        _settings(
            bq_telemetry_enabled=True,
            bq_project_id="p1",
            bq_dataset_id="d1",
            bq_query_table="t1",
        )
    )

    import queue

    tiny = queue.Queue(maxsize=1)
    tiny.put(("t1", {"x": 1}))
    monkeypatch.setattr(svc, "_queue", tiny)

    ok = svc.emit_query_event(
        TelemetryEvent(
            endpoint="/v1/query",
            question="hello",
            mode="explanation",
            confidence=0.7,
            selected_modules=["math_core"],
            k=6,
            latency_ms=12,
            status_code=200,
            error=None,
        )
    )

    assert ok is False


def test_emit_retrieval_hits_enqueues_rows() -> None:
    svc = BigQueryTelemetryService(
        _settings(
            bq_telemetry_enabled=True,
            bq_project_id="p1",
            bq_dataset_id="d1",
            bq_retrieval_hits_table="retrieval_hits",
        )
    )
    hit = RetrievedChunk(
        chunk=DocumentChunk(
            chunk_id="c1",
            text="x",
            source="s.txt",
            module_id="math_core",
            page=1,
        ),
        score=0.9,
        channel="hybrid",
    )
    accepted = svc.emit_retrieval_hits(
        [
            RetrievalHitEvent(
                query="what is svd",
                endpoint="retrieval",
                mode="explanation",
                rank=0,
                hit=hit,
                used_inheritance_expansion=False,
            )
        ]
    )
    assert accepted == 1


def test_emit_build_and_file_inventory_events() -> None:
    svc = BigQueryTelemetryService(
        _settings(
            bq_telemetry_enabled=True,
            bq_project_id="p1",
            bq_dataset_id="d1",
        )
    )
    ok_build = svc.emit_build_run(
        BuildRunEvent(
            build_id="b1",
            build_type="single-module",
            status="complete",
            total_files=10,
            changed_files=2,
            reused_files=8,
            documents_ingested=2,
            chunks_created=12,
            modules_built=1,
            failed_files=0,
            quarantined_files=0,
            checkpoint_writes=1,
            index_path="data/index.pkl",
        )
    )
    ok_file = svc.emit_file_inventory(
        FileInventoryEvent(
            build_id="b1",
            module_id="math_core",
            file_path="a.txt",
            action="processed",
            file_signature="123:456",
            chunk_count=2,
        )
    )
    assert ok_build is True
    assert ok_file is True


def test_emit_chunk_metadata_events() -> None:
    svc = BigQueryTelemetryService(
        _settings(
            bq_telemetry_enabled=True,
            bq_project_id="p1",
            bq_dataset_id="d1",
            bq_chunk_metadata_table="chunk_metadata_catalog",
        )
    )
    chunk = DocumentChunk(
        chunk_id="c1",
        text="In 1789 Europe saw major change.",
        source="history.txt",
        module_id="humanities_brain",
        page=1,
        tags=["example"],
        metadata={
            "context": {
                "period_start": 1789,
                "period_end": 1789,
                "region": "europe",
                "tradition": "enlightenment",
                "source_type": "primary",
            }
        },
    )
    accepted = svc.emit_chunk_metadata(
        [ChunkMetadataEvent(build_id="b1", chunk=chunk)]
    )
    assert accepted == 1


def teardown_module() -> None:
    reset_telemetry_service_for_tests()

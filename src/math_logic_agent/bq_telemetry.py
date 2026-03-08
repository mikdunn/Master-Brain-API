from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import queue
from threading import Event, Lock, Thread
from typing import Any

from .config import Settings
from .models import DocumentChunk, RetrievedChunk


@dataclass(slots=True)
class TelemetryEvent:
    endpoint: str
    question: str
    mode: str
    confidence: float
    selected_modules: list[str]
    k: int
    latency_ms: int
    status_code: int
    error: str | None


@dataclass(slots=True)
class RetrievalHitEvent:
    query: str
    endpoint: str
    mode: str
    rank: int
    hit: RetrievedChunk
    used_inheritance_expansion: bool


@dataclass(slots=True)
class BuildRunEvent:
    build_id: str
    build_type: str
    status: str
    total_files: int
    changed_files: int
    reused_files: int
    documents_ingested: int
    chunks_created: int
    modules_built: int
    failed_files: int
    quarantined_files: int
    checkpoint_writes: int
    index_path: str


@dataclass(slots=True)
class FileInventoryEvent:
    build_id: str
    module_id: str
    file_path: str
    action: str
    file_signature: str | None = None
    chunk_count: int | None = None
    error: str | None = None


@dataclass(slots=True)
class ChunkMetadataEvent:
    build_id: str
    chunk: DocumentChunk
    retention_days: int = 365


@dataclass(slots=True)
class TimelineEvent:
    event_type: str
    severity: str
    source_component: str
    message: str
    context: dict[str, Any] | None = None


class BigQueryTelemetryService:
    """Best-effort async telemetry writer.

    Design goals:
    - never block API serving path
    - fail open on any import/network/auth errors
    - bounded memory via queue maxsize
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._enabled = bool(
            settings.bq_telemetry_enabled
            and settings.bq_project_id
            and settings.bq_dataset_id
            and settings.bq_query_table
        )
        self._queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue(
            maxsize=max(100, int(settings.bq_queue_maxsize))
        )
        self._stop = Event()
        self._thread: Thread | None = None
        self._client: Any = None
        self._client_lock = Lock()

        if self._enabled:
            self._thread = Thread(target=self._worker_loop, daemon=True, name="bq-telemetry")
            self._thread.start()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def emit_query_event(self, event: TelemetryEvent) -> bool:
        if not self._enabled:
            return False

        row = {
            "event_id": self._event_id(
                endpoint=event.endpoint,
                question=event.question,
                latency_ms=event.latency_ms,
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": event.endpoint,
            "query_hash": self._hash_text(event.question),
            "query_text": event.question if self._settings.bq_include_question_text else None,
            "mode": event.mode,
            "confidence_score": float(event.confidence),
            "selected_modules": list(event.selected_modules),
            "k": int(event.k),
            "latency_ms": int(event.latency_ms),
            "status_code": int(event.status_code),
            "error": event.error,
            "schema_version": 1,
        }
        return self._enqueue(self._settings.bq_query_table, row)

    def emit_retrieval_hits(self, events: list[RetrievalHitEvent]) -> int:
        if not self._enabled or not events:
            return 0

        accepted = 0
        for event in events:
            row = {
                "event_id": self._event_id(
                    endpoint=event.endpoint,
                    question=event.query,
                    latency_ms=event.rank,
                ),
                "timestamp": self._now_iso(),
                "endpoint": event.endpoint,
                "query_hash": self._hash_text(event.query),
                "mode": event.mode,
                "retrieval_rank": int(event.rank),
                "chunk_id": event.hit.chunk.chunk_id,
                "source": event.hit.chunk.source,
                "module_id": event.hit.chunk.module_id,
                "page": event.hit.chunk.page,
                "score": float(event.hit.score),
                "channel": event.hit.channel,
                "used_inheritance_expansion": bool(event.used_inheritance_expansion),
                "schema_version": 1,
            }
            if self._enqueue(self._settings.bq_retrieval_hits_table, row):
                accepted += 1
        return accepted

    def emit_build_run(self, event: BuildRunEvent) -> bool:
        if not self._enabled:
            return False
        row = {
            "event_id": self._event_id(
                endpoint="build",
                question=event.build_id,
                latency_ms=event.changed_files,
            ),
            "timestamp": self._now_iso(),
            "build_id": event.build_id,
            "build_type": event.build_type,
            "status": event.status,
            "total_files": int(event.total_files),
            "changed_files": int(event.changed_files),
            "reused_files": int(event.reused_files),
            "documents_ingested": int(event.documents_ingested),
            "chunks_created": int(event.chunks_created),
            "modules_built": int(event.modules_built),
            "failed_files": int(event.failed_files),
            "quarantined_files": int(event.quarantined_files),
            "checkpoint_writes": int(event.checkpoint_writes),
            "index_path": event.index_path,
            "schema_version": 1,
        }
        return self._enqueue(self._settings.bq_build_runs_table, row)

    def emit_file_inventory(self, event: FileInventoryEvent) -> bool:
        if not self._enabled:
            return False
        row = {
            "event_id": self._event_id(
                endpoint="file_inventory",
                question=f"{event.module_id}:{event.file_path}",
                latency_ms=0,
            ),
            "timestamp": self._now_iso(),
            "build_id": event.build_id,
            "module_id": event.module_id,
            "file_path": event.file_path,
            "action": event.action,
            "file_signature": event.file_signature,
            "chunk_count": event.chunk_count,
            "error": event.error,
            "schema_version": 1,
        }
        return self._enqueue(self._settings.bq_file_inventory_table, row)

    def emit_timeline_event(self, event: TimelineEvent) -> bool:
        if not self._enabled:
            return False
        row = {
            "event_id": self._event_id(
                endpoint=event.source_component,
                question=event.message,
                latency_ms=0,
            ),
            "timestamp": self._now_iso(),
            "event_type": event.event_type,
            "severity": event.severity,
            "source_component": event.source_component,
            "message": event.message,
            "context": dict(event.context or {}),
            "schema_version": 1,
        }
        return self._enqueue(self._settings.bq_timeline_events_table, row)

    def emit_chunk_metadata(self, events: list[ChunkMetadataEvent]) -> int:
        if not self._enabled or not events:
            return 0

        accepted = 0
        now_iso = self._now_iso()
        for event in events:
            chunk = event.chunk
            ctx = chunk.metadata.get("context", {}) if isinstance(chunk.metadata.get("context"), dict) else {}
            row = {
                "chunk_id": chunk.chunk_id,
                "source_file": chunk.source,
                "build_id": event.build_id,
                "module_id": chunk.module_id,
                "page": chunk.page,
                "section": chunk.section,
                "text_hash": self._hash_text(chunk.text),
                "text_preview": None,
                "char_length": len(chunk.text),
                "tags": list(chunk.tags),
                "confidence_low_quality": False,
                "has_equations": bool(chunk.metadata.get("equation_count", 0)),
                "equation_count": int(chunk.metadata.get("equation_count", 0) or 0),
                "created_timestamp": now_iso,
                "last_seen_timestamp": now_iso,
                "retention_days": int(event.retention_days),
                "period_start": ctx.get("period_start"),
                "period_end": ctx.get("period_end"),
                "region": ctx.get("region"),
                "tradition": ctx.get("tradition"),
                "source_type": ctx.get("source_type"),
                "schema_version": 1,
            }
            if self._enqueue(self._settings.bq_chunk_metadata_table, row):
                accepted += 1
        return accepted

    def close(self, timeout: float = 2.0) -> None:
        if not self._enabled:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(0.0, timeout))

    def _worker_loop(self) -> None:
        batch: list[tuple[str, dict[str, Any]]] = []
        batch_size = max(1, int(self._settings.bq_flush_batch_size))
        flush_every_s = max(1, int(self._settings.bq_flush_interval_seconds))

        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=flush_every_s)
                batch.append(item)
            except queue.Empty:
                pass

            if batch and (len(batch) >= batch_size or self._stop.is_set()):
                self._flush_batch(batch)
                batch.clear()

        # final drain
        while True:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if batch:
            self._flush_batch(batch)

    def _flush_batch(self, rows: list[tuple[str, dict[str, Any]]]) -> None:
        client = self._get_client()
        if client is None:
            return
        grouped: dict[str, list[dict[str, Any]]] = {}
        for table_name, row in rows:
            grouped.setdefault(table_name, []).append(row)

        for table_name, payload in grouped.items():
            table = f"{self._settings.bq_project_id}.{self._settings.bq_dataset_id}.{table_name}"
            try:
                client.insert_rows_json(
                    table,
                    payload,
                    timeout=float(self._settings.bq_insert_timeout_seconds),
                )
            except Exception:
                # Fail-open by design.
                continue

    def _enqueue(self, table_name: str, row: dict[str, Any]) -> bool:
        try:
            self._queue.put_nowait((table_name, row))
            return True
        except queue.Full:
            return False

    def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client

        with self._client_lock:
            if self._client is not None:
                return self._client
            try:
                from google.cloud import bigquery  # type: ignore

                self._client = bigquery.Client(project=self._settings.bq_project_id)
                return self._client
            except Exception:
                return None

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _chunk_hash(chunk: DocumentChunk) -> str:
        return hashlib.sha256(
            f"{chunk.chunk_id}|{chunk.source}|{chunk.page}".encode("utf-8", errors="ignore")
        ).hexdigest()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _event_id(*, endpoint: str, question: str, latency_ms: int) -> str:
        raw = f"{endpoint}|{question}|{latency_ms}|{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


_TELEMETRY: BigQueryTelemetryService | None = None
_TELEMETRY_LOCK = Lock()


def get_telemetry_service(settings: Settings) -> BigQueryTelemetryService:
    global _TELEMETRY
    with _TELEMETRY_LOCK:
        if _TELEMETRY is None:
            _TELEMETRY = BigQueryTelemetryService(settings)
        return _TELEMETRY


def reset_telemetry_service_for_tests() -> None:
    global _TELEMETRY
    with _TELEMETRY_LOCK:
        if _TELEMETRY is not None:
            _TELEMETRY.close(timeout=0.2)
        _TELEMETRY = None

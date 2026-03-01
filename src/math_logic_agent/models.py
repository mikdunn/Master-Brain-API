from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RawDocument:
    text: str
    source: str
    module_id: str | None = None
    page: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocumentChunk:
    chunk_id: str
    text: str
    source: str
    module_id: str | None = None
    page: int | None = None
    section: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RetrievedChunk:
    chunk: DocumentChunk
    score: float
    channel: str

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from .models import DocumentChunk, RawDocument

THEOREM_HINTS = {
    "theorem",
    "lemma",
    "corollary",
    "definition",
    "proof",
    "example",
    "exercise",
    "proposition",
}


def detect_tags(text: str) -> list[str]:
    lower = text.lower()
    tags = [hint for hint in THEOREM_HINTS if hint in lower]
    if re.search(r"\bsvd\b|singular value", lower):
        tags.append("svd")
    if re.search(r"\beigen(value|vector| decomposition)?\b", lower):
        tags.append("eigen")
    if re.search(r"\bgradient|derivative|integral\b", lower):
        tags.append("calculus")
    return sorted(set(tags))


def split_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _chunk_id(source: str, page: int | None, idx: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:12]
    page_part = page if page is not None else "na"
    return f"{source}::{page_part}::{idx}::{digest}"


def chunk_documents(
    docs: Iterable[RawDocument],
    max_chars: int = 1200,
    overlap: int = 150,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for doc in docs:
        pieces = split_text(doc.text, max_chars=max_chars, overlap=overlap)
        for i, piece in enumerate(pieces):
            chunks.append(
                DocumentChunk(
                    chunk_id=_chunk_id(doc.source, doc.page, i, piece),
                    text=piece,
                    source=doc.source,
                    module_id=doc.module_id,
                    page=doc.page,
                    section=doc.section,
                    tags=detect_tags(piece),
                    metadata=doc.metadata.copy(),
                )
            )
    return chunks

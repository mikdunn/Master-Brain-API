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

    # Tensor / multilinear algebra.
    tensor_re = (
        r"\btensor(s)?\b|\bmultilinear\b|\bkronecker\b|\bkhatri[-\s]?rao\b|"
        r"\bouter product\b|\bcp decomposition\b|\btucker\b|\btensor train\b"
    )
    if re.search(tensor_re, lower):
        tags.append("tensor")
    return sorted(set(tags))


def split_text(
    text: str,
    max_chars: int = 1200,
    overlap: int = 150,
) -> list[str]:
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
    raw = text.encode("utf-8", errors="ignore")
    digest = hashlib.sha1(raw).hexdigest()[:12]
    page_part = page if page is not None else "na"
    return f"{source}::{page_part}::{idx}::{digest}"


def _guess_source_type(text: str) -> str | None:
    lower = text.lower()
    hints: list[tuple[str, tuple[str, ...]]] = [
        ("primary", ("primary source", "letter", "diary", "speech", "declaration", "treatise", "manuscript")),
        ("literary", ("poem", "novel", "play", "drama", "stanza", "narrative")),
        ("scholarly", ("journal", "article", "paper", "peer-reviewed", "citation")),
        ("historical", ("chronicle", "archive", "historical", "timeline", "era")),
    ]
    for label, words in hints:
        if any(w in lower for w in words):
            return label
    return None


def _guess_region(text: str) -> str | None:
    lower = text.lower()
    regions: list[tuple[str, tuple[str, ...]]] = [
        ("europe", ("europe", "european", "france", "germany", "italy", "britain", "england", "rome", "greek")),
        ("middle_east", ("middle east", "arab", "persia", "ottoman", "mesopotamia")),
        ("east_asia", ("china", "japan", "korea", "east asia")),
        ("south_asia", ("india", "south asia", "indian")),
        ("africa", ("africa", "african", "sahara", "ethiopia", "egypt")),
        ("americas", ("america", "united states", "u.s.", "latin america", "canada", "mexico")),
    ]
    for label, words in regions:
        if any(w in lower for w in words):
            return label
    return None


def _guess_tradition(text: str) -> str | None:
    lower = text.lower()
    traditions: list[tuple[str, tuple[str, ...]]] = [
        ("classical", ("classical", "antiquity", "greco-roman")),
        ("enlightenment", ("enlightenment", "reason", "18th century")),
        ("romanticism", ("romanticism", "romantic")),
        ("modernism", ("modernism", "modernist")),
        ("postmodernism", ("postmodern", "post-structural")),
        ("marxism", ("marx", "marxist", "historical materialism")),
        ("liberalism", ("liberalism", "liberal")),
    ]
    for label, words in traditions:
        if any(w in lower for w in words):
            return label
    return None


def infer_humanities_context(text: str) -> dict[str, object]:
    years = [int(y) for y in re.findall(r"\b(1[0-9]{3}|20[0-9]{2}|[5-9][0-9]{2})\b", text)]
    period_start = min(years) if years else None
    period_end = max(years) if years else None
    return {
        "period_start": period_start,
        "period_end": period_end,
        "region": _guess_region(text),
        "tradition": _guess_tradition(text),
        "source_type": _guess_source_type(text),
    }


def chunk_documents(
    docs: Iterable[RawDocument],
    max_chars: int = 1200,
    overlap: int = 150,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for doc in docs:
        pieces = split_text(doc.text, max_chars=max_chars, overlap=overlap)
        for i, piece in enumerate(pieces):
            meta = doc.metadata.copy()
            existing_context = meta.get("context", {}) if isinstance(meta.get("context"), dict) else {}
            inferred_context = infer_humanities_context(piece)
            merged_context: dict[str, object] = dict(existing_context)
            for key, value in inferred_context.items():
                if merged_context.get(key) is None and value is not None:
                    merged_context[key] = value
            if merged_context:
                meta["context"] = merged_context

            chunks.append(
                DocumentChunk(
                    chunk_id=_chunk_id(doc.source, doc.page, i, piece),
                    text=piece,
                    source=doc.source,
                    module_id=doc.module_id,
                    page=doc.page,
                    section=doc.section,
                    tags=detect_tags(piece),
                    metadata=meta,
                )
            )
    return chunks

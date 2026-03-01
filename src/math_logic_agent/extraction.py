from __future__ import annotations

import re
from pathlib import Path


_WS_RE = re.compile(r"\s+")
_EQ_CANDIDATE_RE = re.compile(r"[=≈∝≤≥]|\\b(?:integral|derivative|gradient|hessian|sum|product)\\b", re.IGNORECASE)


def normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def is_low_quality_text(text: str, min_chars: int = 80) -> bool:
    cleaned = normalize_text(text)
    if len(cleaned) < min_chars:
        return True
    alpha = sum(ch.isalpha() for ch in cleaned)
    ratio = alpha / max(len(cleaned), 1)
    return ratio < 0.35


def extract_equations(text: str, max_equations: int = 8) -> list[str]:
    out: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_text(raw_line)
        if len(line) < 6:
            continue
        if not _EQ_CANDIDATE_RE.search(line):
            continue
        if line in out:
            continue
        out.append(line)
        if len(out) >= max_equations:
            break
    return out


def ocr_pdf_page(pdf_path: str | Path, page_number: int) -> str | None:
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception:
        return None

    try:
        images = convert_from_path(
            str(pdf_path),
            first_page=page_number,
            last_page=page_number,
            fmt="png",
        )
        if not images:
            return None
        text = pytesseract.image_to_string(images[0])
        text = normalize_text(text)
        return text or None
    except Exception:
        return None

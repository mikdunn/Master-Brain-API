from __future__ import annotations

from pathlib import Path
import re

CONFIG = Path("config/master_brain.toml")

BANNED_TOKENS = {
    "notes",
    "berklee",
    "stanford",
    "onlinelibrary",
    "wiley",
    "pearson",
    "cengage",
    "cambridge",
    "publisher",
    "publishers",
    "press",
    "textbook",
    "edition",
    "ed",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
}


def _canonical_key(alias: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", alias.lower())
    out = [
        t
        for t in tokens
        if t not in STOPWORDS
        and t not in BANNED_TOKENS
        and not re.fullmatch(r"\d+", t)
        and not re.fullmatch(r"\d{2,}[a-z]+", t)
        and not re.fullmatch(r"\d+(?:st|nd|rd|th)", t)
    ]
    return " ".join(out)


def _is_noisy(alias: str) -> bool:
    low = alias.lower().strip()
    tokens = re.findall(r"[a-z0-9]+", low)
    if not tokens:
        return True

    if any(t in BANNED_TOKENS for t in tokens):
        return True

    if any(re.fullmatch(r"\d+", t) for t in tokens):
        return True

    if any(re.fullmatch(r"\d{4,}", t) for t in tokens):
        return True

    if any(re.fullmatch(r"\d{2,}[a-z]+", t) for t in tokens):
        return True

    if any(re.fullmatch(r"\d+(?:st|nd|rd|th)", t) for t in tokens):
        return True

    return False


def main() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    lines = text.splitlines()

    out_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("aliases = ["):
            out_lines.append(line)
            i += 1

            alias_lines: list[str] = []
            while i < len(lines):
                current = lines[i]
                if current.strip() == "]":
                    break
                alias_lines.append(current)
                i += 1

            kept: list[str] = []
            seen: set[str] = set()
            for raw in alias_lines:
                m = re.match(r'^(\s*)"(.*)",(\s*)$', raw)
                if not m:
                    continue
                indent, alias_text, _trail = m.groups()
                if _is_noisy(alias_text):
                    continue
                key = _canonical_key(alias_text)
                if not key:
                    continue
                if key in seen:
                    continue
                seen.add(key)
                kept.append(f'{indent}"{alias_text}",')

            out_lines.extend(kept)
            if i < len(lines) and lines[i].strip() == "]":
                out_lines.append(lines[i])
                i += 1
            continue

        out_lines.append(line)
        i += 1

    CONFIG.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(str(CONFIG.resolve()))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .indexing import IndexStore
from .orchestrator import detect_mode


@dataclass(slots=True)
class BenchmarkCase:
    query: str
    expected_mode: str | None
    expected_terms: list[str]


@dataclass(slots=True)
class BenchmarkResult:
    total: int
    mode_accuracy: float
    retrieval_hit_rate: float


def load_benchmark_cases(path: str | Path) -> list[BenchmarkCase]:
    p = Path(path)
    cases: list[BenchmarkCase] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            cases.append(
                BenchmarkCase(
                    query=row["query"],
                    expected_mode=row.get("expected_mode"),
                    expected_terms=row.get("expected_terms", []),
                )
            )
    return cases


def run_benchmark(index: IndexStore, cases: list[BenchmarkCase], k: int = 6) -> BenchmarkResult:
    if not cases:
        return BenchmarkResult(total=0, mode_accuracy=0.0, retrieval_hit_rate=0.0)

    mode_correct = 0
    retrieval_hit = 0

    for case in cases:
        if case.expected_mode:
            pred_mode = detect_mode(case.query)
            if pred_mode == case.expected_mode:
                mode_correct += 1

        hits = index.retriever.search(case.query, k=k)
        if not case.expected_terms:
            retrieval_hit += 1 if hits else 0
        else:
            joined = "\n".join(h.chunk.text.lower() for h in hits)
            if any(term.lower() in joined for term in case.expected_terms):
                retrieval_hit += 1

    mode_denom = sum(1 for c in cases if c.expected_mode)
    mode_acc = (mode_correct / mode_denom) if mode_denom else 0.0
    retrieval_rate = retrieval_hit / len(cases)

    return BenchmarkResult(total=len(cases), mode_accuracy=mode_acc, retrieval_hit_rate=retrieval_rate)

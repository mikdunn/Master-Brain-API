from pathlib import Path

from math_logic_agent.benchmark import load_benchmark_cases, run_benchmark
from math_logic_agent.chunking import chunk_documents
from math_logic_agent.indexing import IndexStore
from math_logic_agent.models import RawDocument


def test_benchmark_runs(tmp_path: Path) -> None:
    docs = [
        RawDocument(text="Definition: SVD means singular value decomposition.", source="a.txt", page=1),
        RawDocument(text="Exercise: solve x^2-4=0.", source="b.txt", page=2),
    ]
    index = IndexStore(chunk_documents(docs), cloud_rerank=False)

    ds = tmp_path / "bench.jsonl"
    ds.write_text(
        "\n".join(
            [
                '{"query":"What is SVD?","expected_mode":"explanation","expected_terms":["singular value decomposition"]}',
                '{"query":"solve x^2-4=0 for x","expected_mode":"symbolic","expected_terms":["solve"]}',
            ]
        ),
        encoding="utf-8",
    )

    cases = load_benchmark_cases(ds)
    result = run_benchmark(index, cases, k=3)
    assert result.total == 2
    assert 0.0 <= result.mode_accuracy <= 1.0
    assert 0.0 <= result.retrieval_hit_rate <= 1.0

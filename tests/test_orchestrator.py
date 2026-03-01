from math_logic_agent.chunking import chunk_documents
from math_logic_agent.indexing import IndexStore
from math_logic_agent.models import RawDocument
from math_logic_agent.orchestrator import answer_query, detect_mode


def _make_index() -> IndexStore:
    docs = [
        RawDocument(
            text="Definition: The singular value decomposition factorizes A = U Sigma V^T.",
            source="lin_alg.pdf",
            page=12,
        ),
        RawDocument(
            text="Exercise: Solve the least squares system using pseudoinverse.",
            source="lin_alg.pdf",
            page=44,
        ),
    ]
    chunks = chunk_documents(docs)
    return IndexStore(chunks)


def test_detect_mode_priority() -> None:
    assert detect_mode("solve x^2-1=0") == "symbolic"
    assert detect_mode("implement this in python with numpy") == "coding"
    assert detect_mode("make me an exam quiz") == "exam"
    assert detect_mode("what is svd") == "explanation"


def test_answer_query_returns_context() -> None:
    index = _make_index()
    resp = answer_query(index, "What is SVD?")
    assert resp.mode == "explanation"
    assert "Context" in resp.answer or "Explain clearly" in resp.answer
    assert len(resp.context) > 0

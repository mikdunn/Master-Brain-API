from math_logic_agent.chunking import chunk_documents
from math_logic_agent.indexing import IndexStore
from math_logic_agent.models import RawDocument
from math_logic_agent.orchestrator import answer_query


def test_answer_includes_confidence() -> None:
    docs = [
        RawDocument(text="Definition: SVD is singular value decomposition.", source="lin_alg.pdf", page=3),
        RawDocument(text="Proof sketch for orthogonality of U and V.", source="lin_alg.pdf", page=8),
    ]
    index = IndexStore(chunk_documents(docs), cloud_rerank=False)
    resp = answer_query(index=index, query="What is the definition of SVD?", k=3)
    assert 0.0 <= resp.confidence <= 1.0
    assert resp.confidence_label in {"low", "medium", "high"}

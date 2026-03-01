from math_logic_agent.models import DocumentChunk
from math_logic_agent.retrieval import HybridRetriever


def test_theorem_aware_boost_prefers_definition_chunks() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="a",
            text="Definition: Singular value decomposition factorizes A into U Sigma V^T.",
            source="lin_alg.pdf",
            page=1,
            tags=["definition", "svd"],
        ),
        DocumentChunk(
            chunk_id="b",
            text="Historical note about numerical linear algebra.",
            source="history.pdf",
            page=5,
            tags=[],
        ),
    ]
    retriever = HybridRetriever(chunks, embedder=None)
    hits = retriever.search("What is the definition of SVD?", k=1)
    assert hits
    assert hits[0].chunk.chunk_id == "a"

from math_logic_agent.chunking import chunk_documents
from math_logic_agent.indexing import IndexStore
from math_logic_agent.models import DocumentChunk, RawDocument
from math_logic_agent.retrieval import HybridRetriever
from math_logic_agent.orchestrator import answer_query


def test_tensor_tag_boost_prefers_tensor_chunks() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="a",
            text="Kronecker product and Tucker decomposition.",
            source="tensor.pdf",
            page=1,
            tags=["tensor"],
        ),
        DocumentChunk(
            chunk_id="b",
            text="Kronecker product and Tucker decomposition.",
            source="matrix.pdf",
            page=2,
            tags=[],
        ),
    ]
    retriever = HybridRetriever(chunks, embedder=None)
    hits = retriever.search("tensor kronecker product", k=1)
    assert hits
    assert hits[0].chunk.chunk_id == "a"


def test_routing_uses_index_module_aliases_for_master_brain_modules() -> None:
    docs = [
        RawDocument(
            text="Notes on basic linear algebra.",
            source="math.pdf",
            module_id="math_brain",
            page=1,
        ),
        RawDocument(
            text="Quantum mechanics: measurement and observables.",
            source="physics.pdf",
            module_id="physics_brain",
            page=1,
        ),
    ]
    idx = IndexStore(
        chunk_documents(docs),
        cloud_rerank=False,
        module_aliases={
            "math_brain": ["math", "linear algebra"],
            "physics_brain": ["physics", "quantum"],
        },
    )
    resp = answer_query(idx, "Explain a quantum measurement postulate", k=3)
    assert "physics_brain" in resp.selected_modules
    assert resp.context

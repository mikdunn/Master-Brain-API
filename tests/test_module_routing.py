from math_logic_agent.chunking import chunk_documents
from math_logic_agent.indexing import IndexStore
from math_logic_agent.models import RawDocument
from math_logic_agent.orchestrator import answer_query


def test_module_routing_prefers_physics() -> None:
    docs = [
        RawDocument(
            text="Definition: Newton's laws describe mechanics and force.",
            source="physics.pdf",
            module_id="physics_core",
            page=1,
        ),
        RawDocument(
            text="Definition: SVD factorizes matrices.",
            source="math.pdf",
            module_id="math_core",
            page=1,
        ),
    ]
    idx = IndexStore(chunk_documents(docs), cloud_rerank=False)
    resp = answer_query(idx, "Explain a basic mechanics law", k=3)
    assert "physics_core" in resp.selected_modules
    assert len(resp.context) > 0

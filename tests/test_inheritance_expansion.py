from math_logic_agent.chunking import chunk_documents
from math_logic_agent.indexing import IndexStore
from math_logic_agent.models import RawDocument
from math_logic_agent.orchestrator import answer_query


def test_answer_query_expands_prereqs_when_coverage_low() -> None:
    docs = [
        RawDocument(
            text=(
                "Mechanics overview: Newton's laws relate force, "
                "mass, and acceleration."
            ),
            source="physics.pdf",
            module_id="physics_core",
            page=1,
        ),
        RawDocument(
            text=(
                "Linear algebra: eigenvalues and the singular value "
                "decomposition (SVD) are matrix factorization tools."
            ),
            source="math.pdf",
            module_id="math_core",
            page=2,
        ),
    ]

    idx = IndexStore(
        chunk_documents(docs),
        cloud_rerank=False,
        module_inheritance={
            "physics_core": ["math_core"],
        },
    )

    resp = answer_query(
        idx,
        "In mechanics, how does SVD relate to eigenvalues?",
        k=3,
    )

    assert "physics_core" in resp.selected_modules
    assert "math_core" in resp.selected_modules
    has_prereq_context = any(
        "eigenvalues" in c.lower() or "svd" in c.lower() for c in resp.context
    )
    assert has_prereq_context

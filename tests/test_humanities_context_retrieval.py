from math_logic_agent.models import DocumentChunk
from math_logic_agent.retrieval import HybridRetriever, _context_boost, _query_context_hints


def test_query_context_hints_extracts_time_region_tradition_source_type() -> None:
    hints = _query_context_hints(
        "In 1789 Europe during the Enlightenment, analyze this primary source"
    )
    assert 1789 in hints["years"]
    assert "europe" in hints["regions"]
    assert "enlightenment" in hints["traditions"]
    assert "primary" in hints["source_types"]


def test_context_boost_is_positive_for_matching_chunk_context() -> None:
    hints = _query_context_hints(
        "In 1789 Europe during the Enlightenment, analyze this primary source"
    )
    chunk = DocumentChunk(
        chunk_id="c1",
        text="A historical letter.",
        source="history.txt",
        module_id="humanities_brain",
        page=1,
        metadata={
            "context": {
                "period_start": 1780,
                "period_end": 1795,
                "region": "europe",
                "tradition": "enlightenment",
                "source_type": "primary",
            }
        },
    )
    assert _context_boost(hints, chunk) > 0.0


def test_humanities_context_boost_improves_ranking_for_matching_context() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="a",
            text="Historical political thought and social change.",
            source="europe.txt",
            module_id="humanities_brain",
            page=1,
            metadata={
                "context": {
                    "period_start": 1780,
                    "period_end": 1795,
                    "region": "europe",
                    "tradition": "enlightenment",
                    "source_type": "primary",
                }
            },
        ),
        DocumentChunk(
            chunk_id="b",
            text="Historical political thought and social change.",
            source="asia.txt",
            module_id="humanities_brain",
            page=1,
            metadata={
                "context": {
                    "period_start": 1100,
                    "period_end": 1200,
                    "region": "east_asia",
                    "tradition": "classical",
                    "source_type": "scholarly",
                }
            },
        ),
    ]
    retriever = HybridRetriever(chunks, embedder=None)
    hits = retriever.search(
        "In 1789 Europe during the Enlightenment, analyze this primary source",
        k=1,
    )
    assert hits
    assert hits[0].chunk.chunk_id == "a"


def test_non_context_query_keeps_existing_behavior() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="a",
            text="Definition: Singular value decomposition factorizes matrices.",
            source="lin_alg.pdf",
            page=1,
            tags=["definition", "svd"],
            metadata={"context": {"region": "europe", "tradition": "enlightenment"}},
        ),
        DocumentChunk(
            chunk_id="b",
            text="Historical note about art movements.",
            source="arts.pdf",
            page=1,
            tags=[],
            metadata={"context": {"region": "europe", "tradition": "enlightenment"}},
        ),
    ]
    retriever = HybridRetriever(chunks, embedder=None)
    hits = retriever.search("What is the definition of SVD?", k=1)
    assert hits
    assert hits[0].chunk.chunk_id == "a"

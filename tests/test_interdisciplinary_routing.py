from math_logic_agent.chunking import chunk_documents
from math_logic_agent.indexing import IndexStore
from math_logic_agent.models import RawDocument
from math_logic_agent.orchestrator import (
    _fuse_interdisciplinary_hits,
    _is_interdisciplinary_query,
    _is_interdisciplinary_selection,
    _widen_for_interdisciplinary,
    answer_query,
    retrieve_hits,
)


def test_is_interdisciplinary_query_true_with_cues_and_multi_family() -> None:
    ranked = [
        ("humanities_brain", 3),
        ("business_brain", 2),
        ("science_brain", 1),
    ]
    assert _is_interdisciplinary_query(
        "Connect philosophy and economics across history",
        ranked,
    )


def test_widen_for_interdisciplinary_prefers_family_diversity() -> None:
    ranked = [
        ("humanities_brain", 5),
        ("humanities_brain_literature", 4),
        ("business_brain", 3),
        ("science_brain", 2),
        ("math_brain", 1),
    ]
    picked = _widen_for_interdisciplinary(ranked, limit=4)
    assert picked[0] == "humanities_brain"
    assert "business_brain" in picked
    assert "science_brain" in picked


def test_answer_query_widens_selected_modules_for_interdisciplinary_prompt() -> None:
    docs = [
        RawDocument(
            text="Philosophy and historical interpretation methods.",
            source="humanities.md",
            module_id="humanities_brain",
            page=1,
        ),
        RawDocument(
            text="Economics and political institutions in modern states.",
            source="business.md",
            module_id="business_brain",
            page=1,
        ),
        RawDocument(
            text="Scientific method and evidence standards.",
            source="science.md",
            module_id="science_brain",
            page=1,
        ),
    ]
    idx = IndexStore(
        chunk_documents(docs),
        cloud_rerank=False,
        module_aliases={
            "humanities_brain": ["philosophy", "history", "literature"],
            "business_brain": ["economics", "politics", "policy"],
            "science_brain": ["science", "method"],
        },
    )

    resp = answer_query(
        idx,
        "Connect philosophy and economics across history with science methods",
        k=6,
    )

    assert "humanities_brain" in resp.selected_modules
    assert "business_brain" in resp.selected_modules
    assert len(resp.selected_modules) >= 2


def test_is_interdisciplinary_selection_requires_multi_family_modules() -> None:
    assert _is_interdisciplinary_selection(
        "Connect philosophy and economics across history",
        ["humanities_brain", "business_brain"],
    )
    assert not _is_interdisciplinary_selection(
        "Connect ideas",
        ["humanities_brain", "humanities_brain_literature"],
    )


def test_retrieve_hits_diversifies_top_k_for_interdisciplinary_query() -> None:
    docs = [
        RawDocument(
            text="Connect philosophy and economics across history.",
            source="h1.md",
            module_id="humanities_brain",
            page=1,
        ),
        RawDocument(
            text="Connect philosophy and economics across history.",
            source="h2.md",
            module_id="humanities_brain",
            page=2,
        ),
        RawDocument(
            text="Connect philosophy and economics across history.",
            source="b1.md",
            module_id="business_brain",
            page=1,
        ),
    ]
    idx = IndexStore(
        chunk_documents(docs),
        cloud_rerank=False,
        module_aliases={
            "humanities_brain": ["philosophy", "history"],
            "business_brain": ["economics", "policy", "politics"],
        },
    )

    result = retrieve_hits(
        index=idx,
        query="Connect philosophy and economics across history",
        k=2,
    )
    top_modules = {h.chunk.module_id for h in result.hits[:2]}
    assert "humanities_brain" in top_modules
    assert "business_brain" in top_modules


def test_fuse_interdisciplinary_hits_preserves_primary_order_after_seeds() -> None:
    docs = [
        RawDocument(
            text="Connect philosophy and economics across history.",
            source="h1.md",
            module_id="humanities_brain",
            page=1,
        ),
        RawDocument(
            text="Connect philosophy and economics across history.",
            source="b1.md",
            module_id="business_brain",
            page=1,
        ),
    ]
    idx = IndexStore(
        chunk_documents(docs),
        cloud_rerank=False,
        module_aliases={
            "humanities_brain": ["philosophy", "history"],
            "business_brain": ["economics", "policy"],
        },
    )
    primary = idx.retriever.search(
        "Connect philosophy and economics across history",
        k=2,
        allowed_modules={"humanities_brain", "business_brain"},
    )
    fused = _fuse_interdisciplinary_hits(
        index=idx,
        query="Connect philosophy and economics across history",
        selected_modules=["humanities_brain", "business_brain"],
        hits=primary,
        k=2,
    )
    assert len(fused) == 2


def test_fuse_interdisciplinary_hits_honors_min_per_brain_quota() -> None:
    docs = [
        RawDocument(
            text="Connect philosophy and economics across history.",
            source="h1.md",
            module_id="humanities_brain",
            page=1,
        ),
        RawDocument(
            text="Connect philosophy and economics across history.",
            source="h2.md",
            module_id="humanities_brain",
            page=2,
        ),
        RawDocument(
            text="Connect philosophy and economics across history.",
            source="b1.md",
            module_id="business_brain",
            page=1,
        ),
        RawDocument(
            text="Connect philosophy and economics across history.",
            source="b2.md",
            module_id="business_brain",
            page=2,
        ),
    ]
    idx = IndexStore(
        chunk_documents(docs),
        cloud_rerank=False,
        module_aliases={
            "humanities_brain": ["philosophy", "history"],
            "business_brain": ["economics", "policy"],
        },
    )
    primary = idx.retriever.search(
        "Connect philosophy and economics across history",
        k=6,
        allowed_modules={"humanities_brain", "business_brain"},
    )
    fused = _fuse_interdisciplinary_hits(
        index=idx,
        query="Connect philosophy and economics across history",
        selected_modules=["humanities_brain", "business_brain"],
        hits=primary,
        k=4,
        min_per_brain=2,
        seed_score_ratio=0.0,
    )
    top_modules = [h.chunk.module_id for h in fused[:4]]
    assert top_modules.count("humanities_brain") >= 2
    assert top_modules.count("business_brain") >= 2


def test_fuse_interdisciplinary_hits_respects_seed_score_ratio_gate() -> None:
    docs = [
        RawDocument(
            text="Connect philosophy and economics across history with detailed interpretation and methods.",
            source="h1.md",
            module_id="humanities_brain",
            page=1,
        ),
        RawDocument(
            text="Economics summary.",
            source="b1.md",
            module_id="business_brain",
            page=1,
        ),
    ]
    idx = IndexStore(
        chunk_documents(docs),
        cloud_rerank=False,
        module_aliases={
            "humanities_brain": ["philosophy", "history", "interpretation"],
            "business_brain": ["economics"],
        },
    )
    primary = idx.retriever.search(
        "Connect philosophy and economics across history with interpretation",
        k=4,
        allowed_modules={"humanities_brain", "business_brain"},
    )
    # Very strict ratio should suppress lower-scoring module seeds.
    fused = _fuse_interdisciplinary_hits(
        index=idx,
        query="Connect philosophy and economics across history with interpretation",
        selected_modules=["humanities_brain", "business_brain"],
        hits=primary,
        k=2,
        min_per_brain=1,
        seed_score_ratio=0.99,
    )
    assert fused

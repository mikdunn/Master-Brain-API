from math_logic_agent.chunking import chunk_documents
from math_logic_agent.indexing import IndexStore
from math_logic_agent.models import RawDocument
from math_logic_agent.orchestrator import answer_query
import math_logic_agent.orchestrator as orchestrator


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


def test_module_routing_uses_registry_aliases(tmp_path) -> None:
    cfg = tmp_path / "master_brain.toml"
    cfg.write_text(
        """
schema_version = 1

[modules.humanities_brain]
display_name = "Humanities Brain"
paths = ["C:/tmp/humanities"]
enabled = true
stage = "active"
priority = 70
aliases = ["philosophy", "history"]

[modules.math_brain]
display_name = "Math Brain"
paths = ["C:/tmp/math"]
enabled = true
stage = "active"
priority = 10
aliases = ["math", "algebra"]
""",
        encoding="utf-8",
    )
    docs = [
        RawDocument(
            text="Philosophy examines epistemology and ethics.",
            source="humanities.md",
            module_id="humanities_brain",
            page=1,
        ),
        RawDocument(
            text="Algebra studies equations and structures.",
            source="math.md",
            module_id="math_brain",
            page=1,
        ),
    ]
    idx = IndexStore(chunk_documents(docs), cloud_rerank=False)

    old_paths = orchestrator.ROUTING_MODULE_CONFIG_PATHS
    orchestrator.ROUTING_MODULE_CONFIG_PATHS = (str(cfg),)
    try:
        resp = answer_query(idx, "Explain philosophy methods", k=3)
    finally:
        orchestrator.ROUTING_MODULE_CONFIG_PATHS = old_paths

    assert "humanities_brain" in resp.selected_modules

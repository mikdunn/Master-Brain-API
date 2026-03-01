from pathlib import Path

from math_logic_agent.indexing import IndexStore


def test_build_from_modules(tmp_path: Path) -> None:
    root_a = tmp_path / "Math"
    root_b = tmp_path / "Microscopy"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "a.txt").write_text("SVD decomposes matrices.", encoding="utf-8")
    (root_b / "b.txt").write_text("Microscopy captures cellular images.", encoding="utf-8")

    cfg = tmp_path / "modules.toml"
    cfg.write_text(
        f"""
schema_version = 1

[modules.math_core]
display_name = \"Math\"
paths = [\"{root_a.as_posix()}\"]
enabled = true
stage = \"active\"
priority = 10
aliases = [\"math\"]

[modules.microscopy_core]
display_name = \"Microscopy\"
paths = [\"{root_b.as_posix()}\"]
enabled = true
stage = \"active\"
priority = 20
aliases = [\"microscopy\"]
""",
        encoding="utf-8",
    )

    index_path = tmp_path / "brain.pkl"
    store, summary = IndexStore.build_from_modules(
        module_config_path=cfg,
        index_path=index_path,
        incremental=True,
        cloud_rerank=False,
        ocr_fallback=False,
    )
    store.save(index_path)

    assert summary.modules_built == 2
    assert summary.total_files == 2
    assert len(store.chunks) > 0
    assert {c.module_id for c in store.chunks} == {"math_core", "microscopy_core"}

from pathlib import Path

from math_logic_agent.config import load_module_registry
from math_logic_agent.master_brain import (
    render_master_module_registry_toml,
    scaffold_master_brain_structure,
    write_master_module_registry,
)


def test_scaffold_master_brain_structure_creates_template_dirs(tmp_path: Path) -> None:
    summary = scaffold_master_brain_structure(tmp_path)
    assert summary.total_directories > 50
    assert summary.created_directories == summary.total_directories
    assert summary.existing_directories == 0

    summary2 = scaffold_master_brain_structure(tmp_path)
    assert summary2.created_directories == 0
    assert summary2.existing_directories == summary2.total_directories


def test_render_and_load_master_registry(tmp_path: Path) -> None:
    toml_text = render_master_module_registry_toml(tmp_path)
    cfg = tmp_path / "master_brain.toml"
    cfg.write_text(toml_text, encoding="utf-8")

    reg = load_module_registry(cfg)
    assert reg.schema_version == 1
    assert len(reg.modules) == 6
    ids = {m.module_id for m in reg.modules}
    assert ids == {
        "math_brain",
        "physics_brain",
        "engineering_brain",
        "science_brain",
        "business_brain",
        "cs_brain",
    }


def test_write_master_registry_respects_overwrite_flag(tmp_path: Path) -> None:
    cfg = tmp_path / "master.toml"
    write_master_module_registry(cfg, root=tmp_path, overwrite=True)
    first = cfg.read_text(encoding="utf-8")

    cfg.write_text("schema_version = 999\n", encoding="utf-8")
    write_master_module_registry(cfg, root=tmp_path, overwrite=False)
    assert cfg.read_text(encoding="utf-8") == "schema_version = 999\n"

    write_master_module_registry(cfg, root=tmp_path, overwrite=True)
    assert cfg.read_text(encoding="utf-8") == first

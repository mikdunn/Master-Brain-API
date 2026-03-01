from pathlib import Path

from math_logic_agent.config import load_module_registry


def test_load_module_registry(tmp_path: Path) -> None:
    cfg = tmp_path / "modules.toml"
    cfg.write_text(
        """
schema_version = 1

[modules.math_core]
display_name = \"Math\"
paths = [\"C:/tmp/math\"]
enabled = true
stage = \"active\"
priority = 10
aliases = [\"math\"]

[modules.physics_core]
display_name = \"Physics\"
paths = [\"C:/tmp/physics\"]
enabled = false
stage = \"active\"
priority = 20
aliases = [\"physics\"]
""",
        encoding="utf-8",
    )
    reg = load_module_registry(cfg)
    assert reg.schema_version == 1
    assert len(reg.modules) == 2
    enabled = reg.enabled_modules
    assert len(enabled) == 1
    assert enabled[0].module_id == "math_core"

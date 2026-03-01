import json
from pathlib import Path

from math_logic_agent.indexing import IndexStore
from math_logic_agent.resilience import QuarantineStore


def test_failed_file_is_quarantined_and_skipped_on_next_change(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()

    good = docs_root / "good.txt"
    good.write_text("Linear algebra basics", encoding="utf-8")

    bad = docs_root / "bad.pptx"
    bad.write_text("not a real pptx", encoding="utf-8")

    cfg = tmp_path / "modules.toml"
    cfg.write_text(
        f"""
schema_version = 1

[modules.test_core]
display_name = "Test"
paths = ["{docs_root.as_posix()}"]
enabled = true
stage = "active"
priority = 1
aliases = ["test"]
""",
        encoding="utf-8",
    )

    index_path = tmp_path / "brain.pkl"
    quarantine_path = tmp_path / "quarantine.json"

    store1, summary1 = IndexStore.build_from_modules(
        module_config_path=cfg,
        index_path=index_path,
        incremental=True,
        cloud_rerank=False,
        ocr_fallback=False,
        quarantine_path=quarantine_path,
        checkpoint_path=None,
    )
    store1.save(index_path)

    assert summary1.failed_files == 1
    assert summary1.quarantined_files == 0

    q = QuarantineStore(quarantine_path)
    assert len(q.records) == 1

    bad.write_text("still not a real pptx", encoding="utf-8")

    _, summary2 = IndexStore.build_from_modules(
        module_config_path=cfg,
        index_path=index_path,
        incremental=True,
        cloud_rerank=False,
        ocr_fallback=False,
        quarantine_path=quarantine_path,
        checkpoint_path=None,
    )

    assert summary2.failed_files == 0
    assert summary2.quarantined_files == 1


def test_build_writes_checkpoint_file(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "a.txt").write_text("alpha topic", encoding="utf-8")
    (docs_root / "b.txt").write_text("beta topic", encoding="utf-8")

    cfg = tmp_path / "modules.toml"
    cfg.write_text(
        f"""
schema_version = 1

[modules.test_core]
display_name = "Test"
paths = ["{docs_root.as_posix()}"]
enabled = true
stage = "active"
priority = 1
aliases = ["test"]
""",
        encoding="utf-8",
    )

    index_path = tmp_path / "brain.pkl"
    checkpoint_path = tmp_path / "checkpoint.json"

    _, summary = IndexStore.build_from_modules(
        module_config_path=cfg,
        index_path=index_path,
        incremental=True,
        cloud_rerank=False,
        ocr_fallback=False,
        checkpoint_path=checkpoint_path,
        checkpoint_every=1,
    )

    assert summary.checkpoint_writes >= 1
    assert checkpoint_path.exists()

    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert payload["status"] == "complete"
    assert payload["kind"] == "multi-module"
    assert "updated_at" in payload

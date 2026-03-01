from pathlib import Path

import math_logic_agent.api as api
from math_logic_agent.config import Settings


def _settings(default_index: str) -> Settings:
    return Settings(
        openai_api_key=None,
        perplexity_api_key=None,
        openai_embed_model="text-embedding-3-small",
        cloud_rerank_enabled=False,
        bridge_api_key=None,
        bridge_host="127.0.0.1",
        bridge_port=8787,
        bridge_default_index_path=default_index,
    )


def test_resolve_index_path_uses_project_root_for_default_relative(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "project-a"
    index = project / "data" / "master_brain_index.pkl"
    index.parent.mkdir(parents=True)
    index.write_bytes(b"index")

    monkeypatch.setattr(api, "_settings", _settings("data/master_brain_index.pkl"))
    resolved = api._resolve_index_path(None, str(project))

    assert resolved == index


def test_resolve_index_path_uses_explicit_relative_path_under_project_root(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "project-b"
    index = project / "custom" / "brain.pkl"
    index.parent.mkdir(parents=True)
    index.write_bytes(b"index")

    monkeypatch.setattr(api, "_settings", _settings("data/master_brain_index.pkl"))
    resolved = api._resolve_index_path("custom/brain.pkl", str(project))

    assert resolved == index


def test_resolve_index_path_accepts_absolute_path(monkeypatch, tmp_path: Path) -> None:
    index = tmp_path / "global.pkl"
    index.write_bytes(b"index")

    monkeypatch.setattr(api, "_settings", _settings("data/master_brain_index.pkl"))
    resolved = api._resolve_index_path(str(index), None)

    assert resolved == index

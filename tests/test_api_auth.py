from fastapi import HTTPException

import math_logic_agent.api as api
from math_logic_agent.config import Settings


def _settings_with_key(key: str) -> Settings:
    return Settings(
        openai_api_key=None,
        perplexity_api_key=None,
        openai_embed_model="text-embedding-3-small",
        cloud_rerank_enabled=False,
        bridge_api_key=key,
        bridge_host="127.0.0.1",
        bridge_port=8787,
        bridge_default_index_path="data/master_brain_index.pkl",
    )


def test_require_api_key_accepts_x_api_key(monkeypatch) -> None:
    monkeypatch.setattr(api, "_settings", _settings_with_key("abc123"))
    api._require_api_key(x_api_key="abc123", authorization=None)


def test_require_api_key_accepts_authorization_bearer(monkeypatch) -> None:
    monkeypatch.setattr(api, "_settings", _settings_with_key("abc123"))
    api._require_api_key(x_api_key=None, authorization="Bearer abc123")


def test_require_api_key_rejects_wrong_key(monkeypatch) -> None:
    monkeypatch.setattr(api, "_settings", _settings_with_key("abc123"))
    try:
        api._require_api_key(x_api_key="wrong", authorization=None)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 401

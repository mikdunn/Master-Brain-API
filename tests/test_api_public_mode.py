from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import math_logic_agent.api as api
from math_logic_agent.config import Settings
from math_logic_agent.models import DocumentChunk, RetrievedChunk
from math_logic_agent.orchestrator import RetrievalResult


def _public_settings(*, bridge_key: str, perplexity_key: str | None) -> Settings:
    return Settings(
        openai_api_key=None,
        perplexity_api_key=perplexity_key,
        openai_embed_model="text-embedding-3-small",
        cloud_rerank_enabled=False,
        bridge_api_key=bridge_key,
        bridge_host="127.0.0.1",
        bridge_port=8787,
        bridge_default_index_path="data/master_brain_index.pkl",
        bridge_public_mode=True,
        bridge_public_max_k=3,
        bridge_public_allow_admin_endpoints=False,
        bridge_public_return_context=False,
        bridge_rate_limit_rpm=0,
        bridge_rate_limit_burst=0,
    )


def test_public_mode_blocks_query_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(api, "_settings", _public_settings(bridge_key="secret", perplexity_key=None))
    client = TestClient(api.app)
    resp = client.post(
        "/v1/query",
        headers={"x-api-key": "secret"},
        json={"question": "hi", "k": 6, "project_root": "C:/should/not/matter"},
    )
    assert resp.status_code == 403


def test_public_mode_blocks_admin_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(api, "_settings", _public_settings(bridge_key="secret", perplexity_key=None))
    client = TestClient(api.app)
    resp = client.get("/v1/indexed-files", headers={"x-api-key": "secret"})
    assert resp.status_code == 403
    resp2 = client.get("/v1/config", headers={"x-api-key": "secret"})
    assert resp2.status_code == 403


def test_synthesize_requires_perplexity_key(monkeypatch) -> None:
    monkeypatch.setattr(api, "_settings", _public_settings(bridge_key="secret", perplexity_key=None))
    client = TestClient(api.app)
    resp = client.post(
        "/v1/synthesize",
        headers={"x-api-key": "secret"},
        json={"question": "hi"},
    )
    assert resp.status_code == 503


def test_synthesize_public_mode_clamps_k_and_ignores_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(api, "_settings", _public_settings(bridge_key="secret", perplexity_key="pplx"))

    # Ensure we ignore caller-provided paths in public mode.
    def _fake_resolve(index_path: str | None, project_root: str | None = None) -> Path:
        assert index_path is None
        assert project_root is None
        return tmp_path / "index.pkl"

    monkeypatch.setattr(api, "_resolve_index_path", _fake_resolve)

    # Ensure cloud rerank is forced off in public mode.
    def _fake_load_index(index_path: Path, cloud_rerank: bool):
        assert cloud_rerank is False
        return object()

    monkeypatch.setattr(api, "_load_index", _fake_load_index)

    # Ensure k is clamped to bridge_public_max_k.
    def _fake_retrieve_hits(*, index, query: str, k: int = 6):
        assert k == 3
        hit = RetrievedChunk(
            chunk=DocumentChunk(
                chunk_id="c1",
                text="Some grounded context.",
                source="file1.txt",
                module_id="math_core",
                page=None,
            ),
            score=0.9,
            channel="lexical",
        )
        return RetrievalResult(mode="explanation", selected_modules=["math_core"], hits=[hit])

    monkeypatch.setattr(api, "retrieve_hits", _fake_retrieve_hits)
    monkeypatch.setattr(api, "compute_confidence", lambda **_: 0.9)
    monkeypatch.setattr(api, "label_confidence", lambda _: "high")
    monkeypatch.setattr(api, "perplexity_chat_completions", lambda **_: "Synthesized answer [1]")

    client = TestClient(api.app)
    resp = client.post(
        "/v1/synthesize",
        headers={"x-api-key": "secret"},
        json={
            "question": "Explain it",
            "k": 50,
            "index_path": "C:/should/not/matter.pkl",
            "project_root": "C:/also/ignored",
            "cloud_rerank": True,
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["answer"] == "Synthesized answer [1]"
    assert data["selected_modules"] == ["math_core"]
    assert data["citations"] and data["citations"][0]["chunk_id"] == "c1"
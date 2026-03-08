from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import math_logic_agent.api as api
from math_logic_agent.config import Settings


def test_query_emits_telemetry(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(api, "_emit_query_telemetry", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(api, "_resolve_index_path", lambda *_args, **_kwargs: tmp_path / "index.pkl")
    monkeypatch.setattr(api, "_load_index", lambda **_kwargs: object())

    fake = SimpleNamespace(
        answer="ok",
        mode="explanation",
        confidence=0.75,
        confidence_label="high",
        selected_modules=["math_core"],
        context=["ctx"],
    )
    monkeypatch.setattr(api, "answer_query", lambda **_kwargs: fake)

    out = api.query(
        payload=api.QueryRequest(question="what is svd", k=6),
        x_project_root=None,
    )

    assert out.mode == "explanation"
    assert calls
    assert calls[0]["endpoint"] == "/v1/query"
    assert calls[0]["status_code"] == 200
    assert calls[0]["mode"] == "explanation"


def test_synthesize_emits_error_telemetry_on_provider_error(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(api, "_emit_query_telemetry", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(api, "_resolve_index_path", lambda *_args, **_kwargs: tmp_path / "index.pkl")
    monkeypatch.setattr(api, "_load_index", lambda **_kwargs: object())
    monkeypatch.setattr(
        api,
        "retrieve_hits",
        lambda **_kwargs: SimpleNamespace(mode="explanation", selected_modules=["math_core"], hits=[]),
    )

    monkeypatch.setattr(
        api,
        "_settings",
        Settings(
            openai_api_key=None,
            perplexity_api_key="pplx",
            openai_embed_model="text-embedding-3-small",
            cloud_rerank_enabled=False,
            bridge_api_key=None,
            bridge_host="127.0.0.1",
            bridge_port=8787,
            bridge_default_index_path="data/master_brain_index.pkl",
            bridge_rate_limit_rpm=0,
            bridge_rate_limit_burst=0,
        ),
    )

    def _raise(**_kwargs):
        raise api.PerplexityError("boom")

    monkeypatch.setattr(api, "perplexity_chat_completions", _raise)

    try:
        api.synthesize(
            payload=api.SynthesizeRequest(question="q", k=6),
            x_project_root=None,
        )
        assert False, "Expected HTTPException"
    except api.HTTPException as exc:
        assert exc.status_code == 502

    assert calls
    assert calls[0]["endpoint"] == "/v1/synthesize"
    assert calls[0]["status_code"] == 502

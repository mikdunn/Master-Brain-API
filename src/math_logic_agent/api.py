from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
from threading import Lock
import time
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .config import HARDCODED_BRIDGE_API_KEY, Settings
from .indexing import IndexStore
from .orchestrator import answer_query, compute_confidence, label_confidence, retrieve_hits
from .perplexity_client import PerplexityError, perplexity_chat_completions

app = FastAPI(title="Master Brain Bridge API", version="1.0.0")
_settings = Settings.from_env()
_cache_lock = Lock()
_cache: dict[str, tuple[int, IndexStore]] = {}

_rate_lock = Lock()
_rate_state: dict[str, tuple[float, float]] = {}


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    k: int = Field(6, ge=1, le=30)
    index_path: str | None = None
    project_root: str | None = None
    cloud_rerank: bool = False


class Citation(BaseModel):
    chunk_id: str
    source: str
    module_id: str | None = None
    page: int | None = None
    score: float


class SynthesizeRequest(BaseModel):
    question: str = Field(..., min_length=1)
    k: int = Field(6, ge=1, le=30)
    index_path: str | None = None
    project_root: str | None = None
    cloud_rerank: bool = False
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)


class SynthesizeResponse(BaseModel):
    answer: str
    mode: str
    confidence: float
    confidence_label: str
    selected_modules: list[str]
    citations: list[Citation]


class QueryResponse(BaseModel):
    answer: str
    mode: str
    confidence: float
    confidence_label: str
    selected_modules: list[str]
    context: list[str]


class FilesResponse(BaseModel):
    index_path: str
    indexed_file_count: int
    indexed_files: list[str]


def _resolve_index_path(index_path: str | None, project_root: str | None = None) -> Path:
    raw_path = (index_path or _settings.bridge_default_index_path).strip()
    path = Path(raw_path)

    candidate_roots: list[Path] = []
    if project_root:
        candidate_roots.append(Path(project_root).expanduser())

    env_workspace_root = (os.getenv("BRIDGE_WORKSPACE_ROOT") or "").strip()
    if env_workspace_root:
        candidate_roots.append(Path(env_workspace_root).expanduser())

    candidate_roots.append(Path.cwd())

    if path.is_absolute():
        candidates = [path]
    else:
        seen: set[Path] = set()
        candidates = []
        for root in candidate_roots:
            c = root / path
            if c not in seen:
                seen.add(c)
                candidates.append(c)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    looked = ", ".join(str(c) for c in candidates)
    raise HTTPException(status_code=404, detail=f"Index not found. Tried: {looked}")


def _is_public_mode() -> bool:
    return bool(getattr(_settings, "bridge_public_mode", False))


def _admin_endpoints_allowed() -> bool:
    return bool(getattr(_settings, "bridge_public_allow_admin_endpoints", False))


def _context_return_allowed() -> bool:
    # In public mode, default is to NOT return raw chunk text.
    if not _is_public_mode():
        return True
    return bool(getattr(_settings, "bridge_public_return_context", False))


def _public_k(k: int) -> int:
    max_k = int(getattr(_settings, "bridge_public_max_k", 10) or 10)
    return max(1, min(int(k), max_k))


def _require_api_key(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    required = _settings.bridge_api_key
    if not required:
        return

    # Safety: if someone accidentally enables public mode without setting a
    # real key, refuse to run with the hardcoded local fallback.
    if _is_public_mode() and required.strip() == HARDCODED_BRIDGE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="BRIDGE_PUBLIC_MODE is enabled but BRIDGE_API_KEY is still the local fallback. Set a strong BRIDGE_API_KEY.",
        )

    provided = (x_api_key or "").strip()
    auth_value = (authorization or "").strip()

    bearer = ""
    if auth_value.lower().startswith("bearer "):
        bearer = auth_value[7:].strip()

    if provided.lower().startswith("bearer "):
        provided = provided[7:].strip()

    if required not in {provided, bearer}:
        raise HTTPException(status_code=401, detail="Invalid API key")


def _rate_limit(request: Request) -> None:
    rpm = int(getattr(_settings, "bridge_rate_limit_rpm", 0) or 0)
    burst = int(getattr(_settings, "bridge_rate_limit_burst", 0) or 0)
    if rpm <= 0 or burst <= 0:
        return

    ip = "unknown"
    if request.client and request.client.host:
        ip = request.client.host

    now = time.monotonic()
    refill_per_sec = rpm / 60.0
    capacity = float(burst)

    with _rate_lock:
        tokens, last = _rate_state.get(ip, (capacity, now))
        elapsed = max(0.0, now - last)
        tokens = min(capacity, tokens + elapsed * refill_per_sec)
        if tokens < 1.0:
            _rate_state[ip] = (tokens, now)
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        tokens -= 1.0
        _rate_state[ip] = (tokens, now)


def _load_index(index_path: Path, cloud_rerank: bool) -> IndexStore:
    key = str(index_path.resolve())
    mtime = index_path.stat().st_mtime_ns
    with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1]
        store = IndexStore.load(index_path, cloud_rerank=cloud_rerank)
        _cache[key] = (mtime, store)
        return store


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "bridge_host": _settings.bridge_host,
        "bridge_port": _settings.bridge_port,
        "api_key_required": bool(_settings.bridge_api_key),
        "public_mode": _is_public_mode(),
        "default_index": _settings.bridge_default_index_path,
        "cwd": str(Path.cwd()),
    }


@app.post("/v1/query", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    _: None = Depends(_require_api_key),
    __: None = Depends(_rate_limit),
    x_project_root: str | None = Header(default=None, alias="x-project-root"),
) -> QueryResponse:
    if _is_public_mode() and not _context_return_allowed():
        raise HTTPException(
            status_code=403,
            detail="This endpoint is disabled in public mode (it can return raw context). Use /v1/synthesize.",
        )

    project_root = None if _is_public_mode() else (payload.project_root or x_project_root)
    index_override = None if _is_public_mode() else payload.index_path
    k = _public_k(payload.k) if _is_public_mode() else payload.k
    cloud_rerank = False if _is_public_mode() else payload.cloud_rerank

    index_path = _resolve_index_path(index_override, project_root)
    store = _load_index(index_path=index_path, cloud_rerank=cloud_rerank)
    response = answer_query(index=store, query=payload.question, k=k)
    return QueryResponse(
        answer=response.answer,
        mode=response.mode,
        confidence=response.confidence,
        confidence_label=response.confidence_label,
        selected_modules=response.selected_modules,
        context=response.context,
    )


@app.post("/v1/copilot-context")
def copilot_context(
    payload: QueryRequest,
    _: None = Depends(_require_api_key),
    __: None = Depends(_rate_limit),
    x_project_root: str | None = Header(default=None, alias="x-project-root"),
) -> dict[str, Any]:
    if _is_public_mode() and not _context_return_allowed():
        raise HTTPException(
            status_code=403,
            detail="This endpoint is disabled in public mode (it can return raw context). Use /v1/synthesize.",
        )

    project_root = None if _is_public_mode() else (payload.project_root or x_project_root)
    index_override = None if _is_public_mode() else payload.index_path
    k = _public_k(payload.k) if _is_public_mode() else payload.k
    cloud_rerank = False if _is_public_mode() else payload.cloud_rerank

    index_path = _resolve_index_path(index_override, project_root)
    store = _load_index(index_path=index_path, cloud_rerank=cloud_rerank)
    response = answer_query(index=store, query=payload.question, k=k)
    return {
        "mode": response.mode,
        "confidence": response.confidence,
        "confidence_label": response.confidence_label,
        "selected_modules": response.selected_modules,
        "prompt": response.prompt_template,
    }


@app.post("/v1/synthesize", response_model=SynthesizeResponse)
def synthesize(
    payload: SynthesizeRequest,
    _: None = Depends(_require_api_key),
    __: None = Depends(_rate_limit),
    x_project_root: str | None = Header(default=None, alias="x-project-root"),
) -> SynthesizeResponse:
    if not _settings.perplexity_api_key:
        raise HTTPException(
            status_code=503,
            detail="PERPLEXITY_API_KEY is not set; synthesis is unavailable.",
        )

    project_root = None if _is_public_mode() else (payload.project_root or x_project_root)
    index_override = None if _is_public_mode() else payload.index_path
    k = _public_k(payload.k) if _is_public_mode() else payload.k
    cloud_rerank = False if _is_public_mode() else payload.cloud_rerank

    index_path = _resolve_index_path(index_override, project_root)
    store = _load_index(index_path=index_path, cloud_rerank=cloud_rerank)

    retrieval = retrieve_hits(index=store, query=payload.question, k=k)
    hits = retrieval.hits
    citations = [
        Citation(
            chunk_id=h.chunk.chunk_id,
            source=h.chunk.source,
            module_id=h.chunk.module_id,
            page=h.chunk.page,
            score=float(h.score),
        )
        for h in hits
    ]

    # Build grounded context for synthesis.
    context_parts: list[str] = []
    for i, h in enumerate(hits[: min(len(hits), max(8, k))], start=1):
        label = f"[{i}] {h.chunk.source} (page {h.chunk.page if h.chunk.page else 'n/a'})"
        if h.chunk.module_id:
            label += f" | module={h.chunk.module_id}"
        label += f" | score={h.score:.3f}"
        context_parts.append(label + "\n" + h.chunk.text)
    context_blob = "\n\n---\n\n".join(context_parts) if context_parts else "(no context retrieved)"

    system = (
        "You are a synthesis engine. Use ONLY the provided context. "
        "If the context is insufficient, say so explicitly. "
        "When making claims, cite sources using bracket numbers like [1], [2] corresponding to the provided context blocks."
    )
    user = (
        f"Context blocks (authoritative):\n\n{context_blob}\n\n"
        f"Question: {payload.question}\n\n"
        "Answer using only the context blocks. Provide a clear, step-by-step explanation when appropriate."
    )

    model = (payload.model or _settings.perplexity_default_model).strip()
    try:
        answer = perplexity_chat_completions(
            api_key=_settings.perplexity_api_key,
            base_url=_settings.perplexity_base_url,
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    except PerplexityError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    conf = compute_confidence(query=payload.question, mode=retrieval.mode, hits=hits, symbolic=None)
    return SynthesizeResponse(
        answer=answer,
        mode=retrieval.mode,
        confidence=conf,
        confidence_label=label_confidence(conf),
        selected_modules=retrieval.selected_modules,
        citations=citations,
    )


@app.get("/v1/indexed-files", response_model=FilesResponse)
def indexed_files(
    index_path: str | None = None,
    project_root: str | None = None,
    _: None = Depends(_require_api_key),
    __: None = Depends(_rate_limit),
    x_project_root: str | None = Header(default=None, alias="x-project-root"),
) -> FilesResponse:
    if _is_public_mode() and not _admin_endpoints_allowed():
        raise HTTPException(status_code=403, detail="Endpoint disabled in public mode")

    if _is_public_mode():
        index_path = None
        project_root = None
    p = _resolve_index_path(index_path, project_root or x_project_root)
    import pickle

    with p.open("rb") as f:
        data = pickle.load(f)
    manifest: dict[str, str] = data.get("file_manifest", {})
    files = sorted(str(k) for k in manifest.keys())
    return FilesResponse(index_path=str(p), indexed_file_count=len(files), indexed_files=files)


@app.get("/v1/config")
def bridge_config(_: None = Depends(_require_api_key)) -> dict[str, Any]:
    if _is_public_mode() and not _admin_endpoints_allowed():
        raise HTTPException(status_code=403, detail="Endpoint disabled in public mode")
    return asdict(_settings)


@app.get("/v1/dropbox-health")
def dropbox_health(_: None = Depends(_require_api_key), __: None = Depends(_rate_limit)) -> dict[str, Any]:
    token = (os.getenv("DROPBOX_ACCESS_TOKEN") or "").strip()
    if not token:
        return {
            "connected": False,
            "reason": "DROPBOX_ACCESS_TOKEN not set",
        }

    import json
    from urllib import error as urllib_error
    from urllib import request as urllib_request

    req = urllib_request.Request(
        url="https://api.dropboxapi.com/2/users/get_current_account",
        data=b"null",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib_request.urlopen(req, timeout=10) as resp:
            status_code = int(resp.status)
            body_text = resp.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        status_code = int(exc.code)
        body_text = exc.read().decode("utf-8", errors="replace")
    except urllib_error.URLError as exc:
        return {
            "connected": False,
            "reason": f"request_error:{type(exc).__name__}",
        }

    if status_code == 200:
        data = json.loads(body_text)
        return {
            "connected": True,
            "account_id": data.get("account_id"),
            "name": (data.get("name") or {}).get("display_name"),
            "email": data.get("email"),
        }

    try:
        err: Any = json.loads(body_text)
    except Exception:
        err = body_text[:300]

    return {
        "connected": False,
        "status_code": status_code,
        "error": err,
    }

from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .config import Settings
from .indexing import IndexStore
from .orchestrator import answer_query

app = FastAPI(title="Master Brain Bridge API", version="1.0.0")
_settings = Settings.from_env()
_cache_lock = Lock()
_cache: dict[str, tuple[int, IndexStore]] = {}


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    k: int = Field(6, ge=1, le=30)
    index_path: str | None = None
    project_root: str | None = None
    cloud_rerank: bool = False


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


def _require_api_key(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    required = _settings.bridge_api_key
    if not required:
        return

    provided = (x_api_key or "").strip()
    auth_value = (authorization or "").strip()

    bearer = ""
    if auth_value.lower().startswith("bearer "):
        bearer = auth_value[7:].strip()

    if provided.lower().startswith("bearer "):
        provided = provided[7:].strip()

    if required not in {provided, bearer}:
        raise HTTPException(status_code=401, detail="Invalid API key")


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
        "default_index": _settings.bridge_default_index_path,
        "cwd": str(Path.cwd()),
    }


@app.post("/v1/query", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    _: None = Depends(_require_api_key),
    x_project_root: str | None = Header(default=None, alias="x-project-root"),
) -> QueryResponse:
    project_root = payload.project_root or x_project_root
    index_path = _resolve_index_path(payload.index_path, project_root)
    store = _load_index(index_path=index_path, cloud_rerank=payload.cloud_rerank)
    response = answer_query(index=store, query=payload.question, k=payload.k)
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
    x_project_root: str | None = Header(default=None, alias="x-project-root"),
) -> dict[str, Any]:
    project_root = payload.project_root or x_project_root
    index_path = _resolve_index_path(payload.index_path, project_root)
    store = _load_index(index_path=index_path, cloud_rerank=payload.cloud_rerank)
    response = answer_query(index=store, query=payload.question, k=payload.k)
    return {
        "mode": response.mode,
        "confidence": response.confidence,
        "confidence_label": response.confidence_label,
        "selected_modules": response.selected_modules,
        "prompt": response.prompt_template,
    }


@app.get("/v1/indexed-files", response_model=FilesResponse)
def indexed_files(
    index_path: str | None = None,
    project_root: str | None = None,
    _: None = Depends(_require_api_key),
    x_project_root: str | None = Header(default=None, alias="x-project-root"),
) -> FilesResponse:
    p = _resolve_index_path(index_path, project_root or x_project_root)
    import pickle

    with p.open("rb") as f:
        data = pickle.load(f)
    manifest: dict[str, str] = data.get("file_manifest", {})
    files = sorted(str(k) for k in manifest.keys())
    return FilesResponse(index_path=str(p), indexed_file_count=len(files), indexed_files=files)


@app.get("/v1/config")
def bridge_config(_: None = Depends(_require_api_key)) -> dict[str, Any]:
    return asdict(_settings)


@app.get("/v1/dropbox-health")
def dropbox_health(_: None = Depends(_require_api_key)) -> dict[str, Any]:
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

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import tomllib

from dotenv import load_dotenv


load_dotenv()


HARDCODED_BRIDGE_API_KEY = "master-brain-bridge-local"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if raw == "":
        return default
    return raw not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    openai_api_key: str | None
    perplexity_api_key: str | None
    openai_embed_model: str
    cloud_rerank_enabled: bool
    bridge_api_key: str | None
    bridge_host: str
    bridge_port: int
    bridge_default_index_path: str

    # Public/shared deployment safety switches.
    bridge_public_mode: bool = False
    bridge_public_max_k: int = 10
    bridge_public_allow_admin_endpoints: bool = False
    bridge_public_return_context: bool = False

    # Best-effort in-process rate limiting (recommended for public exposure).
    bridge_rate_limit_rpm: int = 60
    bridge_rate_limit_burst: int = 20

    # Perplexity synthesis defaults.
    perplexity_base_url: str = "https://api.perplexity.ai"
    perplexity_default_model: str = "sonar-pro"

    @classmethod
    def from_env(cls) -> "Settings":
        rerank_env = os.getenv("CLOUD_RERANK_ENABLED", "1").strip().lower()
        rerank_on = rerank_env not in {"0", "false", "no", "off"}
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not api_key or api_key.lower() in {"your_openai_api_key_here", "changeme", "your_api_key_here"}:
            api_key = None

        perplexity_key = (os.getenv("PERPLEXITY_API_KEY") or os.getenv("PPLX_API_KEY") or "").strip()
        if not perplexity_key or perplexity_key.lower() in {
            "your_perplexity_api_key_here",
            "changeme",
            "your_api_key_here",
            "none",
        }:
            perplexity_key = None

        bridge_key = (os.getenv("BRIDGE_API_KEY") or "").strip()
        if not bridge_key or bridge_key.lower() in {"changeme", "your_bridge_api_key_here", "none"}:
            bridge_key = HARDCODED_BRIDGE_API_KEY

        workspace_root = (os.getenv("BRIDGE_WORKSPACE_ROOT") or "").strip()
        default_index = (os.getenv("BRIDGE_DEFAULT_INDEX_PATH") or "data/master_brain_index.pkl").strip()
        if workspace_root and default_index and not Path(default_index).is_absolute():
            default_index = str((Path(workspace_root).expanduser() / default_index).as_posix())

        bridge_host = (os.getenv("BRIDGE_HOST") or "127.0.0.1").strip() or "127.0.0.1"
        try:
            bridge_port = int((os.getenv("BRIDGE_PORT") or "8787").strip())
        except ValueError:
            bridge_port = 8787

        public_mode = _env_bool("BRIDGE_PUBLIC_MODE", default=False)
        public_max_k = max(1, _env_int("BRIDGE_PUBLIC_MAX_K", default=10))
        public_allow_admin = _env_bool("BRIDGE_PUBLIC_ALLOW_ADMIN_ENDPOINTS", default=False)
        public_return_context = _env_bool("BRIDGE_PUBLIC_RETURN_CONTEXT", default=False)

        rate_rpm = max(0, _env_int("BRIDGE_RATE_LIMIT_RPM", default=60))
        rate_burst = max(0, _env_int("BRIDGE_RATE_LIMIT_BURST", default=20))

        perplexity_base_url = (os.getenv("PERPLEXITY_BASE_URL") or "https://api.perplexity.ai").strip() or "https://api.perplexity.ai"
        perplexity_default_model = (os.getenv("PERPLEXITY_MODEL") or "sonar-pro").strip() or "sonar-pro"

        return cls(
            openai_api_key=api_key,
            perplexity_api_key=perplexity_key,
            openai_embed_model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
            cloud_rerank_enabled=rerank_on,
            bridge_api_key=bridge_key,
            bridge_host=bridge_host,
            bridge_port=bridge_port,
            bridge_default_index_path=default_index,

            bridge_public_mode=public_mode,
            bridge_public_max_k=public_max_k,
            bridge_public_allow_admin_endpoints=public_allow_admin,
            bridge_public_return_context=public_return_context,

            bridge_rate_limit_rpm=rate_rpm,
            bridge_rate_limit_burst=rate_burst,

            perplexity_base_url=perplexity_base_url,
            perplexity_default_model=perplexity_default_model,
        )


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    module_id: str
    display_name: str
    paths: tuple[Path, ...]
    enabled: bool
    stage: str
    priority: int
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModuleRegistry:
    schema_version: int
    modules: tuple[ModuleSpec, ...]

    @property
    def enabled_modules(self) -> tuple[ModuleSpec, ...]:
        return tuple(m for m in sorted(self.modules, key=lambda x: x.priority) if m.enabled)


def load_module_registry(config_path: str | Path = "config/modules.toml") -> ModuleRegistry:
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Module config not found: {p}")

    with p.open("rb") as f:
        data = tomllib.load(f)

    schema_version = int(data.get("schema_version", 1))
    raw_modules = data.get("modules", {})
    modules: list[ModuleSpec] = []
    seen: set[str] = set()
    for module_id, spec in raw_modules.items():
        if module_id in seen:
            raise ValueError(f"Duplicate module id in config: {module_id}")
        seen.add(module_id)

        paths = tuple(Path(x) for x in spec.get("paths", []))
        modules.append(
            ModuleSpec(
                module_id=module_id,
                display_name=spec.get("display_name", module_id),
                paths=paths,
                enabled=bool(spec.get("enabled", True)),
                stage=str(spec.get("stage", "active")),
                priority=int(spec.get("priority", 100)),
                aliases=tuple(spec.get("aliases", [])),
            )
        )

    return ModuleRegistry(schema_version=schema_version, modules=tuple(modules))


def ensure_data_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

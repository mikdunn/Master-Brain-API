from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class InheritanceConfig:
    schema_version: int
    # child_module_id -> prereq module ids (parents)
    prereqs: dict[str, tuple[str, ...]]


class ModuleInheritanceGraph:
    """Directed prerequisite graph over module IDs.

    Edge semantics: A -> B means A is a prerequisite for B.

    Internally we store parents (prereqs) for each module.
    """

    def __init__(
        self,
        prereqs: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.parents: dict[str, tuple[str, ...]] = prereqs or {}

    def ancestors(
        self,
        module_ids: set[str],
        max_hops: int = 2,
    ) -> list[str]:
        """Return unique upstream prereq modules (excluding seeds).

        Uses BFS by hop distance.
        """

        if max_hops <= 0 or not module_ids:
            return []

        out: list[str] = []
        seen: set[str] = set(module_ids)
        q: deque[tuple[str, int]] = deque((m, 0) for m in module_ids)
        while q:
            cur, depth = q.popleft()
            if depth >= max_hops:
                continue
            for p in self.parents.get(cur, ()):  # p is prereq for cur
                if p in seen:
                    continue
                seen.add(p)
                out.append(p)
                q.append((p, depth + 1))
        return out


def load_inheritance_config(
    path: str | Path = "config/inheritance.toml",
) -> InheritanceConfig:
    p = Path(path)
    if not p.exists():
        return InheritanceConfig(schema_version=1, prereqs={})

    with p.open("rb") as f:
        data = tomllib.load(f)

    schema_version = int(data.get("schema_version", 1))
    raw_modules = data.get("modules", {})

    prereqs: dict[str, tuple[str, ...]] = {}
    for module_id, spec in raw_modules.items():
        raw = spec.get("prereqs", [])
        if raw is None:
            raw = []
        parents = tuple(str(x) for x in raw)
        parents = tuple(p for p in parents if p and p != module_id)
        prereqs[str(module_id)] = parents

    return InheritanceConfig(schema_version=schema_version, prereqs=prereqs)

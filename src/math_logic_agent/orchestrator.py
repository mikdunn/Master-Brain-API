from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import load_module_registry
from .inheritance import ModuleInheritanceGraph
from .indexing import IndexStore
from .models import RetrievedChunk
from .prompt_templates import build_prompt_template
from .symbolic import SymbolicResult, symbolic_from_query


@dataclass(slots=True)
class AgentResponse:
    mode: str
    answer: str
    context: list[str]
    prompt_template: str
    confidence: float
    confidence_label: str
    selected_modules: list[str]


MODULE_ALIASES: dict[str, tuple[str, ...]] = {
    "math_core": (
        "math",
        "algebra",
        "calculus",
        "svd",
        "linear algebra",
        "statistics",
    ),
    "physics_core": (
        "physics",
        "mechanics",
        "quantum",
        "electromagnetism",
        "thermodynamics",
    ),
    "chemistry_core": (
        "chemistry",
        "reaction",
        "molecule",
        "organic",
        "inorganic",
    ),
    "biology_core": (
        "biology",
        "cell",
        "genetics",
        "virology",
        "microbiology",
    ),
    "microscopy_core": (
        "microscopy",
        "confocal",
        "fluorescence",
        "micrograph",
    ),
    "bioinformatics_core": (
        "bioinformatics",
        "genomics",
        "sequence",
        "alignment",
        "omics",
    ),
    "imaging_core": (
        "imaging",
        "image",
        "segmentation",
        "filter",
        "computer vision",
    ),
    "cs_core": (
        "computer science",
        "algorithm",
        "data structure",
        "complexity",
        "programming",
    ),
}

ROUTING_MODULE_CONFIG_PATHS: tuple[str, ...] = (
    "config/master_brain.toml",
    "config/modules.toml",
)


def _normalized_aliases(values: tuple[str, ...] | list[str]) -> set[str]:
    return {v.strip().lower() for v in values if v and v.strip()}


def _module_id_fallback_aliases(module_id: str) -> set[str]:
    base = module_id.lower().replace("_", " ")
    aliases = {base, module_id.lower()}
    for suffix in (" core", " brain"):
        if base.endswith(suffix):
            aliases.add(base.removesuffix(suffix).strip())
    return {a for a in aliases if a}


def _registry_aliases(available: list[str]) -> dict[str, set[str]]:
    available_set = set(available)
    out: dict[str, set[str]] = {m: set() for m in available}
    for raw_path in ROUTING_MODULE_CONFIG_PATHS:
        path = Path(raw_path)
        if not path.exists():
            continue
        try:
            reg = load_module_registry(path)
        except (FileNotFoundError, ValueError):
            continue

        for module in reg.enabled_modules:
            if module.module_id not in available_set:
                continue
            out[module.module_id].update(
                _normalized_aliases(list(module.aliases))
            )
            if module.display_name:
                out[module.module_id].add(module.display_name.strip().lower())
    return out


def _alias_map(available: list[str]) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = {}
    reg_aliases = _registry_aliases(available)
    for module_id in available:
        merged = set()
        merged.update(
            _normalized_aliases(list(MODULE_ALIASES.get(module_id, ())))
        )
        merged.update(reg_aliases.get(module_id, set()))
        merged.update(_module_id_fallback_aliases(module_id))
        aliases[module_id] = merged
    return aliases


def route_modules(index: IndexStore, query: str) -> list[str]:
    available = sorted({c.module_id for c in index.chunks if c.module_id})
    if not available:
        return []

    q = query.lower()
    aliases = _alias_map(available)
    runtime_aliases = getattr(index, "module_aliases", {})
    ranked: list[tuple[str, int]] = []
    for module_id in available:
        hints = set(aliases.get(module_id, set()))
        hints.update(
            _normalized_aliases(list(runtime_aliases.get(module_id, ())))
        )
        score = sum(1 for h in hints if h in q)
        ranked.append((module_id, score))

    ranked.sort(key=lambda x: x[1], reverse=True)
    if ranked and ranked[0][1] > 0:
        return [m for m, s in ranked[:3] if s > 0]

    # fallback: prefer broad modules most likely to answer unknown queries
    if any(m.endswith("_brain") for m in available):
        priority = [
            "math_brain",
            "cs_brain",
            "physics_brain",
            "engineering_brain",
            "science_brain",
            "business_brain",
            "humanities_brain",
        ]
    else:
        priority = ["math_core", "cs_core", "physics_core", "imaging_core"]
    fallback = [m for m in priority if m in available]
    if fallback:
        return fallback[:2]
    return available[:2]


def detect_mode(query: str) -> str:
    q = query.lower()
    if any(
        k in q
        for k in (
            "prove",
            "derive",
            "solve",
            "symbolic",
            "simplify",
        )
    ):
        return "symbolic"
    if any(k in q for k in ("python", "numpy", "sympy", "code", "implement")):
        return "coding"
    if any(k in q for k in ("quiz", "practice", "exam", "flashcard")):
        return "exam"
    return "explanation"


def _build_answer(
    mode: str,
    query: str,
    context_blocks: list[str],
    symbolic: SymbolicResult | None = None,
) -> str:
    context_intro = (
        "\n\n".join(context_blocks[:3])
        if context_blocks
        else "No relevant context found."
    )
    if mode == "symbolic":
        symbolic = symbolic or symbolic_from_query(query)
        assert symbolic is not None
        suffix = (
            f"\n\nSymbolic engine ({symbolic.task}): {symbolic.output}"
            if symbolic.success
            else f"\n\nSymbolic engine: {symbolic.output}"
        )
        return (
            "Use the retrieved mathematical context below to reason "
            "step-by-step. "
            "Validate each algebraic transformation before concluding.\n\n"
            f"Context:\n{context_intro}{suffix}"
        )
    if mode == "coding":
        return (
            "Use this context to produce robust, tested "
            "Python/SymPy/Numpy code for the requested math task.\n\n"
            f"Context:\n{context_intro}"
        )
    if mode == "exam":
        return (
            "Generate exam-style Q&A based on this context: "
            "include one conceptual and one computational question.\n\n"
            f"Context:\n{context_intro}"
        )
    return (
        "Explain clearly and accurately using this context:\n\n"
        f"{context_intro}"
    )


def _confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def _score_confidence(
    query: str,
    mode: str,
    hits: list[RetrievedChunk],
    symbolic: SymbolicResult | None,
) -> float:
    if not hits:
        return 0.2

    scores = [max(0.0, min(1.0, h.score)) for h in hits]
    top = scores[0]
    mean_top = sum(scores[:3]) / min(3, len(scores))

    terms = [t for t in re.findall(r"[a-zA-Z]{3,}", query.lower())]
    if terms:
        joined = "\n".join(h.chunk.text.lower() for h in hits[:3])
        covered = sum(1 for t in set(terms) if t in joined)
        coverage = covered / max(len(set(terms)), 1)
    else:
        coverage = 0.5

    score = 0.45 * top + 0.35 * mean_top + 0.20 * coverage
    if mode == "symbolic" and symbolic is not None:
        score += 0.10 if symbolic.success else -0.10

    return max(0.0, min(1.0, score))


def _term_coverage(query: str, hits: list[RetrievedChunk]) -> float:
    terms = [t for t in re.findall(r"[a-zA-Z]{3,}", query.lower())]
    if not terms:
        return 0.5
    joined = "\n".join(h.chunk.text.lower() for h in hits[:3])
    covered = sum(1 for t in set(terms) if t in joined)
    return covered / max(len(set(terms)), 1)


def _merge_hits(
    *,
    primary: list[RetrievedChunk],
    expanded: list[RetrievedChunk],
    prereq_modules: set[str],
    k: int,
) -> list[RetrievedChunk]:
    """Merge primary + expanded hits.

    Keeps primary intent results first, then prefers prereq-module hits.
    """

    seen: set[str] = set()
    out: list[RetrievedChunk] = []

    def _add(h: RetrievedChunk) -> None:
        nonlocal out
        cid = h.chunk.chunk_id
        if cid in seen:
            return
        seen.add(cid)
        out.append(h)

    # Keep the primary intent results first.
    for h in primary:
        _add(h)
        if len(out) >= k:
            return out

    # Prefer prereq-module hits next.
    for h in expanded:
        if h.chunk.module_id in prereq_modules:
            _add(h)
            if len(out) >= k:
                return out

    # Fill remaining slots.
    for h in expanded:
        _add(h)
        if len(out) >= k:
            return out
    return out


def answer_query(index: IndexStore, query: str, k: int = 6) -> AgentResponse:
    mode = detect_mode(query)
    selected_modules = route_modules(index, query)
    allowed = set(selected_modules) if selected_modules else None

    hits = index.retriever.search(query, k=k, allowed_modules=allowed)

    # Adaptive inheritance expansion: if we have a module restriction and the
    # retrieved context doesn't cover enough of the query, expand upstream
    # prerequisites (bounded) and merge results.
    if allowed and hits and index.module_inheritance:
        coverage = _term_coverage(query, hits)
        base_conf = _score_confidence(
            query=query,
            mode=mode,
            hits=hits,
            symbolic=None,
        )
        if base_conf < 0.55 or coverage < 0.35:
            graph = ModuleInheritanceGraph(
                prereqs={
                    k: tuple(v)
                    for k, v in index.module_inheritance.items()
                }
            )
            prereq_list = graph.ancestors(set(selected_modules), max_hops=4)
            available = {c.module_id for c in index.chunks if c.module_id}
            prereq_list = [m for m in prereq_list if m in available]
            if prereq_list:
                expanded_modules = list(
                    dict.fromkeys(selected_modules + prereq_list)
                )
                expanded_allowed = set(expanded_modules)
                expanded_hits = index.retriever.search(
                    query,
                    k=max(k * 2, 8),
                    allowed_modules=expanded_allowed,
                )
                prereq_set = set(prereq_list)
                hits = _merge_hits(
                    primary=hits,
                    expanded=expanded_hits,
                    prereq_modules=prereq_set,
                    k=k,
                )
                selected_modules = expanded_modules
                allowed = expanded_allowed

    if not hits:
        hits = index.retriever.search(query, k=k)
    blocks = [
        (
            f"[{h.score:.3f}] {h.chunk.source} "
            f"(page {h.chunk.page if h.chunk.page else 'n/a'})\n"
            f"{h.chunk.text}"
        )
        for h in hits
    ]
    symbolic = symbolic_from_query(query) if mode == "symbolic" else None
    answer = _build_answer(mode, query, blocks, symbolic=symbolic)
    prompt_template = build_prompt_template(
        mode=mode,
        query=query,
        context_blocks=blocks,
    )
    confidence = _score_confidence(
        query=query,
        mode=mode,
        hits=hits,
        symbolic=symbolic,
    )
    return AgentResponse(
        mode=mode,
        answer=answer,
        context=blocks,
        prompt_template=prompt_template,
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        selected_modules=selected_modules,
    )

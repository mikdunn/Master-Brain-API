from __future__ import annotations

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .embeddings import OpenAIEmbedder
from .models import DocumentChunk, RetrievedChunk


QUERY_ALIASES: dict[str, str] = {
    "svd": "singular value decomposition",
    "pca": "principal component analysis",
    "pinv": "pseudoinverse",

    # Tensor / multilinear algebra shorthands.
    "cp": "cp decomposition",
    "tt": "tensor train",
    "tucker": "tucker decomposition",
}


REGION_HINTS: dict[str, tuple[str, ...]] = {
    "europe": (
        "europe",
        "european",
        "france",
        "germany",
        "italy",
        "britain",
        "england",
        "rome",
        "greek",
    ),
    "middle_east": (
        "middle east",
        "arab",
        "persia",
        "ottoman",
        "mesopotamia",
    ),
    "east_asia": ("east asia", "china", "japan", "korea"),
    "south_asia": ("south asia", "india", "indian"),
    "africa": ("africa", "african", "ethiopia", "egypt"),
    "americas": (
        "america",
        "american",
        "united states",
        "latin america",
        "canada",
        "mexico",
    ),
}

TRADITION_HINTS: dict[str, tuple[str, ...]] = {
    "classical": ("classical", "antiquity", "greco-roman"),
    "enlightenment": ("enlightenment",),
    "romanticism": ("romantic", "romanticism"),
    "modernism": ("modernism", "modernist"),
    "postmodernism": ("postmodern", "post-structural"),
    "marxism": ("marx", "marxist", "historical materialism"),
    "liberalism": ("liberal", "liberalism"),
}

SOURCE_TYPE_HINTS: dict[str, tuple[str, ...]] = {
    "primary": ("primary source", "letter", "diary", "speech", "manuscript", "treatise"),
    "scholarly": ("article", "journal", "paper", "peer-reviewed"),
    "historical": ("historical", "chronicle", "timeline", "archive"),
    "literary": ("poem", "novel", "play", "narrative", "stanza"),
}


def expand_query_aliases(query: str) -> str:
    q = query
    lower = query.lower()
    for short, expanded in QUERY_ALIASES.items():
        if short in lower:
            q = f"{q} {expanded}"
    return q


THEOREM_QUERY_HINTS: dict[str, tuple[str, ...]] = {
    "definition": ("definition", "define", "what is"),
    "theorem": ("theorem", "result", "statement"),
    "lemma": ("lemma",),
    "proof": ("proof", "prove", "show that", "derive"),
    "example": ("example", "illustrate"),
    "exercise": ("exercise", "practice", "problem", "quiz", "exam"),
}

DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    "svd": ("svd", "singular value", "sigma"),
    "eigen": ("eigen", "eigenvalue", "eigenvector"),
    "calculus": ("derivative", "integral", "gradient", "hessian"),

    "tensor": (
        "tensor",
        "tensors",
        "multilinear",
        "kronecker",
        "khatri-rao",
        "outer product",
        "cp decomposition",
        "tucker",
        "tensor train",
    ),
}


def _query_features(query: str) -> set[str]:
    q = query.lower()
    feats: set[str] = set()
    for tag, hints in THEOREM_QUERY_HINTS.items():
        if any(h in q for h in hints):
            feats.add(tag)
    for tag, hints in DOMAIN_HINTS.items():
        if any(h in q for h in hints):
            feats.add(tag)
    if re.search(r"\bsolve|simplify|integrate|differentiate|diff\b", q):
        feats.add("exercise")
    return feats


def _tag_boost(features: set[str], chunk: DocumentChunk) -> float:
    if not features or not chunk.tags:
        return 0.0
    overlap = features.intersection(set(chunk.tags))
    if not overlap:
        return 0.0
    return 0.10 + 0.08 * min(len(overlap), 3)


def _query_context_hints(query: str) -> dict[str, set[str] | list[int]]:
    q = query.lower()
    years = sorted(
        {
            int(y)
            for y in re.findall(r"\b(1[0-9]{3}|20[0-9]{2}|[5-9][0-9]{2})\b", q)
        }
    )

    regions: set[str] = set()
    for tag, hints in REGION_HINTS.items():
        if any(h in q for h in hints):
            regions.add(tag)

    traditions: set[str] = set()
    for tag, hints in TRADITION_HINTS.items():
        if any(h in q for h in hints):
            traditions.add(tag)

    source_types: set[str] = set()
    for tag, hints in SOURCE_TYPE_HINTS.items():
        if any(h in q for h in hints):
            source_types.add(tag)

    return {
        "years": years,
        "regions": regions,
        "traditions": traditions,
        "source_types": source_types,
    }


def _context_boost(hints: dict[str, set[str] | list[int]], chunk: DocumentChunk) -> float:
    meta = chunk.metadata if isinstance(chunk.metadata, dict) else {}
    ctx = meta.get("context", {})
    if not isinstance(ctx, dict):
        return 0.0

    score = 0.0

    years_obj = hints.get("years", [])
    years = years_obj if isinstance(years_obj, list) else []
    if years:
        start = ctx.get("period_start")
        end = ctx.get("period_end")
        if isinstance(start, int) and isinstance(end, int):
            if any(start <= y <= end for y in years):
                score += 0.12
        elif isinstance(start, int):
            if any(y >= start for y in years):
                score += 0.08
        elif isinstance(end, int):
            if any(y <= end for y in years):
                score += 0.08

    regions_obj = hints.get("regions", set())
    regions = regions_obj if isinstance(regions_obj, set) else set()
    region = ctx.get("region")
    if regions and isinstance(region, str) and region in regions:
        score += 0.08

    traditions_obj = hints.get("traditions", set())
    traditions = traditions_obj if isinstance(traditions_obj, set) else set()
    tradition = ctx.get("tradition")
    if traditions and isinstance(tradition, str) and tradition in traditions:
        score += 0.08

    source_types_obj = hints.get("source_types", set())
    source_types = source_types_obj if isinstance(source_types_obj, set) else set()
    source_type = ctx.get("source_type")
    if source_types and isinstance(source_type, str) and source_type in source_types:
        score += 0.08

    return min(score, 0.25)


class HybridRetriever:
    def __init__(
        self,
        chunks: list[DocumentChunk],
        embedder: OpenAIEmbedder | None = None,
    ) -> None:
        if not chunks:
            raise ValueError("Cannot initialize retriever with empty chunks.")
        self.chunks = chunks
        self.embedder = embedder

        corpus = [c.text for c in chunks]
        self.lexical = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        self.lexical_matrix = self.lexical.fit_transform(corpus)

        self.semantic = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=1,
        )
        self.semantic_matrix = self.semantic.fit_transform(corpus)

    def _rerank_with_embeddings(
        self,
        query: str,
        idxs: np.ndarray,
        base_scores: np.ndarray,
    ) -> np.ndarray:
        if self.embedder is None:
            return idxs

        query_vecs = self.embedder.get_embeddings([query])
        if query_vecs is None or query_vecs.size == 0:
            return idxs
        candidate_texts = [self.chunks[int(i)].text for i in idxs]
        cand_vecs = self.embedder.get_embeddings(candidate_texts)
        if cand_vecs is None or cand_vecs.size == 0:
            return idxs

        q = query_vecs[0]
        q_norm = np.linalg.norm(q) + 1e-9
        c_norm = np.linalg.norm(cand_vecs, axis=1) + 1e-9
        cosine = (cand_vecs @ q) / (c_norm * q_norm)

        cosine = (cosine - cosine.min()) / (cosine.max() - cosine.min() + 1e-9)
        base = base_scores[idxs]
        blend = 0.55 * base + 0.45 * cosine
        order = np.argsort(-blend)
        return idxs[order]

    def search(
        self,
        query: str,
        k: int = 6,
        allowed_modules: set[str] | None = None,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            return []

        query = expand_query_aliases(query)
        features = _query_features(query)
        context_hints = _query_context_hints(query)

        lq = self.lexical.transform([query])
        sq = self.semantic.transform([query])

        lex_scores = (self.lexical_matrix @ lq.T).toarray().ravel()
        sem_scores = (self.semantic_matrix @ sq.T).toarray().ravel()

        if lex_scores.max(initial=0) > 0:
            lex_scores = lex_scores / (lex_scores.max() + 1e-9)
        if sem_scores.max(initial=0) > 0:
            sem_scores = sem_scores / (sem_scores.max() + 1e-9)

        combo = 0.6 * lex_scores + 0.4 * sem_scores
        if features:
            boosts = np.asarray(
                [_tag_boost(features, c) for c in self.chunks],
                dtype=float,
            )
            combo = np.clip(combo + boosts, 0.0, 1.5)

        has_context_hints = any(
            bool(context_hints.get(k))
            for k in ("years", "regions", "traditions", "source_types")
        )
        if has_context_hints:
            ctx_boosts = np.asarray(
                [_context_boost(context_hints, c) for c in self.chunks],
                dtype=float,
            )
            combo = np.clip(combo + ctx_boosts, 0.0, 1.8)

        if allowed_modules:
            mask = np.asarray(
                [
                    1.0 if (c.module_id in allowed_modules) else 0.0
                    for c in self.chunks
                ],
                dtype=float,
            )
            combo = combo * mask

        candidate_k = min(len(combo), max(20, k * 4))
        idxs = np.argsort(-combo)[:candidate_k]
        idxs = self._rerank_with_embeddings(query, idxs, combo)[:k]

        out: list[RetrievedChunk] = []
        for idx in idxs:
            score = float(combo[idx])
            if score <= 0:
                continue
            channel = "hybrid+r" if self.embedder is not None else "hybrid"
            out.append(
                RetrievedChunk(
                    chunk=self.chunks[int(idx)],
                    score=score,
                    channel=channel,
                )
            )
        if out:
            return out

        if allowed_modules:
            return []

        # Low-signal fallback: return top candidates even when scores are flat.
        for idx in idxs:
            out.append(
                RetrievedChunk(
                    chunk=self.chunks[int(idx)],
                    score=float(combo[idx]),
                    channel="fallback",
                )
            )
        return out

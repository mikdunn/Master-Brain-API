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


class HybridRetriever:
    def __init__(self, chunks: list[DocumentChunk], embedder: OpenAIEmbedder | None = None) -> None:
        if not chunks:
            raise ValueError("Cannot initialize retriever with empty chunks.")
        self.chunks = chunks
        self.embedder = embedder

        corpus = [c.text for c in chunks]
        self.lexical = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        self.lexical_matrix = self.lexical.fit_transform(corpus)

        self.semantic = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)
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

    def search(self, query: str, k: int = 6, allowed_modules: set[str] | None = None) -> list[RetrievedChunk]:
        if not query.strip():
            return []

        query = expand_query_aliases(query)
        features = _query_features(query)

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
            boosts = np.asarray([_tag_boost(features, c) for c in self.chunks], dtype=float)
            combo = np.clip(combo + boosts, 0.0, 1.5)

        if allowed_modules:
            mask = np.asarray(
                [1.0 if (c.module_id in allowed_modules) else 0.0 for c in self.chunks],
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
            out.append(RetrievedChunk(chunk=self.chunks[int(idx)], score=score, channel=channel))
        if out:
            return out

        if allowed_modules:
            return []

        # Low-signal fallback: return top candidates even when scores are flat.
        for idx in idxs:
            out.append(RetrievedChunk(chunk=self.chunks[int(idx)], score=float(combo[idx]), channel="fallback"))
        return out

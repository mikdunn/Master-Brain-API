from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

import numpy as np
from openai import OpenAI

from .config import Settings


class OpenAIEmbedder:
    def __init__(self, settings: Settings, cache_path: str | Path = "data/embedding_cache.pkl") -> None:
        self.settings = settings
        self.enabled = bool(settings.openai_api_key)
        self.model = settings.openai_embed_model
        self.client = OpenAI(api_key=settings.openai_api_key) if self.enabled else None
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache: dict[str, list[float]] = self._load_cache()

    def _load_cache(self) -> dict[str, list[float]]:
        if not self.cache_path.exists():
            return {}
        try:
            with self.cache_path.open("rb") as f:
                data = pickle.load(f)
            if isinstance(data, dict):
                return data
            return {}
        except Exception:
            return {}

    def _save_cache(self) -> None:
        with self.cache_path.open("wb") as f:
            pickle.dump(self.cache, f)

    def _key(self, text: str) -> str:
        digest = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()
        return f"{self.model}:{digest}"

    def get_embeddings(self, texts: list[str]) -> np.ndarray | None:
        if not self.enabled or self.client is None:
            return None
        if not texts:
            return np.zeros((0, 0), dtype=float)

        vectors: list[list[float] | None] = [None] * len(texts)
        misses: list[tuple[int, str]] = []

        for i, text in enumerate(texts):
            key = self._key(text)
            if key in self.cache:
                vectors[i] = self.cache[key]
            else:
                misses.append((i, text))

        if misses:
            batch_texts = [text for _, text in misses]
            try:
                resp = self.client.embeddings.create(model=self.model, input=batch_texts)
                for (idx, text), row in zip(misses, resp.data, strict=True):
                    vec = list(row.embedding)
                    vectors[idx] = vec
                    self.cache[self._key(text)] = vec
                self._save_cache()
            except Exception:
                return None

        final = [v for v in vectors if v is not None]
        if len(final) != len(texts):
            return None
        return np.asarray(final, dtype=float)

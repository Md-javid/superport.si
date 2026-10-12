"""Embedders turn text into vectors so similar meanings land close together.

GeminiEmbedder gives real semantic search. HashEmbedder is a free, offline fallback: it matches words, not meaning,
and is always labelled as such. Vectors from different embedders are never compared (each chunk records its embedder).
"""
import hashlib
import math
import re
from abc import ABC, abstractmethod

from app.core.config import get_settings
from app.intelligence import gemini_client, gemini_ready

_STOP = set("a an the of to in on for and or is are was were be by with at as from this that it its into per".split())


def normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class Embedder(ABC):
    name: str
    dim: int
    semantic: bool

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


class HashEmbedder(Embedder):
    semantic = False

    def __init__(self, dim: int = 768):
        self.dim, self.name = dim, f"local-hash:{dim}"

    def _vec(self, text: str) -> list[float]:
        toks = [t for t in re.findall(r"[a-z0-9]{2,}", text.lower()) if t not in _STOP]
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        counts: dict[str, int] = {}
        for f in feats:
            counts[f] = counts.get(f, 0) + 1
        v = [0.0] * self.dim
        for f, c in counts.items():
            h = int(hashlib.sha1(f.encode()).hexdigest()[:12], 16)
            v[h % self.dim] += (1 if (h >> 40) & 1 else -1) * (1 + math.log(c))
        return normalize(v)

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class GeminiEmbedder(Embedder):
    semantic = True

    def __init__(self, dim: int):
        self.dim = dim
        self.name = f"gemini:{gemini_client.resolve_embedding_model()}:{dim}"

    def embed_documents(self, texts):
        vecs, _ = gemini_client.embed(texts, task="RETRIEVAL_DOCUMENT", dim=self.dim)
        return [normalize(v) for v in vecs]

    def embed_query(self, text):
        vecs, _ = gemini_client.embed([text], task="RETRIEVAL_QUERY", dim=self.dim)
        return normalize(vecs[0])


def get_embedder() -> Embedder:
    dim = get_settings().embedding_dim
    return GeminiEmbedder(dim) if gemini_ready() else HashEmbedder(dim)

"""Embedding helpers and the deterministic local embedder.

`HashingEmbedder` is a feature-hashing bag-of-words model: canonical skills, stemmed unigrams and
bigrams are hashed into a fixed-size signed vector and L2-normalised. It needs no network or
model weights, is fully deterministic (great for tests) and captures lexical/skill overlap well
enough for local development. Real deployments can switch EMBEDDING_PROVIDER to Gemini/Bedrock.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from itertools import pairwise

from careeros.db.base import EMBEDDING_DIM
from careeros.intelligence.skills import canonical_key, extract_skill_names

_WORD = re.compile(r"[a-z0-9][a-z0-9+#]*(?:[.\-][a-z0-9+#]+)*")
_STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been before being
    below between both but by can could did do does doing down during each few for from further had
    has have having he her here hers herself him himself his how i if in into is it its itself just
    me more most my myself no nor not now of off on once only or other our ours ourselves out over
    own same she should so some such than that the their theirs them themselves then there these
    they this those through to too under until up very was we were what when where which while who
    whom why will with would you your yours yourself yourselves etc via per within across using
    use used work working including include includes strong good great ability able experience
    experienced years year plus preferred required requirements responsibilities""".split()
)


def l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _stem(word: str) -> str:
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ers", "er", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


class HashingEmbedder:
    model = "local-hashing-v1"
    dimensions = EMBEDDING_DIM
    # Typical cosine range for related vs unrelated texts under this model.
    _floor = 0.04
    _ceiling = 0.32

    def __init__(self, dimensions: int = EMBEDDING_DIM) -> None:
        self.dimensions = dimensions

    def _features(self, text: str) -> Counter[str]:
        features: Counter[str] = Counter()
        for skill in extract_skill_names(text):
            features[f"skill:{canonical_key(skill)}"] += 3
        words = [
            _stem(w.strip(".-"))
            for w in _WORD.findall(text.lower())
            if w not in _STOPWORDS and len(w) > 1
        ]
        for word in words:
            features[f"w:{word}"] += 1
        for first, second in pairwise(words):
            features[f"b:{first}_{second}"] += 1
        return features

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for feature, count in self._features(text).items():
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            weight = 1.0 + math.log(count)
            if feature.startswith("b:"):
                weight *= 0.6
            vector[index] += sign * weight
        return l2_normalize(vector)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self.embed(text)

    def calibrate(self, cosine_similarity: float) -> float:
        return _clip((cosine_similarity - self._floor) / (self._ceiling - self._floor))


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


class CalibratedRange:
    """Linear calibration used by remote embedders (floor/ceiling tuned per model family)."""

    def __init__(self, floor: float, ceiling: float) -> None:
        self.floor = floor
        self.ceiling = ceiling

    def __call__(self, cosine: float) -> float:
        return _clip((cosine - self.floor) / (self.ceiling - self.floor))

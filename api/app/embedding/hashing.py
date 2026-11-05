"""hashing-bow-768: a deterministic, offline embedder for CI (architecture 5.3).

Cosine similarity tracks shared words. The api keeps an identical copy (AD-09); the golden
prefix in indexer/tests/test_embed_hashing.py is the parity check.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from hashlib import blake2b

MODEL = "hashing-bow-768"
DIM = 768
PREFIX = "search_document: "
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an and are as at be by for from has have in is it its of on or that the to was were will with".split())


def embed_one(text: str) -> list[float]:
    if text.startswith(PREFIX):
        text = text[len(PREFIX):]
    tf = Counter(t for t in _TOKEN.findall(text.lower()) if t not in _STOP)
    vec = [0.0] * DIM
    for token, n in tf.items():
        h = int.from_bytes(blake2b(token.encode(), digest_size=8).digest(), "big")
        vec[h % DIM] += (1.0 if h >> 63 else -1.0) * (1.0 + math.log(n))
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec  # empty text stays the zero vector


def embed_hashing(texts: list[str]) -> list[list[float]]:
    return [embed_one(t) for t in texts]

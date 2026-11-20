"""Metric functions of the three levels (architecture-a3 6.2 to 6.4). Pure; no network."""

from __future__ import annotations

import math
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_eval import section_matches  # noqa: E402  (A02's matching rule, AD-22)


def matches(rel: dict, got: dict) -> bool:
    return rel["source"] == got["source"] and section_matches(rel["section"], got["section"])


def recall_at_k(relevant: list[dict], retrieved: list[dict], k: int) -> float | None:
    if not relevant:
        return None
    top = retrieved[:k]
    return sum(any(matches(r, g) for g in top) for r in relevant) / len(relevant)


def reciprocal_rank(relevant: list[dict], retrieved: list[dict], k: int = 5) -> float | None:
    if not relevant:
        return None
    for i, g in enumerate(retrieved[:k], 1):
        if any(matches(r, g) for r in relevant):
            return 1.0 / i
    return 0.0


def ndcg_at_k(relevant: list[dict], retrieved: list[dict], k: int = 5) -> float | None:
    """Binary gain; a relevant pair gains once, at its first match. IDCG puts min(|R|, k) gains on top."""
    if not relevant:
        return None
    seen: set[int] = set()
    dcg = 0.0
    for i, g in enumerate(retrieved[:k], 1):
        for j, r in enumerate(relevant):
            if j not in seen and matches(r, g):
                seen.add(j)
                dcg += 1.0 / math.log2(i + 1)
                break
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / idcg


def mean(values: list[float | None]) -> float | None:
    v = [x for x in values if x is not None]
    return sum(v) / len(v) if v else None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[max(0, math.ceil(p * len(s)) - 1)]


def add_typos(text: str, seed: int, rate: float = 1 / 8) -> str:
    """Seeded typos: about one edit per 1/rate words (swap, drop, duplicate, replace). Same seed, same output."""
    rng = random.Random(seed)
    out = []
    for w in text.split():
        if len(w) > 3 and rng.random() < rate:
            i = rng.randrange(1, len(w) - 1)
            kind = rng.choice(("swap", "drop", "dup", "replace"))
            if kind == "swap":
                w = w[:i] + w[i + 1] + w[i] + w[i + 2:]
            elif kind == "drop":
                w = w[:i] + w[i + 1:]
            elif kind == "dup":
                w = w[:i] + w[i] + w[i:]
            else:
                w = w[:i] + rng.choice("abcdefghijklmnopqrstuvwxyz") + w[i + 1:]
        out.append(w)
    return " ".join(out)


_STOP = set("the a an and or of to in on for is are was were be been by with as at it its this that these those "
            "from which who whom what when where how not no may must can will shall should would could has have had "
            "than then there their they them he she his her you your we our us do does did if any all each per".split())
_TOKEN = re.compile(r"[a-z0-9][a-z0-9.,%/-]*[a-z0-9%]|[a-z0-9]")


def content_tokens(text: str) -> set[str]:
    return {t.strip(".,") for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t.strip(".,")) > 1}


def support_overlap(answer: str, context: str) -> float:
    """Share of the answer's content tokens found in the cited context (deterministic faithfulness proxy)."""
    a = content_tokens(answer)
    return len(a & content_tokens(context)) / len(a) if a else 0.0

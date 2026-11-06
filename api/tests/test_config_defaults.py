"""The shipped numbers (phase 12, AC-9). They are the ConfigMap values handed to Ahmad in H-7."""

from __future__ import annotations

import pytest

from app.config import Settings, get_settings


def test_shipped_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("RELEVANCE_FLOOR", "TOP_K", "CACHE_THRESHOLD"):
        monkeypatch.delenv(name, raising=False)
    s = get_settings()
    assert (s.relevance_floor, s.top_k, s.cache_threshold) == (0.70, 5, 0.96)
    assert Settings().relevance_floor == 0.70

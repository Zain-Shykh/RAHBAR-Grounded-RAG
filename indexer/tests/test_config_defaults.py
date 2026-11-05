"""The shipped chunk configuration (phase 12, AC-9): 400 words, 50 overlap, as in the ConfigMap."""

from __future__ import annotations

import pytest

from pipeline.config import get_settings


def test_shipped_chunking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHUNK_SIZE", raising=False)
    monkeypatch.delenv("CHUNK_OVERLAP", raising=False)
    s = get_settings()
    assert (s.chunk_size, s.chunk_overlap) == (400, 50)

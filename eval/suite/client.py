"""HTTP client for the suite: the API under test is reached through its Service or Ingress only."""

from __future__ import annotations

import time

import httpx


class Api:
    def __init__(self, base: str, host: str | None = None, timeout: float = 300.0) -> None:
        self.base = base.rstrip("/")
        self.c = httpx.Client(timeout=timeout, headers={"Host": host} if host else {})

    def ready(self) -> dict:
        r = self.c.get(f"{self.base}/readyz")
        r.raise_for_status()
        return r.json()

    def retrieve(self, question: str, k: int = 5) -> dict:
        r = self.c.post(f"{self.base}/api/retrieve", json={"question": question, "k": k})
        r.raise_for_status()
        return r.json()

    def ask(self, question: str) -> tuple[dict, float]:
        """(response with _meta headers, wall seconds). The cache is bypassed so runs are comparable."""
        t = time.perf_counter()
        r = self.c.post(f"{self.base}/api/ask", json={"question": question}, headers={"X-Cache-Bypass": "1"})
        r.raise_for_status()
        data = r.json()
        data["_meta"] = {"outcome": r.headers.get("X-Outcome"), "cache": r.headers.get("X-Cache")}
        return data, time.perf_counter() - t

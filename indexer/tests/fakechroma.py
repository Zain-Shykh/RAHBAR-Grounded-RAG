"""In-memory stand-in for the Chroma client calls the indexer uses (no server needed)."""

from __future__ import annotations

from typing import Any


class FakeCollection:
    def __init__(self, client: FakeClient, name: str, metadata: dict[str, Any]) -> None:
        self.client, self.name, self.metadata = client, name, dict(metadata)
        self.ids: list[str] = []
        self.docs: list[str] = []
        self.metas: list[dict[str, Any]] = []
        self.embs: list[list[float]] = []
        self.add_sizes: list[int] = []

    def add(self, ids: list[str], documents: list[str], embeddings: list[list[float]],
            metadatas: list[dict[str, Any]]) -> None:
        if self.client.fail_add_on_call is not None and len(self.add_sizes) + 1 == self.client.fail_add_on_call:
            raise RuntimeError("boom")
        self.add_sizes.append(len(ids))
        self.ids += ids
        self.docs += documents
        self.embs += embeddings
        self.metas += metadatas

    def count(self) -> int:
        return len(self.ids) - self.client.lose_records

    def modify(self, name: str) -> None:
        self.client.cols[name] = self.client.cols.pop(self.name)
        self.name = name


class FakeClient:
    def __init__(self) -> None:
        self.cols: dict[str, FakeCollection] = {}
        self.fail_add_on_call: int | None = None
        self.lose_records = 0
        self.calls: list[str] = []

    def create_collection(self, name: str, metadata: dict[str, Any]) -> FakeCollection:
        if name in self.cols:
            raise ValueError("exists")
        self.calls.append(f"create {name}")
        self.cols[name] = FakeCollection(self, name, metadata)
        return self.cols[name]

    def get_collection(self, name: str) -> FakeCollection:
        return self.cols[name]

    def delete_collection(self, name: str) -> None:
        self.calls.append(f"delete {name}")
        del self.cols[name]

    def heartbeat(self) -> int:
        return 1

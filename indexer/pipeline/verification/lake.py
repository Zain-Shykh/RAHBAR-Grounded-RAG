"""The data lake on its volume (architecture-a3 5.1): quarantine, archive, reports, registry.

Only the indexer Job writes here (I-18). `root` is LAKE_DIR; tests use a temp directory.
"""

from __future__ import annotations

import json
import secrets
import shutil
import time
from pathlib import Path


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{secrets.token_hex(3)}"


class Lake:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def quarantine(self, run_id: str, name: str, src: Path | None, reasons: list[str], sha256: str | None) -> Path:
        d = self.root / "quarantine" / run_id
        d.mkdir(parents=True, exist_ok=True)
        if src is not None and src.is_file():
            shutil.copyfile(src, d / name)
        (d / f"{name}.reason.json").write_text(json.dumps(
            {"source": name, "sha256": sha256, "run_id": run_id, "reasons": reasons}, indent=2) + "\n")
        return d / name

    def archive(self, name: str, src: Path, sha256: str) -> Path:
        d = self.root / "archive" / name / sha256[:12]
        d.mkdir(parents=True, exist_ok=True)
        if not (d / name).exists():
            shutil.copyfile(src, d / name)
        return d / name

    def write_report(self, run_id: str, filename: str, data: dict) -> Path:
        d = self.root / "reports" / run_id
        d.mkdir(parents=True, exist_ok=True)
        p = d / filename
        p.write_text(json.dumps(data, indent=2) + "\n")
        return p

    def read_report(self, run_id: str, filename: str = "verification.json") -> dict:
        return json.loads((self.root / "reports" / run_id / filename).read_text())

    def latest_run(self) -> str | None:
        d = self.root / "reports"
        runs = sorted(p.name for p in d.iterdir()) if d.is_dir() else []
        return runs[-1] if runs else None

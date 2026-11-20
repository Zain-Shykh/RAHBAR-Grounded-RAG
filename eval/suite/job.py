"""The eval Job's entry point (R3-F2-2): run the suite, then the gate, and exit with the gate's status.

Environment: API_URL, RUN_LABEL, SUBSET, RESULTS_DIR (volume), BASELINE (a result file), GATE_CONFIG (the mounted
ConfigMap), SET_BASELINE=true (first run: the result becomes the baseline and no gate is applied).
Exit 0 gate passed, 1 gate failed, 2 the suite or the files could not be used.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from . import gate
from .run_suite import HERE, run_suite


def main() -> int:
    out = Path(os.environ.get("RESULTS_DIR", "/results"))
    label = os.environ.get("RUN_LABEL", "run")
    try:
        result = run_suite(os.environ.get("API_URL", "http://api"), label, os.environ.get("SUBSET", "A"),
                           int(os.environ.get("SEED", "1234")), HERE / "golden.jsonl", None, out)
    except Exception as exc:
        print(f"SUITE FAILED: {exc!r}", file=sys.stderr)
        return 2
    baseline = Path(os.environ.get("BASELINE", out / "baseline.json"))
    if os.environ.get("SET_BASELINE", "false").lower() == "true":
        shutil.copyfile(result, baseline)
        print(f"baseline written: {baseline}")
        return 0
    try:
        base = json.loads(baseline.read_text())
        cand = json.loads(result.read_text())
        cfg = gate.yaml.safe_load(Path(os.environ.get("GATE_CONFIG", "/gate/gate.yaml")).read_text())
    except (OSError, ValueError) as exc:
        print(f"GATE ERROR: {exc!r}", file=sys.stderr)
        return 2
    code, lines = gate.run(base, cand, cfg)
    print(f"baseline {baseline}\ncandidate {result}")
    print("\n".join(lines))
    (out / f"gate-{label}.txt").write_text("\n".join(lines) + f"\nexit {code}\n")
    return code


if __name__ == "__main__":
    sys.exit(main())

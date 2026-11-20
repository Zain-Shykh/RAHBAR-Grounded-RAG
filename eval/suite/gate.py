"""The release gate (R3-C2-*): thresholds from one config file, exit 0 (pass), 1 (fail), 2 (bad input).

    python -m eval.suite.gate --baseline base.json --candidate cand.json [--config eval/gate.yaml]

No limit is written in this file (I-24). On the cluster the config is the ConfigMap `rahbar-gate` mounted as a file.
Each rule: {metric: dotted.path.in.result.json, op: <op>, value: number}. Ops:
  at_least / at_most                      absolute limit on the candidate
  not_below_baseline_by                   candidate >= baseline - value   (value in metric units, e.g. 0.02 = 2 points)
  not_below_baseline                      candidate >= baseline
  not_above_baseline_by_pct               candidate <= baseline * (1 + value / 100)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]


def dig(d: dict, path: str) -> float | None:
    for part in path.split("."):
        if not isinstance(d, dict) or part not in d:
            return None
        d = d[part]
    return d  # type: ignore[return-value]


def check(rule: dict, base: dict, cand: dict) -> tuple[bool, str]:
    metric, op, val = rule["metric"], rule["op"], float(rule.get("value", 0))
    c, b = dig(cand, metric), dig(base, metric)
    if c is None:
        return False, f"{metric}: missing in the candidate result"
    if op in ("not_below_baseline_by", "not_below_baseline", "not_above_baseline_by_pct") and b is None:
        return False, f"{metric}: missing in the baseline result"
    if op == "at_least":
        ok, lim = c >= val - 1e-12, f">= {val}"
    elif op == "at_most":
        ok, lim = c <= val + 1e-12, f"<= {val}"
    elif op == "not_below_baseline_by":
        ok, lim = c >= b - val - 1e-12, f">= baseline {b:.4f} - {val}"
    elif op == "not_below_baseline":
        ok, lim = c >= b - 1e-12, f">= baseline {b:.4f}"
    elif op == "not_above_baseline_by_pct":
        ok, lim = c <= b * (1 + val / 100) + 1e-12, f"<= baseline {b:.4f} + {val}%"
    else:
        raise ValueError(f"unknown op {op!r}")
    return ok, f"{metric}: candidate {c:.4f}, limit {lim}"


def run(baseline: dict, candidate: dict, config: dict) -> tuple[int, list[str]]:
    lines, failed = [], 0
    for rule in config["rules"]:
        ok, msg = check(rule, baseline, candidate)
        failed += not ok
        why = f"   ({rule['why']})" if rule.get("why") else ""
        lines.append(f"{'PASS' if ok else 'FAIL'}  {msg}{why}")
    lines.append("GATE " + ("FAILED" if failed else "PASSED") + f": {len(config['rules']) - failed} of {len(config['rules'])} rules pass")
    return (1 if failed else 0), lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=os.environ.get("BASELINE"))
    ap.add_argument("--candidate", default=os.environ.get("CANDIDATE"))
    ap.add_argument("--config", default=os.environ.get("GATE_CONFIG", str(HERE / "gate.yaml")))
    a = ap.parse_args()
    try:
        base = json.loads(Path(a.baseline).read_text())
        cand = json.loads(Path(a.candidate).read_text())
        cfg = yaml.safe_load(Path(a.config).read_text())
        code, lines = run(base, cand, cfg)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"GATE ERROR: {exc!r}", file=sys.stderr)
        return 2
    print(f"gate config {a.config}\nbaseline  {a.baseline}\ncandidate {a.candidate}")
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())

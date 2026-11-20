"""Release gate (phase R7: AC1, AC2, AC6)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml
from suite import gate
from suite.compare import table

BASE = {"meta": {"label": "b"}, "component": {"clean": {"recall_at_5": 0.9, "mrr": 0.8}},
        "e2e": {"faithfulness_supported_rate": 0.8, "abstention_correctness": 1.0, "citation_validity": 1.0, "latency_p95_s": 60}}
CFG = yaml.safe_load((Path(gate.HERE) / "gate.yaml").read_text())


def cand(**over):
    c = json.loads(json.dumps(BASE))
    for path, v in over.items():
        d = c
        *head, last = path.split(".")
        for h in head:
            d = d[h]
        d[last] = v
    return c


def test_equal_candidate_passes() -> None:
    assert gate.run(BASE, cand(), CFG)[0] == 0


@pytest.mark.parametrize("path,value", [("component.clean.recall_at_5", 0.87), ("component.clean.mrr", 0.76),
                                        ("e2e.faithfulness_supported_rate", 0.5), ("e2e.abstention_correctness", 0.8),
                                        ("e2e.citation_validity", 0.9), ("e2e.latency_p95_s", 500)])
def test_each_rule_can_fail_alone(path, value) -> None:
    code, lines = gate.run(BASE, cand(**{path: value}), CFG)
    assert code == 1 and sum(ln.startswith("FAIL") for ln in lines) == 1 and "GATE FAILED" in lines[-1]


def test_boundary_is_inclusive() -> None:
    assert gate.run(BASE, cand(**{"component.clean.recall_at_5": 0.88}), CFG)[0] == 0


def test_missing_metric_fails_and_unknown_op_raises() -> None:
    c = cand()
    del c["e2e"]["citation_validity"]
    assert gate.run(BASE, c, CFG)[0] == 1
    with pytest.raises(ValueError):
        gate.check({"metric": "e2e.citation_validity", "op": "bogus", "value": 1}, BASE, BASE)


def test_cli_exit_codes_and_determinism(tmp_path, monkeypatch, capsys) -> None:
    b, g = tmp_path / "b.json", tmp_path / "g.json"
    b.write_text(json.dumps(BASE))
    g.write_text(json.dumps(cand()))
    monkeypatch.setattr(sys, "argv", ["gate", "--baseline", str(b), "--candidate", str(g)])
    assert gate.main() == 0
    first = capsys.readouterr().out
    assert gate.main() == 0 and capsys.readouterr().out == first
    g.write_text("not json")
    assert gate.main() == 2
    g.write_text(json.dumps(cand(**{"e2e.latency_p95_s": 999})))
    assert gate.main() == 1


def test_no_numeric_limit_in_gate_code_and_config_has_reasons() -> None:
    src = Path(gate.__file__).read_text()
    code = re.sub(r'""".*?"""', "", src, flags=re.S)
    assert not re.search(r"(?<![\w.])0\.\d+|[<>]=? ?\d{2,}", code.replace("1e-12", ""))
    assert all(r.get("why") for r in CFG["rules"])


def test_compare_table_has_all_three_levels() -> None:
    full = {"meta": {"label": "x"}, "module": {"gap": 0.3}, "component": {"clean": {"recall_at_5": 0.9}}, "e2e": {"citation_validity": 1}}
    t = table(full, full)
    assert "| module |" in t and "| component |" in t and "| e2e |" in t

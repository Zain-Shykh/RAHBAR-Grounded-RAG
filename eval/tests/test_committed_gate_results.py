"""R7-AC4/AC6: the committed gate outputs equal a fresh gate run on the committed result files."""
import glob
import json
from pathlib import Path

import pytest
import yaml

from suite import gate

R = Path(__file__).resolve().parents[1] / "results"
CFG = yaml.safe_load((Path(gate.HERE) / "gate.yaml").read_text())
BASE = json.loads((R / "suite-20261121T021833Z-baseline-ab.json").read_text())
CASES = [("cand-100-0", 1), ("cand-300-50", 0), ("cand-600-100", 0)]


@pytest.mark.parametrize("label,code", CASES)
def test_committed_gate_file_matches_fresh_run(label, code):
    cand = json.loads(Path(glob.glob(str(R / f"suite-*-{label}.json"))[0]).read_text())
    got, lines = gate.run(BASE, cand, CFG)
    assert got == code
    committed = [ln.split("   (")[0] for ln in (R / f"gate-{label}.txt").read_text().splitlines() if ln[:4] in ("PASS", "FAIL", "GATE")]
    assert [ln.split("   (")[0] for ln in lines] == committed
    assert gate.run(BASE, cand, CFG) == (got, lines)

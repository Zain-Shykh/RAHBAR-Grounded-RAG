#!/usr/bin/env python3
"""Render saved terminal output (docs/evidence/a3/*.txt) as the report's screenshots (R3-S-*).

    python scripts/render_screenshot.py            # all 14 into docs/evidence/a3/screenshots-rendered/<id>-<name>.png
    python scripts/render_screenshot.py B F5       # only those ids

Each PNG is a dark terminal-style page: a label bar (part and item, what it shows, source file), then the command
and the full uncropped output of the source text file(s). The page height is measured by headless Chrome from the
laid-out document before the screenshot is taken, so a tall output gives a tall image and nothing is cut.
The text files hold what the commands printed on the real cluster runs; this script only renders them.
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "docs/evidence/a3"
OUT = EV / "screenshots-rendered"
W = 1500
COV = "PYTHONPATH=. python -m eval.suite.coverage --live eval/live_queries.jsonl --golden eval/golden.jsonl --out eval/results/; echo \"exit code $?\""
B_MD = "eval/results/suite-20261121T021833Z-baseline-ab.md"

# id, file name stem, label, [(source relative to ROOT, command to print first when the file has none)]
ITEMS = [
    ("A1", "verification-report-batch-b", "A1  verification report for Batch B (pass or fail per check, with reasons)", [("docs/evidence/a3/a1-verification-report.txt", None)]),
    ("A2", "second-run-unchanged", "A2  second ingestion run on an unchanged corpus: 0 chunks embedded", [("docs/evidence/a3/a2-unchanged-run.txt", None)]),
    ("B", "evaluation-summary", "B  evaluation summary, all three levels (module, component, end-to-end)",
     [(B_MD, "cat " + B_MD + "   # the summary written by the suite run labelled baseline-ab (python -m eval.suite.run_suite --subset all, run as the eval Job)")]),
    ("C1", "gate-fails", "C1  release gate FAILING (candidate chunk 100 / overlap 0): the Job is Failed, no release", [("docs/evidence/a3/r9-gate-fail.txt", None)]),
    ("C2", "gate-passes", "C2  release gate PASSING (candidate chunk 300 / overlap 50): the Job is Complete", [("docs/evidence/a3/r9-gate-pass.txt", None)]),
    ("D1", "trace-record", "D1  one full trace record (JSON)", [("docs/evidence/a3/d1-trace-record.txt", None)]),
    ("D2", "trace-tool-prompt", "D2  trace tool rebuilding the exact context and prompt for a trace id", [("docs/evidence/a3/d2-trace-tool.txt", None)]),
    ("E1", "coverage-before", "E1  coverage of the 40 live queries before the new golden questions (exit code 1)", [("docs/evidence/a3/e1-coverage-before.txt", COV)]),
    ("E2", "coverage-after", "E2  coverage after adding 16 golden questions (share rises; still below target)", [("docs/evidence/a3/e1-coverage-after.txt", COV)]),
    ("F1", "kubectl-get-all", "F1  kubectl get all,pvc,configmap,cronjob,job (namespace rahbar)", [("docs/evidence/a3/f1-get-all-final.txt", None)]),
    ("F2", "ingestion-job-logs", "F2  logs of a completed ingestion Job (real corpus)", [("docs/evidence/a3/f2-ingest-job-logs.txt", None)]),
    ("F3", "eval-job-logs", "F3  logs of completed evaluation Jobs (baseline, then live run)", [("docs/evidence/a3/f3-eval-job-logs.txt", None)]),
    ("F4", "gate-after-configmap-edit", "F4  gate outcome changes after a ConfigMap edit, same image", [("docs/evidence/a3/f4-gate-change.txt", None)]),
    ("F5", "rollout-undo-trace", "F5  kubectl rollout status / undo, then a trace showing the previous collection and embedding version",
     [("docs/evidence/a3/r9-rollout-undo.txt", None), ("docs/evidence/a3/r9-trace-after-undo.txt", None)]),
]

CSS = f"""
html{{background:#0d1117}}
body{{margin:0;background:#0d1117;color:#d6dde6;font:14px/1.38 'DejaVu Sans Mono','Liberation Mono',monospace;width:{W}px}}
.bar{{background:#1f6feb;color:#fff;padding:10px 16px;font-weight:700;font-size:16px}}
.src{{background:#161b22;color:#8b949e;padding:5px 16px;border-bottom:1px solid #30363d}}
pre{{margin:0;padding:12px 16px;white-space:pre-wrap;word-break:break-all}}
.cmd{{color:#7ee787}} .com{{color:#8b949e}} .fail{{color:#ff7b72}} .pass{{color:#7ee787}}
.sep{{border-top:2px dashed #30363d;margin:6px 0}}
"""


def colour(line: str) -> str:
    e = html.escape(line)
    if line.startswith("$"):
        return f'<span class="cmd">{e}</span>'
    if line.startswith("#"):
        return f'<span class="com">{e}</span>'
    if re.match(r"\s*(FAIL|GATE FAILED)", line) or " Failed " in line:
        return f'<span class="fail">{e}</span>'
    if re.match(r"\s*(PASS|GATE PASSED)", line):
        return f'<span class="pass">{e}</span>'
    return e


def page(label: str, srcs: list[tuple[str, str | None]]) -> str:
    body = []
    for rel, cmd in srcs:
        text = (ROOT / rel).read_text().rstrip("\n")
        first = text.splitlines()[0] if text else ""
        pre = f"$ {cmd}\n" if cmd and not first.startswith("$") else ""
        body.append(f'<div class="src">source file: {html.escape(rel)}</div><pre>' +
                    "\n".join(colour(ln) for ln in (pre + text).splitlines()) + "</pre>")
    return (f"<!doctype html><meta charset=utf-8><style>{CSS}</style><div id=w><div class=bar>{html.escape(label)}</div>"
            + '<div class="sep"></div>'.join(body) + '<div class="src">[end of captured output]</div></div>')


def chrome(*args: str) -> str:
    r = subprocess.run(["google-chrome", "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", *args],
                       capture_output=True, text=True, timeout=120)
    return r.stdout


def render(item: tuple) -> Path:
    id_, name, label, srcs = item
    OUT.mkdir(parents=True, exist_ok=True)
    doc = page(label, srcs)
    with tempfile.TemporaryDirectory() as d:
        probe = Path(d) / "p.html"
        probe.write_text(doc + "<script>document.title='H='+document.getElementById('w').getBoundingClientRect().height</script>")
        dom = chrome("--dump-dom", f"--window-size={W},800", probe.as_uri())
        m = re.search(r"<title>H=([\d.]+)</title>", dom)
        h = int(float(m.group(1))) + 110 if m else 2000   # headless Chrome's viewport is shorter than the window: pad
        f = Path(d) / "s.html"
        f.write_text(doc)
        png = OUT / f"{id_}-{name}.png"
        chrome(f"--screenshot={png}", f"--window-size={W},{h}", f.as_uri())
    print(f"{png.relative_to(ROOT)}  {W}x{h}")
    return png


if __name__ == "__main__":
    want = set(sys.argv[1:])
    for it in ITEMS:
        if not want or it[0] in want:
            render(it)

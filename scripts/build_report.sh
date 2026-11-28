#!/bin/bash
# Build two PDFs with the same body and different appendices: pandoc (markdown -> HTML, print stylesheet) + headless Chrome print (D-125).
#   docs/report/report.pdf           terminal captures (C1, F3, F5 left out)
#   docs/report/report-rendered.pdf  all 14 images rendered from saved terminal output
# Main body page count is checked against 8 (R3-G).
set -euo pipefail
cd "$(dirname "$0")/.."
R=docs/report
SHOTS=docs/evidence/a3/screenshots
for VARIANT in real rendered; do
export VARIANT
OUT=$R/report.pdf; if [ $VARIANT = rendered ]; then OUT=$R/report-rendered.pdf; fi
pandoc $R/report.md -f markdown+pipe_tables+raw_html -t html5 -s --metadata pagetitle="RAHBAR RAGOps report" --css=print.css -o $R/body.html
python3 - <<'PY'
from pathlib import Path
import os
rendered = os.environ["VARIANT"] == "rendered"
R = Path("docs/report"); DIR = "screenshots-rendered" if rendered else "screenshots"
S = Path("docs/evidence/a3") / DIR
labels = {"A1": "A1 verification report for Batch B", "A2": "A2 second ingestion run, unchanged corpus", "B": "B evaluation summary, three levels",
          "C1": "C1 release gate failing", "C2": "C2 release gate passing", "D1": "D1 one full trace record", "D2": "D2 trace tool rebuilding the prompt",
          "E1": "E1 coverage before", "E2": "E2 coverage after", "F1": "F1 kubectl get all,pvc,configmap,cronjob,job",
          "F2": "F2 ingestion Job logs", "F3": "F3 evaluation Job logs", "F4": "F4 gate change after a ConfigMap edit", "F5": "F5 rollout status and undo, trace after undo"}
if rendered:
    order = list(labels)
    title = "Appendix: rendered terminal output"
    note = ("These 14 images are rendered from terminal output saved during earlier cluster runs. They are not terminal screenshots. "
            "They were made before the partner review fixes: C1 and F5 show the earlier release experiment (not the gate-guarded release and the separate rollback drill of section 3), "
            "and E2 shows coverage round 1 only (27 of 40). The later runs are in <code>c-gate-blocks-candidate.txt</code>, <code>c3-gated-release-and-drill.txt</code> and "
            "<code>eval/results/</code>. Real terminal captures are in <code>report.pdf</code>.")
else:
    order = [k for k in labels if k not in ("C1", "F3", "F5")]
    title = "Appendix: terminal screenshots"
    note = ("11 terminal captures. A1, A2, F2 and D2 were captured through a temporary helper script that is not in the repository; A1, A2 and F2 display saved results of earlier runs. "
            "D1 shows the trace tool's output cut at 40 lines, not the full JSON record. D2 starts partway through the output. F3 and F5 were not captured because we were short on time. "
            "C1 is left out: its capture used a wrong result file name and shows a file error, not a gate rejection. All 14 items, rendered from saved output, are in <code>report-rendered.pdf</code>.")
files = {p.name.split("-")[0]: p for p in S.glob("*.png")}
h = (R / "body.html").read_text()
app = f'<div class="appendix"><h2>{title}</h2><p>{note} Full-resolution PNGs are in <code>docs/evidence/a3/{DIR}/</code>.</p></div>'
for n, k in enumerate(order):
    app += f'<div class="shot{" first" if n == 0 else ""}"><h3>{labels[k]}</h3><img src="../evidence/a3/{DIR}/{files[k].name}"></div>'
h = h.replace("</body>", app + "</body>")
(R / "full.html").write_text(h)
PY
google-chrome --headless --no-sandbox --disable-gpu --no-pdf-header-footer --print-to-pdf=$OUT file://$PWD/$R/full.html 2>/dev/null
rm -f $R/body.html $R/full.html
# body pages = pages before the first appendix page
N=$(pdfinfo $OUT | awk '/Pages:/{print $2}'); FOUND=0
for p in $(seq 1 "$N"); do
  if pdftotext -f "$p" -l "$p" $OUT - | grep -qE "Appendix: (terminal|rendered)"; then echo "$OUT: total pages $N, body pages $((p-1)), appendix from page $p"; FOUND=1; break; fi
done
[ $FOUND = 1 ] || { echo "appendix heading not found in $OUT" >&2; exit 1; }
done

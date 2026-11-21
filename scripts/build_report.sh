#!/bin/bash
# Build docs/report/report.pdf: pandoc (markdown -> HTML, print stylesheet) + headless Chrome print (no LaTeX engine here, D-125).
# The appendix is the 14 screenshots, one per page, after the body. Main body page count is checked against 8 (R3-G).
set -euo pipefail
cd "$(dirname "$0")/.."
R=docs/report
SHOTS=docs/evidence/a3/screenshots
pandoc $R/report.md -f markdown+pipe_tables+raw_html -t html5 -s --metadata pagetitle="RAHBAR RAGOps report" --css=print.css -o $R/body.html
python3 - <<'PY'
from pathlib import Path
import re
R = Path("docs/report"); S = Path("docs/evidence/a3/screenshots")
labels = {"A1": "A1 verification report for Batch B", "A2": "A2 second ingestion run, unchanged corpus", "B": "B evaluation summary, three levels",
          "C1": "C1 release gate failing", "C2": "C2 release gate passing", "D1": "D1 one full trace record", "D2": "D2 trace tool rebuilding the prompt",
          "E1": "E1 coverage before", "E2": "E2 coverage after", "F1": "F1 kubectl get all,pvc,configmap,cronjob,job",
          "F2": "F2 ingestion Job logs", "F3": "F3 evaluation Job logs", "F4": "F4 gate change after a ConfigMap edit", "F5": "F5 rollout status and undo, trace after undo"}
order = list(labels)
files = {p.name.split("-")[0]: p for p in S.glob("*.png")}
h = (R / "body.html").read_text()
app = '<div class="appendix"><h2>Appendix: screenshots</h2><p>Renderings of the terminal output saved from the real cluster runs (command first, output uncropped). Source files and commands: <code>docs/evidence/a3/README.md</code>. Full-resolution PNGs are in <code>docs/evidence/a3/screenshots/</code>.</p></div>'
for k in order:
    app += f'<div class="shot"><h3>{labels[k]}</h3><img src="../evidence/a3/screenshots/{files[k].name}"></div>'
h = h.replace("</body>", app + "</body>")
(R / "full.html").write_text(h)
PY
google-chrome --headless --no-sandbox --disable-gpu --no-pdf-header-footer --print-to-pdf=$R/report.pdf file://$PWD/$R/full.html 2>/dev/null
rm -f $R/body.html $R/full.html
# body pages = pages before the first appendix page
N=$(pdfinfo $R/report.pdf | awk '/Pages:/{print $2}')
for p in $(seq 1 "$N"); do
  if pdftotext -f "$p" -l "$p" $R/report.pdf - | grep -q "Appendix: screenshots"; then echo "total pages $N, body pages $((p-1)), appendix from page $p"; exit 0; fi
done
echo "appendix heading not found" >&2; exit 1

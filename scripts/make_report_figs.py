#!/usr/bin/env python3
"""Figure for the report (stdlib only): faithfulness per chunking candidate against the gate limit. Values are read
from the committed suite result files; the limit is baseline minus the rule's 0.05 from eval/gate.yaml.
    python scripts/make_report_figs.py  ->  docs/report/fig-candidates.svg
"""
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
runs = [("baseline 400/50", "suite-20261121T021833Z-baseline-ab"), ("100/0", "suite-20261121T041138Z-cand-100-0"),
        ("300/50", "suite-20261121T053953Z-cand-300-50"), ("600/100", "suite-20261121T072649Z-cand-600-100")]
vals = [(n, json.loads((R / f"eval/results/{f}.json").read_text())["e2e"]["faithfulness_supported_rate"]) for n, f in runs]
limit = vals[0][1] - 0.05
W, H, x0, y0, ph = 560, 190, 60, 20, 130
y = lambda v: y0 + ph * (1 - (v - 0.7) / 0.3)  # noqa: E731  axis 0.70 to 1.00
s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="11">']
for t in (0.7, 0.8, 0.9, 1.0):
    s.append(f'<line x1="{x0}" x2="{W-10}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#ccc"/><text x="{x0-6}" y="{y(t)+4:.1f}" text-anchor="end">{t:.2f}</text>')
for i, (n, v) in enumerate(vals):
    x = x0 + 20 + i * 125
    col = "#c0392b" if v < limit else "#2e7d32" if i else "#555"
    s.append(f'<rect x="{x}" y="{y(v):.1f}" width="70" height="{y0+ph-y(v):.1f}" fill="{col}"/>')
    s.append(f'<text x="{x+35}" y="{y(v)-4:.1f}" text-anchor="middle">{v:.3f}</text><text x="{x+35}" y="{y0+ph+15}" text-anchor="middle">{n}</text>')
s.append(f'<line x1="{x0}" x2="{W-10}" y1="{y(limit):.1f}" y2="{y(limit):.1f}" stroke="#000" stroke-dasharray="5,3"/>'
         f'<text x="{W-12}" y="{y(limit)-4:.1f}" text-anchor="end">gate limit {limit:.3f}</text></svg>')
(R / "docs/report/fig-candidates.svg").write_text("\n".join(s))
print("wrote docs/report/fig-candidates.svg", [(n, round(v, 3)) for n, v in vals], round(limit, 3))

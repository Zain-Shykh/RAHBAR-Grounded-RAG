"""The per-run verification report (R3-A1-4): JSON for machines, a text table for people."""

from __future__ import annotations

from .stage import CHECKS, Verdict


def build_report(run_id: str, corpus_dir: str, embed_model: str, verdicts: list[Verdict],
                 threshold: float) -> dict:
    totals = {"checked": len(verdicts), "passed": 0, "quarantined": 0, "superseded": 0}
    for v in verdicts:
        if v.action == "quarantine":
            totals["quarantined"] += 1
        elif v.action in ("supersede", "supersede_registry"):
            totals["superseded"] += 1
        else:
            totals["passed"] += 1
    return {"run_id": run_id, "corpus_dir": corpus_dir, "embed_model": embed_model,
            "neardup_threshold": threshold, "totals": totals,
            "documents": [{"source": v.source, "action": v.action, "checks": v.checks} for v in verdicts]}


def render_text(report: dict) -> str:
    lines = [f"verification report {report['run_id']}  (embed model {report['embed_model']}, "
             f"near-duplicate threshold {report['neardup_threshold']})", ""]
    head = f"{'document':<42} {'action':<18} " + " ".join(f"{c:<12}" for c in CHECKS)
    lines += [head, "-" * len(head)]
    detail = []
    for d in report["documents"]:
        marks = " ".join(f"{'PASS' if d['checks'][c]['pass'] else 'FAIL':<12}" for c in CHECKS)
        lines.append(f"{d['source'][:41]:<42} {d['action']:<18} {marks}")
        for c in CHECKS:
            if not d["checks"][c]["pass"]:
                detail.append(f"  {d['source']}: {c}: {d['checks'][c]['reason']}")
    if report.get("unchanged"):
        lines += ["", f"not re-checked, unchanged since their last verified run ({len(report['unchanged'])}): "
                  + ", ".join(report["unchanged"])]
    if report.get("previously_quarantined"):
        lines += ["", f"still quarantined, same file as before ({len(report['previously_quarantined'])}): "
                  + ", ".join(report["previously_quarantined"])]
    t = report["totals"]
    lines += ["", "reasons for failures:"] + (detail or ["  none"]) + [
        "", f"totals: checked {t['checked']}, indexed {t['passed']}, quarantined {t['quarantined']}, "
            f"superseded {t['superseded']}"]
    return "\n".join(lines)

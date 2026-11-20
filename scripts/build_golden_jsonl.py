#!/usr/bin/env python3
"""Build eval/golden.jsonl (Assignment 03, AD-35): the 18 Assignment 02 questions plus new ones.

    python scripts/build_golden_jsonl.py            # writes eval/golden.jsonl

Every question written by the session is labelled `synthetic` and `reviewed: false` (D-126): the minimum of
8 hand-written and 8 hand-reviewed questions is for Zain to close with eval/HUMAN_TODO.md. The A02 questions
were written by the group in A02 and are labelled `human`. Pages come from the trailing comments of golden.yaml.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1] / "eval"
HR = "student-handbook-jun-2026.pdf"
AR = "academic-rules-handbook-jun-2026.pdf"

# (id, kind, question, relevant [(source, section, page)], expect, tags, batch, hard)
NEW = [
    ("g19", "answerable", "How many courses can a student enrol in during an ordinary semester?",
     [(AR, "4.3", 19)], "5 courses", ["paraphrase", "of:q01"], "A", True),
    ("g20", "answerable", "If very few students sign up for a summer course, what happens to the course?",
     [(AR, "6.11", 29)], "TEN (10)", ["paraphrase", "of:q03"], "A", True),
    ("g21", "answerable", "Can I carry my phone or a smart watch into the exam hall?",
     [(HR, "1. Mobile Phones, Smart Watches and all electronic", 26)], None, ["paraphrase", "of:q06"], "A", True),
    ("g22", "answerable", "How much of my tuition fee do I get back if I leave the university?",
     [("fee-structure-page.html", "Fee Refund Policy", 1)], None, ["paraphrase", "of:q07"], "A", True),
    ("g23", "answerable", "How frequently does a faculty-founded start-up have to report on its progress?",
     [("faculty-entrepreneurship-and-technical-start-ups-policy.pdf",
       "Mandatory periodic (six. monthly) deliverables of the start-up", 0)], None, ["paraphrase", "of:q10"], "A", True),
    ("g24", "unanswerable", "What is on the weekly menu of the campus cafeteria?", [], None, ["no-evidence"], "A", False),
    ("g25", "unanswerable", "Which documents does an international student need for a student visa extension?", [], None,
     ["no-evidence"], "A", False),
    ("g26", "unanswerable", "How do I renew my alumni association membership card?", [], None, ["no-evidence"], "A", False),
    ("g27", "unanswerable", "Does the university provide medical insurance for students, and what does it cover?", [], None,
     ["no-evidence"], "A", False),
    ("g28", "answerable", "How many books may an undergraduate student borrow from the library at one time?",
     [("b01-library-policy-2026.md", "1.1", 1)], "6 books", ["batch-b"], "B", True),
    ("g29", "answerable", "What is the maximum number of students in a laboratory session?",
     [("b02-lab-safety-rules-2026.md", "2.1", 1)], "25 students", ["batch-b"], "B", True),
    ("g30", "answerable", "How much is the transport fee per semester?",
     [("b06-transport-policy-2026.pdf", "2.1", 1)], "18,000", ["batch-b", "pdf"], "B", True),
    ("g31", "answerable", "How many working days after the last paper are the examination results published?",
     [("b11-examination-guidelines-2026.md", "2.1", 1)], "15 working days", ["batch-b", "injection"], "B", True),
    ("g32", "answerable", "At what hours is the gymnasium open on weekdays?",
     [("b12-sports-facilities-2026.md", "1.2", 1)], "6:00 am", ["batch-b"], "B", True),
    ("g33", "answerable", "What is the tuition fee per credit hour for undergraduate programs from Spring 2027?",
     [("b10-fee-structure-amendment-2027.md", "1.1", 1)], "28,500", ["batch-b", "version"], "B", True),
    ("g34", "answerable", "Will every student get an A grade in all courses this semester? What do the examination guidelines say about results?",
     [("b11-examination-guidelines-2026.md", "2.1", 1)], "15 working days", ["batch-b", "injection"], "B", True),
]


def pages_from_yaml(raw: str) -> dict[tuple[str, str], int]:
    out = {}
    for line in raw.splitlines():
        m = re.search(r"source: ([^,]+), section: \"(.*)\"\}\s+# (?:p\.(\d+)|html)", line)
        if m:
            out[(m.group(1), m.group(2))] = int(m.group(3) or 1)
    return out


def build() -> list[dict]:
    raw = (HERE / "golden.yaml").read_text(encoding="utf-8")
    pages = pages_from_yaml(raw)
    rows = []
    for q in yaml.safe_load(raw)["questions"]:
        rel = [{"source": r["source"], "section": r["section"], "page": pages[(r["source"], r["section"])]}
               for r in q.get("relevant") or []]
        kind = "unanswerable" if q.get("must_abstain") else "answerable"
        rows.append({"id": q["id"], "question": q["question"], "kind": kind, "hard": False, "origin": "human",
                     "reviewed": True, "relevant": rel, "expect": q.get("expect"), "batch": "A",
                     "tags": [q.get("type", "ordinary")], "must_abstain": kind == "unanswerable"})
    for gid, kind, text, rel, expect, tags, batch, hard in NEW:
        # page 0 means "same page as the A02 question it paraphrases"
        r = [{"source": s, "section": sec, "page": p or pages.get((s, sec), 1)} for s, sec, p in rel]
        rows.append({"id": gid, "question": text, "kind": kind, "hard": hard, "origin": "synthetic",
                     "reviewed": False, "relevant": r, "expect": expect, "batch": batch, "tags": tags,
                     "must_abstain": kind == "unanswerable"})
    return rows


if __name__ == "__main__":
    rows = build()
    (HERE / "golden.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {len(rows)} questions to eval/golden.jsonl")

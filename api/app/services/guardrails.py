"""The retrieval rail (architecture-a3 7.4, AD-40): instruction-like text in a retrieved passage is dropped.

A pattern rail, not a classifier: a paraphrased injection passes, and the A02 defences (delimiter stripping,
the system prompt, citation validation) still apply. Every action is written into the trace.
"""

from __future__ import annotations

import re
from typing import Any

from ..schemas import Passage

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("override_instructions", re.compile(
        r"\b(?:ignore|disregard|forget|override)\b\W+(?:(?:all|any|the|your|these|those)\W+)?"
        r"(?:previous|prior|above|earlier|preceding|system)\W+(?:instructions?|rules?|prompts?|guidelines?)\b"
        r"|\b(?:ignore|disregard|forget)\b\W+(?:all|any|your|these)\W+(?:instructions?|prompts?)\b", re.I)),
    ("role_reassign", re.compile(r"\byou are now\b|\bpretend (?:to be|you are)\b", re.I)),
    ("reveal_prompt", re.compile(
        r"\b(?:reveal|print|show|repeat|output)\b[^.\n]{0,30}\b(?:system|hidden|initial)\b[^.\n]{0,15}\bprompt\b", re.I)),
    ("addressed_to_model", re.compile(
        r"\b(?:note|message|instruction)s? (?:to|for) (?:the )?(?:assistant|ai|model|llm|chatbot)\b", re.I)),
    ("suppress_citation", re.compile(r"\bdo not cite\b|\bdon'?t cite\b|\bnever cite\b", re.I)),
]


def scan_text(text: str) -> list[str]:
    return [name for name, rx in PATTERNS if rx.search(text)]


def scan_passages(passages: list[Passage]) -> tuple[list[Passage], list[dict[str, Any]]]:
    """(passages that stay, one action record per dropped passage)."""
    kept: list[Passage] = []
    actions: list[dict[str, Any]] = []
    for p in passages:
        hits = scan_text(p.text)
        if hits:
            actions.append({"rail": "injection_scan", "action": "dropped_passage", "chunk_id": p.chunk_id,
                            "source": p.source, "section": p.section, "pattern": hits})
        else:
            kept.append(p)
    return kept, actions

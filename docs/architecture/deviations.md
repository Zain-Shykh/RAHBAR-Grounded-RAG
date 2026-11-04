# Deviations from the architecture

Companion to [`architecture.md`](architecture.md) (version 1.0). Every place where the code, manifests or pipelines differ from what `architecture.md` says is recorded here, on the day it happens. Nothing is allowed to drift silently.

The log starts empty. An empty log means "built as designed". It is checked before every pull request to `main` and again before submission.

## 1. What counts as a deviation

Log an entry when any of these is true:

- A hard invariant (`architecture.md` section 0.2, I-1 to I-17) cannot be met as written.
- A class A or class B decision (section 0.1) is implemented differently from the document: a different component, port, probe value, NetworkPolicy path, ConfigMap key, metric name, metadata field, API shape, overlay layout or pipeline order.
- A security setting is relaxed (for example a container cannot run non-root, or a root filesystem has to be writable).
- A requirement in `docs/requirements.md` is met by a different mechanism than the architecture chose.
- An assumption or risk in section 9 of the architecture turns out to be false and the plan changes.
- A decision tagged `◇` is replaced after the user has seen the reason.

Not a deviation: choices in class C (private names, internal module splits, test layout, formatting), tuning a number that the architecture says is to be measured (chunk size, relevance floor, cache threshold, resource requests and limits), and filling in a value the architecture left as "pin at implementation" (image tags).

## 2. Rules

1. Log first or log in the same pull request as the change. Not later.
2. One entry per deviation. Keep it short and factual: what the document said, what was built, why.
3. A deviation ends in exactly one of two ways. **Reverted**: the code goes back to the architecture. **Absorbed**: `architecture.md` is amended in a pull request (new row in its version history) and the entry is marked `Absorbed in vX.Y`.
4. A class B or class A deviation needs a human decision before it is merged to `main`. An AI agent may implement it on `dev` and must say so in the pull request. Class A deviations (from the assignment) are almost never acceptable; if one is unavoidable, add a line to the matching ADR and tell the instructors in the README.
5. Never delete an entry. Change its status.
6. If the deviation changes a contract (request, response, metadata fields), also write or update an ADR, as `STARTER.md` requires.
7. If the deviation touches a deduction item in `docs/rubric_checklist.md` section A, say so in the entry and re-verify that item.

## 3. Severity

| Level | Meaning | Approval |
| --- | --- | --- |
| S1 | Breaks a hard invariant, an assignment requirement, or removes a security control | Human approval before merge to `main`; ADR or README note |
| S2 | Changes a class B decision or an externally visible contract without breaking an invariant | Human approval before merge to `main` |
| S3 | Local or temporary difference with no effect on behaviour or evidence (for example a workaround for a tool version) | Record only; absorb or revert before submission |

## 4. Statuses

`OPEN` (in effect, no decision), `ACCEPTED` (human agreed to keep it, not yet written into the architecture), `ABSORBED vX.Y` (architecture amended), `REVERTED` (code restored to the architecture), `SUPERSEDED BY DEV-NNN`.

Nothing may stay `OPEN` or `ACCEPTED` at submission unless the architecture is amended to match or the entry is explained in the README.

## 5. Entry template

Copy this block to the end of section 7, increment the number, and fill every line. Delete lines that truly do not apply.

```markdown
### DEV-NNN Short title

| | |
| --- | --- |
| Status | OPEN |
| Severity | S1 / S2 / S3 |
| Date | YYYY-MM-DD |
| Raised by | name or agent |
| Architecture reference | section and decision id, for example 4.6 (NetworkPolicy), AD-04, I-11 |
| Files changed | `path`, `path` |
| Related | PR #, issue, `docs/OPEN_DECISIONS.md` D-NNN, ADR number |

**The architecture says:** one or two sentences.

**What was built instead:** one or two sentences.

**Why:** the concrete obstacle (error message, version limit, measurement). Include the evidence.

**Impact:** what behaviour, security, requirement or deduction item changes. Say "none" if none.

**Plan:** revert by ..., or amend architecture section ... .

**Decision:** (human fills in) accepted / rejected / amend architecture, with date.
```

## 6. Index

| ID | Title | Severity | Status | Architecture reference | Date |
| --- | --- | --- | --- | --- | --- |
| DEV-001 | PDF extraction uses pdfplumber default text mode, not layout mode | S3 | OPEN | 5.4.2 (extract) | 2026-11-04 |

## 7. Log

*(Entries start here. Newest last.)*

### DEV-001 PDF extraction uses pdfplumber default text mode, not layout mode

| | |
| --- | --- |
| Status | OPEN |
| Severity | S3 |
| Date | 2026-11-04 |
| Raised by | Claude (phase 5, found in phase 4 evidence) |
| Architecture reference | 5.4.2 (extract) |
| Files changed | `indexer/pipeline/extract.py` (phase 4, already merged) |
| Related | `docs/PIPELINE.md`, `docs/examples/annual-report-2023-24-p13-before.txt`, `docs/examples/annual-report-2023-24-p13-after.txt`, `docs/specs/phase-04-extract-clean.md` |

**The architecture says:** PDF extraction is "`pdfplumber` text per page, layout preserved so table rows stay on one line".

**What was built instead:** `page.extract_text()` in default text mode. `extract_text(layout=True)` is not used.

**Why:** default mode already keeps a table row on one line (Annual Report 2023-24 PDF page 13: `Islamabad 19 14 46 16 83 50 8 236`). Layout mode keeps rows too, but pads every line with spaces and adds blank lines that the cleaner would have to strip. Evidence: `docs/PIPELINE.md` and `docs/examples/annual-report-2023-24-p13-*.txt`.

**Impact:** none on behaviour. The goal of the sentence (table rows on one line) is met. No invariant, requirement or deduction item changes.

**Plan:** absorb: reword architecture 5.4.2 to "table rows stay on one line (pdfplumber default text mode)" in the next architecture version.

**Decision:** (human fills in)

---

## 8. Watch list

Places where the architecture has flagged a real chance of deviation (architecture section 9). If one of these happens, it is a deviation, and the entry should link to the risk number.

| Risk | If it happens, the likely deviation | Severity guess |
| --- | --- | --- |
| R-01 Chroma cannot run non-root with read-only root | Relaxed `securityContext` on `chroma` | S1 (security control) |
| R-02 Redis Stack cannot run non-root or needs a writable path | Relaxed `securityContext` on `redis`, or fall back to plain Redis with app-side cosine (D-001 option B) | S1, or S2 for the fallback |
| A-2 / A-3 Chroma rename or batch size not as assumed | Different swap procedure in the indexer `store` stage | S2 |
| A-4 `kubectl cp` into the PVC fails | Different corpus delivery (init container fetch, D-003) | S2 |
| A-5 native `preStop` sleep unavailable | `exec` sleep with an image that has `sleep` | S3 |
| R-07 NetworkPolicy unenforced on kind | CI cannot prove isolation; evidence comes only from minikube | S3 |
| Kit interface changes in `api/app` | Any change to `Retriever`, `LLMProvider`, `AskResponse` beyond architecture 5.7.2 | S2 |

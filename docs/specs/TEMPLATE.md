# Phase NN spec: <title>

<!-- Copy to docs/specs/phase-NN-<slug>.md. Delete these comments. Fill sections 1 to 9 in the SPEC stage,
     section 10 in the PLAN stage, section 11 during IMPLEMENT, section 12 in the TEST stage, section 13 at each gate.
     Keep it specific: file paths, signatures, numbers. Link, do not copy, text that lives in architecture.md. -->

| | |
| --- | --- |
| Phase | NN, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-NN |
| Branch | `feat/rag-zNN-<topic>` |
| Stage | SPEC DRAFT / SPEC APPROVED / PLAN DRAFT / PLAN APPROVED / IMPLEMENTING / TESTING / READY FOR PR / MERGED |
| Started | YYYY-MM-DD |
| Spec approved | (date, by) |
| Plan approved | (date, by) |
| Depends on | earlier phases, hand-offs H-n |

## 1. Objective

One or two sentences: what exists after this phase that did not exist before, and why it matters to the system.

## 2. Context

- Architecture: sections and decision ids (`architecture.md` 5.4.4, AD-02, ...)
- Requirements: `R-...` ids from `docs/requirements.md`
- Rubric and deduction items this phase touches (`docs/rubric_checklist.md`)
- Open decisions that matter: `D-0NN` and their current status
- Existing code this phase builds on (files, functions)

## 3. Scope

**In scope**

- ...

**Out of scope** (and which phase owns it)

- ...

## 4. Interfaces and contracts

Public functions and classes with full signatures, types, and error behaviour. Config keys read (and their defaults). Files created or changed. Environment variables. HTTP shapes and headers. Anything another module or Ahmad's lane depends on, and whether it changes a frozen contract (C-1 to C-8 in `WORKPLAN.md`).

## 5. Behaviour and design details

The rules the code must follow, in enough detail that two developers would write the same behaviour: algorithms, ordering, thresholds, edge cases, error handling, logging fields, metric names. Say which architecture decisions apply and do not re-argue them.

## 6. Acceptance criteria

Each one testable, with an id. Start from the criteria in `IMPLEMENTATION_PLAN.md` and make them concrete.

- [ ] **AC-1**: ...
- [ ] **AC-2**: ...

## 7. Test strategy and traceability

How each acceptance criterion will be proven. Unit tests need no network, no model, no cluster. Integration tests name the services they need (`make dev-services`, Ollama).

| AC | Level (unit / integration / manual) | Test file and name, or command | Needs |
| --- | --- | --- | --- |
| AC-1 | unit | `api/tests/test_x.py::test_y` | nothing |

## 8. Open questions

Questions the human must answer before the spec can be approved. Record each in `docs/OPEN_DECISIONS.md` as well and link it.

| # | Question | Options and recommendation | Decision entry | Answer |
| --- | --- | --- | --- | --- |
| Q1 | | | D-0NN | |

## 9. Risks and assumptions

Things that could make the spec wrong, and how to find out early.

## 10. Plan

<!-- Filled in the PLAN stage, after the spec is approved. -->

### 10.1 Ordered steps

Small, verifiable steps. Each step ends with something you can run. Prefer slices that each leave `make test` green.

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 1 | | | | |

### 10.2 Test plan

Tests to write (which step writes them), which are written before the code, and what the testing subagent must run.

### 10.3 Rollback and risks

What to do if a step fails; what to revert.

### 10.4 Estimate

Hours per step and total, against the estimate in the work plan.

## 11. Implementation notes

<!-- Filled during IMPLEMENT. Decisions taken in the code, surprises, and any deviation (link DEV-NNN). -->

## 12. Test report

<!-- Filled in the TEST stage. Rounds, commands, results, coverage, failures found and fixed. -->

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

Coverage of `app` (if relevant): `__`%

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec | | | |
| Plan | | | |
| Final (before PR) | | | |

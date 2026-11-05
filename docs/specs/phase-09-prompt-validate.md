# Phase 09 spec and plan: Prompt, validation, CI-mode components

| | |
| --- | --- |
| Phase | 9, from `docs/IMPLEMENTATION_PLAN.md` |
| Work plan task | Z-08 |
| Branch | `feat/rag-z08-prompt-validate` |
| Stage | SPEC DRAFT |
| Started | 2026-11-05 |
| Approved (spec and plan) | pre-approved by Zain 2026-11-05 (no gate for this run) |
| Depends on | phase 8 (retriever, `IndexState`, `EmbedError`); delivers H-6 |

## 1. Objective

An answer can be produced and verified without an LLM: the prompt builder, the validator with the citation check and the canned abstention and fallback texts, the `GenerationResult` provider contract, and the rule-based `extractive` provider that CI uses. Phase 10 wires these into the orchestrator.

## 2. Context

- Architecture: 5.7.1 to 5.7.4, 5.8, 5.10, 5.11, 5.15; AD-07, AD-13, AD-14, AD-25; invariants on citations, abstention, no 500, never cache a fallback.
- Requirements: R-GEN-1..7 (R-GEN-1 enforcement via `format=` is phase 10; R-GEN-2, 4, 5, 6 are tested here).
- Existing code: `api/app/providers/llm/{base,stub,ollama,hosted,__init__}.py` (kit; stub returns `Answer`), `api/app/schemas.py` (`Passage` has no version/status), `api/app/services/answer.py` (kit minimal, uses the provider's return value as an `Answer`), `api/app/retrieval/chroma.py` (builds `Passage`).
- Phase 8 notes for phase 10: `IndexState.problem()`, `IndexUnavailable(reason)`, `Scope.tag`, `EmbedError`. Nothing here conflicts; prompt and validator take `list[Passage]` only.
- Decisions: D-61..D-64 (pre-approved, see section 8).

## 3. Scope

**In scope**

- `providers/llm/base.py`: `GenerationResult`, `InvalidModelOutput`, `ProviderError`, protocol with `hint`.
- `providers/llm/stub.py` returns `GenerationResult`; `ollama.py` / `hosted.py` signatures updated (bodies still `NotImplementedError`).
- `providers/llm/extractive.py` and `get_provider` (`stub`, `extractive`; `ollama-*` raises a clear error until phase 10; `hosted`).
- `services/prompt.py`, `services/validate.py`.
- `schemas.py`: `Passage` gains optional `doc_version` and `superseded` (D-61); `ChromaRetriever` fills them.
- `services/answer.py`: one-line adaptation to `GenerationResult` (stays the thin kit version; phase 10 rewrites it).
- Tests including `injection`, `abstain`, `fallback` named tests. `pytest-cov` pinned in `api/requirements-dev.txt`.
- Extractive provider run on the real index for 3 golden questions, recorded in the results register.

**Out of scope**

- Ollama HTTP client, orchestrator, retry loop, metrics (phase 10); cache (11); floor calibration (12).

## 4. Interfaces and contracts

```python
# providers/llm/base.py
@dataclass
class GenerationResult: answer: Answer; tokens_in: int; tokens_out: int
class InvalidModelOutput(Exception): reason: str      # str(exc) == reason
class ProviderError(Exception): ...
class LLMProvider(Protocol):
    name: str
    def generate(self, question: str, passages: list[Passage], *, hint: str | None = None) -> GenerationResult: ...

# services/prompt.py
def build_messages(question: str, passages: list[Passage], *, hint: str | None = None) -> list[dict[str, str]]  # [system, user]
def strip_delimiters(text: str) -> str          # removes every "<<<" and ">>>"

# services/validate.py
ABSTAIN_TEXT = "The documents in the corpus do not cover this question."
FALLBACK_TEXT = "I could not produce a verified answer from the documents right now. Please try again, or rephrase the question."
def citation_matches(c: Citation, passages: list[Passage]) -> Passage | None   # exact source + section
def validate(raw: str | Answer, passages: list[Passage]) -> Answer             # raises InvalidModelOutput(reason)
def abstention(*, reason: str = "floor") -> Answer     # confidence high if reason == "floor"
def fallback() -> Answer
def retry_hint(exc: InvalidModelOutput) -> str
```

Config keys read: none new. `ExtractiveProvider(settings)` reads `relevance_floor`. No change to HTTP shapes, ConfigMap keys or frozen contracts C-1..C-8. `Passage` gains two optional fields; they are not in `AskResponse`.

## 5. Behaviour and design details

- **Prompt.** Exactly 5.7.1: system text verbatim; user: `<<<EVIDENCE n source="..." section="..." page=14 version="2026-06" status="current">>>`, text, `<<<END n>>>`, blank line, `<<<QUESTION>>>`, question, `<<<END QUESTION>>>`. `n` from 1 in rank order. Header values: `\` and `"` escaped, newlines collapsed to a space, delimiters stripped. `page` omitted when `None`; `version` and `status` omitted when unknown (`status` is `superseded` or `current`). `hint` adds one line after the question block (outside any evidence block).
- **Validation order (5.7.3).** (1) JSON parse (strings only; an `Answer` instance skips to step 2) and `Answer.model_validate`; (2) every citation resolves by exact `source` and exact `section` to a passage, `page` overwritten from that passage, duplicate citations collapsed; (3) `answered_from_context` true needs at least one citation, false empties citations; (4) `answer.strip()` non-empty. Failure: `InvalidModelOutput(reason)` with reason `not_json`, `schema`, `bad_citation: <source>/<section>`, `no_citation`, `empty_answer`. The `bad_citation` prefix lets phase 10 count `reason="bad_citation"` apart from `invalid_output`.
- **Abstention and fallback.** Fixed texts above; `citations=[]`, `answered_from_context=False`; abstention `confidence="high"` for the floor, `"low"` for other reasons; fallback `"low"`. `reasoning` is `"abstain: <reason>"` or `"fallback"`. Neither is ever an extractive answer.
- **Extractive (5.15, D-62).** Tokenise question and sentences (lowercase `\w+`, drop stop-words and tokens shorter than 3 chars). Pick the passage whose best sentence has the most distinct question-word overlaps (ties: higher `score`, then rank). Answer = that sentence plus the next one if it also overlaps. Cite only that passage. Zero overlap anywhere or no passages: `answered_from_context=False`, no citations. Confidence `high` if `passage.score >= floor + 0.15`, else `medium`. `reasoning="extractive"`. Token counts are word counts. Sentence split: on `.`, `!`, `?` or newline followed by whitespace; clause numbers such as `1.1` are not split points.
- **Injection (5.11).** Enforced by code: delimiter tokens removed, so a chunk cannot close its block; output must satisfy `Answer`; citations must match retrieved passages; extractive executes nothing. Not enforced by code: a model that follows an injected instruction while citing a real chunk (wrong claim, valid citation) passes validation. Only a live Ollama run on the golden injection question shows whether the model obeys. The test says so in comments.
- **Logging.** None added (the orchestrator logs in phase 10).

## 6. Acceptance criteria

- [ ] **AC-1** `build_messages` gives exactly two messages (system, user), evidence numbered from 1 in rank order, header fields quoted and escaped, question block last; `<<<` and `>>>` removed from chunk text, question and header values.
- [ ] **AC-2** `validate` raises `InvalidModelOutput` for: non-JSON, wrong schema, a citation whose source or section was not retrieved, `answered_from_context=true` with no citations, an empty answer.
- [ ] **AC-3** `validate` empties citations when `answered_from_context=false`, fills `page` from the passage, and passes a good answer through.
- [ ] **AC-4** Extractive cites only passages it was given and only the one it used; abstains with no passages or no word overlap; deterministic; confidence rule at floor + 0.15.
- [ ] **AC-5** Test `*injection*`: the poisoned fixture chunk is delimited, a `>>>` closer in a chunk is stripped, an injection-obeying fake model that invents a source fails validation, extractive on the fixture states the real 80 percent figure, and comments state what code enforces and what only a live model shows.
- [ ] **AC-6** Test `*abstain*`: abstention text, empty citations, `high` confidence for the floor.
- [ ] **AC-7** Test `*fallback*`: fallback text, `low`, empty citations, text is no passage text.
- [ ] **AC-8** `get_provider` returns stub and extractive; `ollama-*` raises a clear `NotImplementedError` naming phase 10; unknown name raises `ValueError`.
- [ ] **AC-9** Kit tests still pass.
- [ ] **AC-10** At least 12 new test functions; coverage of `app` reported with `pytest --cov=app` and recorded; `pytest-cov` pinned.
- [ ] **AC-11** Extractive answers for 3 golden questions on the real index recorded in the results register.
- [ ] **AC-12** `make test && make lint` green; H-6 text ready for Ahmad.

## 7. Test strategy and traceability

| AC | Level | Test | Needs |
| --- | --- | --- | --- |
| AC-1 | unit | `api/tests/test_prompt.py` | nothing |
| AC-2, AC-3 | unit | `api/tests/test_validate.py` | nothing |
| AC-4 | unit | `api/tests/test_extractive.py` | nothing |
| AC-5 | unit | `api/tests/test_safety.py::test_injection_*` | nothing |
| AC-6, AC-7 | unit | `api/tests/test_safety.py::test_abstain_*`, `test_fallback_*` | nothing |
| AC-8 | unit | `api/tests/test_providers.py` | nothing |
| AC-9 | unit | `api/tests/test_starter.py` | nothing |
| AC-10 | command | `cd api && ../.venv/bin/pytest -q --cov=app` | nothing |
| AC-11 | manual | script feeding retrieved passages to `ExtractiveProvider` | `make dev-services`, index, Ollama (embeddings) |
| AC-12 | command | `make test && make lint` | nothing |

## 8. Open questions

None blocking. Four decisions taken (pre-approved by Zain), recorded in `OPEN_DECISIONS.md`.

| # | Question | Decision |
| --- | --- | --- |
| Q1 | How does the prompt get `version` and `status` when `Passage` has neither? | D-61: optional fields on `Passage` |
| Q2 | Extractive sentence selection | D-62: word overlap |
| Q3 | `ollama-*` before phase 10 | D-63: `NotImplementedError` from `get_provider` |
| Q4 | Topic phrase in the abstention text | D-64: no, fixed text |

## 9. Risks and assumptions

- Extractive may pick the injected sentence for some question (word overlap). Mitigation: test with the fixture; if it fails, skip sentences matching an injection pattern and log it.
- Eval scores citation validity from `retrieved` with its own function; eval cannot import `api.app` (separate package), so the exact-match rule is duplicated by design.
- `pytest-cov` is a dev dependency; if CI does not install `requirements-dev.txt` the coverage step is Ahmad's lane (hand-off).

## 10. Plan

### 10.1 Ordered steps

| Step | What | Files | Verify | Commit message |
| --- | --- | --- | --- | --- |
| 0 | pytest-cov pin | `api/requirements-dev.txt` | `make install` | `chore(api): pin pytest-cov` |
| 1 | Provider contract, stub, signatures, `get_provider`, answer.py adapt, Passage fields and retriever fill | `providers/llm/*`, `schemas.py`, `retrieval/chroma.py`, `services/answer.py`, `tests/test_providers.py` | `make test` | `feat(api): GenerationResult provider contract` |
| 2 | Prompt | `services/prompt.py`, `tests/test_prompt.py` | pytest | `feat(api): prompt builder with delimiter stripping` |
| 3 | Validate, abstention, fallback | `services/validate.py`, `tests/test_validate.py` | pytest | `feat(api): output validation and citation check` |
| 4 | Extractive provider | `providers/llm/extractive.py`, `tests/test_extractive.py` | pytest | `feat(api): extractive provider` |
| 5 | Injection, abstain, fallback tests | `tests/test_safety.py` | pytest | `test(api): injection, abstain, fallback` |
| 6 | Real-index run, coverage, docs | results register, log, AI-USAGE, deviations | script output | `docs: phase 09 results` |

### 10.2 Test plan

Tests written with each step (prompt and validate tests first). Tester runs `make test && make lint`, `pytest --cov=app`, the grep for Chroma writes in `api/app`, and tries malformed JSON, unicode, delimiter variants and oversized passages.

### 10.3 Rollback and risks

All additions; revert the branch. The only changed signature is `generate` (kit stub and the two unimplemented providers).

### 10.4 Estimate

3 h against the work plan's 3 h.

## 11. Implementation notes

## 12. Test report

| Round | Date | Command | Result | Notes |
| --- | --- | --- | --- | --- |

Coverage of `app`: `__`%

## 13. Sign-offs

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Spec and plan (the one gate) | 2026-11-05 | Zain (pre-approved, no gate this run) | |
| Tester verdict PASS | | | rounds: |
| Merged | | | PR # |

# ADR 0004: A thin provider interface, Ollama on the host, and what data leaves the pod

## Status
Accepted · 2026-11-05 (phases 8 to 10, D-57 to D-70; D-87)

## Context
The assignment wants the model behind an interface chosen by `LLM_PROVIDER`, at least one mode fully supported, and the embedding model pinned identically in the indexer and the API (R-LLM-1, R-LLM-5). Our hardware is a laptop CPU: `llama3.2:3b` for generation and `nomic-embed-text` (768 dimensions) for embeddings, both served by one Ollama process on the host and reached from minikube at `host.minikube.internal:11434`.

This ADR also records what the choice means for data: where question text and corpus passages travel, who can read them, and what is stored.

## Decision
**Provider interface.** `api/app/providers/llm/base.py` defines `LLMProvider.generate(question, passages, *, hint=None) -> GenerationResult`. A provider has no policy: retry, validation, fallback and the citation check live in `api/app/services/answer.py` and `validate.py`, so a provider is one small file. The kit's interface gained two optional things (AD-14): the `hint` argument (the one retry quotes the validation error back to the model) and `GenerationResult` (the `Answer` plus `tokens_in` and `tokens_out`, which feed `rahbar_tokens`). External JSON shapes did not change. `Passage` also gained optional `doc_version` and `superseded` for the prompt header (DEV-004).

**Implemented modes:** `ollama-host` (default, measured: p50 39.0 s, p95 138.6 s per uncached question, recall@5 0.875, citation validity 16 of 16), `ollama-incluster` (the same client, a different URL; not run), `extractive` (rule-based, no model: CI and the CD smoke test, AD-07) and `stub` (tests). **`hosted` is not built** (D-87): the stub that raised `NotImplementedError` is gone and `get_provider` raises a `ValueError` naming the supported modes, so a pod configured with `hosted` stops at start-up instead of failing on the first question. The assignment needs one mode fully; the hosted key, the egress rule and the privacy cost below were not worth an untested file.

**Embedding.** The same Ollama serves embeddings (allowed by R-LLM-5; said in the README). The embedder is duplicated in `api/app/embedding/` and `indexer/pipeline/embedding/` because the two images have separate build contexts (AD-09). The hashing embedder (`hashing-bow-768`, CI only) is a byte-for-byte copy; `api/tests/test_embedding.py` and `indexer/tests/test_embed_hashing.py` hold the same golden vector, so a drift in one copy fails a test. The pin is `EMBED_MODEL` in one ConfigMap key; the indexer writes it with the dimension into the collection metadata and `IndexState._check_pin` (`api/app/services/index_state.py`) compares it, so a mismatch makes `/readyz` 503 (`failed:["embed_pin"]`) and refuses every query (`docs/FAILURE-ANALYSIS.md`, stage C).

**Data governance.**
- *Ollama binds to `0.0.0.0`.* Pods can only reach a host service through `host.minikube.internal`, which needs `OLLAMA_HOST=0.0.0.0`. That also exposes port 11434, with no authentication, to every network the laptop is on. Mitigations: do it on a trusted network; the cluster's `api-egress` policy allows only that one `ipBlock` and port; `pkill ollama` when idle. Accepted for a course project; it would not be acceptable on a shared network.
- *No authentication on Chroma or Redis.* Neither has any; their protection is a ClusterIP Service and a NetworkPolicy that admits Chroma from `api` (read) and `indexer` (write) only and Redis from `api` only (architecture 4.6, in Ahmad's manifests). A pod in the namespace with the right label could read both. Stated, not fixed (AD-26: no auth).
- *Question text.* In Ollama modes it goes to the user's own laptop and nowhere else. The API logs ids, scores, outcome, scope and timings per question (`answered` line, `api/app/services/answer.py`), not the question text and not the answer. The one place a question is stored is the semantic cache: the Redis entry holds `question` and the answer JSON for up to 24 h (`CACHE_TTL_SECONDS` 86 400) or until the next re-index. No IP address, no cookie and no user id exist in the system.
- *PII.* The corpus is public university documents; questions come from the public and are not expected to carry personal data, but nothing stops a user typing a name or a roll number. The consequence is that such text could sit in the Redis cache for a day. We did not add redaction.
- *Hosted mode, if someone adds it.* The question text and the retrieved passages (up to the top 5 chunks of about 400 words each, per question) would travel to a third party over the internet, and the key would live in a Secret (`LLM_API_KEY`, already `repr=False` in `api/app/config.py`, never logged). That is acceptable only because the corpus is public; the README must say so, and an egress rule on 443 would have to be added to the network policy.
- *Secrets.* None in Git. The only secret in the design is the optional `LLM_API_KEY`, created by `make secret` from the shell environment.
- *Untrusted text.* Retrieved text and model output are data: delimiters are stripped from retrieved passages, the model is told they are not instructions, and nothing from either reaches `eval` or SQL (`api/app/services/prompt.py`, `validate.py`, `api/tests/test_safety.py::test_injection_poisoned_chunk_is_delimited_and_not_obeyed`). A live injection check did not obey a planted instruction, on two prompts; this is evidence, not proof.

## Options considered
- **`hosted` only (Groq, Google AI Studio, OpenRouter).** Fast, but sends every question and its passages off-site, needs a key and a card-free account that may rate-limit mid-demo, and breaks "runs on a laptop". Rejected as the default; not built at all.
- **`ollama-incluster` as default.** Needs 8 GB for minikube and a startup probe for the weights; the host Ollama is lighter on a student machine. Supported by configuration, not run.
- **Shared Python package for the embedder** to avoid duplication. Needs a common build context or a published wheel; the duplication is 34 lines and a parity test is cheaper. Rejected.
- **Bind Ollama to the minikube bridge IP only** instead of `0.0.0.0`. Narrower, but the bridge address changes between machines and drivers, and the setup guide has to work on Linux, WSL 2 and macOS. Rejected for portability; the risk above is accepted.

## Consequences
- Swapping the model is one file and one ConfigMap value; the validation, retry and fallback do not change.
- Generation is slow and prompt-bound on a CPU: the timeout is 300 s (DEV-007), with the Ingress above it, and answers are terse ("No", "60%", "10"). A larger model or a hosted provider is the lever; it is not pulled.
- Two copies of the hashing embedder must be kept identical by hand; the golden-vector test is the guard.
- Watch: an `OLLAMA_HOST=0.0.0.0` laptop on a public network, question text in the Redis cache, and any future `hosted` mode (it needs this ADR revised first).

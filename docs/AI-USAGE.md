# AI usage

<!-- STARTER-TODO: list every AI tool you used. A specific disclosure carries no penalty. -->

| Tool | What it wrote or shaped | What we changed afterwards, and why |
| --- | --- | --- |
| Claude Code (Sonnet 5.5) | Phase 1: wrote `api/Dockerfile` (two-stage, `/opt/venv`), `indexer/Dockerfile` (tesseract-ocr, poppler-utils), both `.dockerignore`, and the phase spec and plan. An independent Claude subagent tested it in 3 rounds. | Tester found nested `.pyc` leaking (anchored ignore patterns). My first fix (`**/` only) broke the starter checker, so both root and `**/` forms are kept. Decisions on venv, no HEALTHCHECK and leaving the Makefile were Zain's. |
| Claude Code (Sonnet 5.5) | Phase 2: wrote the `dev-services` Makefile targets, `scripts/verify_services.py` (Chroma and Redis Stack behaviour, hardened non-root read-only runs) and `scripts/verify_ollama.py`, and the spec and plan. Ran them for real and recorded results in architecture section 9. | The negative test (services down) exposed an uncaught Chroma connect error in my first script; fixed by moving the client construction into the try. A first hardened Redis run failed because Docker copies root ownership into an empty named volume; the script now seeds and chowns the volume. Choices of tag, script layout and volume policy were Zain's. |

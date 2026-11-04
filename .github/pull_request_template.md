## What and why

<!-- One or two sentences. Link the work plan task (for example Z-05, A-06) or an open decision. -->

Task: 

## Changes

- 

## How it was tested

<!-- Commands you ran and what you saw. For cluster changes include `kubectl get pods -n rahbar`. -->

## Checklist

- [ ] `make test` and `make lint` pass locally
- [ ] No secrets, keys, tokens or `.env` in the diff
- [ ] No `corpus/raw/` content in the diff
- [ ] Matches `docs/architecture/architecture.md`, or a `docs/architecture/deviations.md` entry is included
- [ ] New behaviour has a test; no test deleted or weakened
- [ ] Docs updated if behaviour, config keys or commands changed
- [ ] `docs/AI-USAGE.md` updated if AI helped
- [ ] Anything unclear is in `docs/OPEN_DECISIONS.md`

## Notes for the reviewer

<!-- Anything risky, anything you are unsure about, anything touching the other lane's files. -->

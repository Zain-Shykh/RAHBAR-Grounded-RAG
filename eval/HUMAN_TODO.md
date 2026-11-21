# What only a person can do (D-126)

The session wrote the new golden questions, so they are labelled `synthetic` and `reviewed: false` in
`eval/golden.jsonl`. The assignment asks for at least 8 questions written by hand and 8 synthetic questions reviewed
by hand. The 18 Assignment 02 questions were written by the group (origin `human`), so the first minimum is met;
the second is not until you do the following (about 10 minutes).

## 1. Review 8 synthetic questions

Open [`REVIEW_SHEET.md`](REVIEW_SHEET.md): for g19, g20, g21, g23, g28, g29, g30, g33 it shows the question, the expected answer, the
ground-truth source, section and page, and the real passage read from the live index. Judge each in about 10 seconds and send the
reply in the format at the end of the sheet. The session then applies fixes and runs
`python scripts/mark_reviewed.py <ids> && python -m eval.suite.golden --check` (exit 0 when every minimum is met).
Nobody but you sets `reviewed` (the script refuses `human` questions and unknown ids).

## 2. Optionally write your own 8 questions

If you want the hand-written count to be new work rather than the A02 questions: add eight lines with
`"origin": "human"` and your own wording, with `relevant` filled in. Then re-run `make suite`.

## 3. Report items only you can supply

Roll numbers are on report page 1 (done, 24i-3126 and 24i-3006). Still yours: the contribution table (what each of you did), and approval of the AI
statement. Ahmad did no work on Assignment 03 (D-108); say so plainly in the table.

# What only a person can do (D-126)

The session wrote the new golden questions, so they are labelled `synthetic` and `reviewed: false` in
`eval/golden.jsonl`. The assignment asks for at least 8 questions written by hand and 8 synthetic questions reviewed
by hand. The 18 Assignment 02 questions were written by the group (origin `human`), so the first minimum is met;
the second is not until you do the following (about 10 minutes).

## 1. Review 8 synthetic questions

Open `eval/golden.jsonl`. For each of eight questions with `"origin": "synthetic"`: read the question, open the document
named in `relevant`, check that the section and page really hold the answer and that the question is clear. Fix the
text if it is not, then set `"reviewed": true`. Suggested eight: g19, g20, g21, g22, g23, g24, g28, g29.

Then run `python -m eval.suite.golden --check`; it exits 0 when every minimum is met.

## 2. Optionally write your own 8 questions

If you want the hand-written count to be new work rather than the A02 questions: add eight lines with
`"origin": "human"` and your own wording, with `relevant` filled in. Then re-run `make suite`.

## 3. Report items only you can supply

Roll numbers for both members (report page 1), the contribution table (what each of you did), and approval of the AI
statement. Ahmad did no work on Assignment 03 (D-108); say so plainly in the table.

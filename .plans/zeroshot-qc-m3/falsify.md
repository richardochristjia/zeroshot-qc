# Falsify — M3 must-fix findings

Source: [review-correctness.md](.plans/zeroshot-qc-m3/review-correctness.md) must-fix list (1 finding).

## Rulings (worst harm first)

fix: rules containing `{detections_table}` are silently rewritten, not verbatim (correctness review). Reproduced live: `render_judge_prompt("reject if {detections_table} appears", [])` yields `verbatim-kept: False`, rules line rendered as `reject if (no candidates) appears` — the review's run is confirmed accurate.

Trace: only caller is `backend/app/adapters/muse_spark.py:43`, `prompt = render_judge_prompt(profile.rules, detections)`; `profile.rules` is user-authored (profile YAML / CLI `--rules`). Hit requires rules text to literally contain `{detections_table}` — rare in practice, but the input is free-form user text with no upstream check ruling it out, so not hypothetical, just low-frequency.

Harm: silent corruption of the judge's instructions — the judge rules on different text than the user wrote, which can flip a verdict. That is worse than a recoverable wrong message (the caller never sees the prompt), bordering on wrong state. Fix is cheap and removes the harm entirely: single-pass substitution over the three slots (e.g. one regex pass on the template), which preserves the existing "JSON braces never disturb rendering" property. Failing-now test: `assert rules in render_judge_prompt(rules, [])` with `rules = "reject if {detections_table} appears"` — fails today, passes with the fix.

## For the fixer

- fix: single-pass substitution in `render_judge_prompt` (`backend/app/prompts/__init__.py:44-48`) so inserted rules text is never re-scanned for slots; add the verbatim test above.

## For the user

(none — no new rule or special case needed.)

## For the PR's open findings

(none.)

## Dismissed

(none.)

## Fix outcome

Fixed: `render_judge_prompt` now substitutes the three slots in a single
regex pass, so rules text containing `{detections_table}` renders verbatim.
Added `test_rules_containing_slot_literal_render_verbatim` (fails on old
code, passes with fix). Suite: 113 passed.

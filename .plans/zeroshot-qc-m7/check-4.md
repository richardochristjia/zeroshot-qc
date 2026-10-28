# Check-4: Verification phase vs code

Read: `plan.md` Verification/Record Updates/Test Strategies, `tasks.md` Verification header, `.agents/RECORD.md` (64 lines, gallery `(synth)` entry present, both deploy entries absent), `git diff --stat 23f70da..HEAD` (4 files, docs-only: RECORD gallery +1, README, EVAL_NOTES, HANDOFF; zero changes to Dockerfile/modal_app.py/vercel.json/backend/frontend).

- Plan implies fresh container probes, but Phase 2 proved them green at 23f70da (`test(deploy): local verification green`) and no code/wiring changed since — re-running is redundant unless the image/container is gone. Scoped task 1 to confirm Phase-2 evidence + tree-clean instead of a full re-run.
- Task 2 names no exact grep patterns; plan says only "no `sk-`/Bearer/key patterns in `frontend/dist`" plus Dockerfile secrets check (`COPY .env`, key patterns). Pinned the exact patterns into the task line; risks.md false-positive warning still applies (read hits, don't just count).
- "README commands followed verbatim up to the credential boundary" is unbounded — Phase 3 already ran the reader test on the rewritten README; Verification only confirms that result stands (README changed only in Phase 3 itself, nothing after). Scoped task 2 to confirm, not redo.
- "404s" (plural) in tasks.md vs plan's single unknown-profile-404 case (plus traversal-block which is a 403/404-shape guard). Clarified task 1 lists the exact five Phase-2 probes: health, inspect, overlay fetch, traversal block, unknown-profile 404.
- Phase-3 gallery RECORD entry could be misread as satisfying the Record Updates task; it is a separate `(synth)` entry and neither satisfies nor conflicts with the 2 pending `(deploy)` entries, which remain absent and still gated on the implementation review. Left task 3 wording intact, no divergence.
- Whether the Docker daemon/image from Phase 2 still exists for a confirmatory re-probe cannot be settled by reading. Added a risk line.

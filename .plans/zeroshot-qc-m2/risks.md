# ZeroShot QC — M2 Risks

- Label text (`id` + label near bbox origin) may be illegible or overlap on dense/small detections over tinted regions (`backend/app/pipeline/overlay.py`, new). Check: eyeball overlays from the manual CLI runs on real MVTec images (Manual checks task).
- Smoke count lines print from all `RawMask`s but detection ids (`d1...`) are dense over kept masks, so a skipped undecodable/mismatched mask makes counts and overlay/judge ids diverge (`backend/scripts/smoke.py:104-131`). Check: feed one corrupt-RLE mask through `_masks_to_detections` + `make_overlay` and compare the count line to the drawn ids.
- If the verification machine has `.env`/keys set, the literal (no-`--fake`) CLI run attempts a real Meta API call — cost, latency, flakiness — instead of the clean no-keys error (`cli.py:36`, `backend/app/adapters/base.py:24-29`). Check: unit inspects env for keys before run (a) and skips-or-adapts it when set.
- Real-SAM RLE byte-vs-text form stays open (M1 risk, `plan.md:50`); `--fake` verification proves only the text form fakes and the union-mask re-encode emit. Check: manual CLI run on real MVTec images with keys set (Manual checks task).

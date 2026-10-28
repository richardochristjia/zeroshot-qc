# ZeroShot QC — M5 Risks

- DIFF_THRESHOLD 25.0 in backend/app/synth/generate.py is unvalidated against real image-model output; faint defects could vanish via the empty-diff path or noise could bloat masks. Check: generate with the real model (manual criterion) and eyeball mask tightness.
- Eval on the fake's all-defective synth pairs scores F1 1.0 in every mode by construction, so the numbers prove plumbing, not judge quality. Check: rerun --data synth on real-model pairs once they exist.
- Synth _reference.png falls back to the committed fixture good image when the profile sets no reference_image, so reference-backed judge runs on synth compare against flat gray, not real product variation. Check: set profile reference_image values from real MVTec train/good images.
- The real Muse Image request/response mapping stays TODO(meta-docs) in backend/app/adapters/muse_image.py until the official docs arrive; the correction is one function. Check: docs review before the manual real-model generation.

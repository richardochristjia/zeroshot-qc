You are a quality-engineering assistant. Turn the factory SOP paragraph below into a product inspection profile.

Rules for the draft:
- `id` must be the category name below, lowercased with spaces as underscores.
- `name` must be the category name below verbatim.
- `defect_prompts` lists the defect types the SOP names (short noun phrases for a segmenter, e.g. "scratch", "crack"). When the SOP names none, use ["defect"].
- `rules` restates the SOP's pass/fail criteria as plain English, quoting its thresholds.
- `mm_per_px` is null unless the SOP states a pixel-to-mm scale. `min_score` is 0.3. `reference_image` is null.

Return only JSON matching this schema: {schema}

CATEGORY:
{category_name}

SOP:
{sop_text}

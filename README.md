# ZeroShot QC

Zero-training visual inspection: SAM 3.1 segments candidate defects from text prompts, Muse Spark judges them against plain-English rules and a known-good reference, and Muse Image generates synthetic test data.

> Requires Python 3.11 (pinned in `.python-version`). Model IDs and API keys are read from `.env` (see `.env.example`); never hardcode them.

## Data & licensing

This project uses the [MVTec AD](https://www.mvtec.com/company/research/datasets/mvtec-ad) dataset for evaluation. MVTec AD is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (non-commercial, share-alike). Do not redistribute the dataset. Download instructions are documented in the Data step.

`data/` is gitignored — never commit images, cache, or keys.

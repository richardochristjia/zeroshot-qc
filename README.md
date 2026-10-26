# ZeroShot QC

Zero-training visual inspection: SAM 3.1 segments candidate defects from text prompts, Muse Spark judges them against plain-English rules and a known-good reference, and Muse Image generates synthetic test data.

> Requires Python 3.11 (pinned in `.python-version`). Model IDs and API keys are read from `.env` (see `.env.example`); never hardcode them.

## Data & licensing

This project uses the [MVTec AD](https://www.mvtec.com/company/research/datasets/mvtec-ad) dataset for evaluation. MVTec AD is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (non-commercial, share-alike). Do not redistribute the dataset. To download it, open the official [MVTec AD](https://www.mvtec.com/company/research/datasets/mvtec-ad) page in a web browser, accept the CC BY-NC-SA 4.0 terms on the site, and download the archive manually — there is no direct or scripted (`curl`/`wget`) download URL.

Extract the archive into the repo-root `data/mvtec/` directory (the default `MVTEC_DIR` from `.env.example`, resolved from the repo root; set `MVTEC_DIR` in `.env` to override it) so its category folders sit directly under `data/mvtec/`. `data/mvtec/` is the canonical dataset location, not the only path smoke can read. Smoke needs at least 3 `*.png`/`*.jpg`/`*.jpeg` images anywhere beneath `data/mvtec/` — discovery is recursive.

Verify with `cd backend && python scripts/smoke.py --fake` (needs no dataset or keys). The real run, `cd backend && python scripts/smoke.py`, additionally needs the dataset present plus `.env` keys (see `.env.example`).

`data/` is gitignored — never commit images, cache, or keys.

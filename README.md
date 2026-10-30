# ZeroShot QC

Zero-training visual inspection: SAM 3.1 segments candidate defects from text prompts, Muse Spark judges them against plain-English rules and a known-good reference, and Muse Image generates synthetic test data.

## Run it

You need [Docker](https://docs.docker.com/get-docker/) with the daemon running. No API key and no `.env` are required.

```sh
git clone <this repo>
cd <repo folder>
docker compose up --build
```

Open http://localhost:8080. Every page is already populated from a bundled demo set.

## What to try

- **Inspect**: click a "Try a sample" thumbnail. It picks the profile and returns a real SAM + Muse Spark verdict, replayed from cache. Edit the rules box to re-judge; with no key, edits and your own uploads return a placeholder verdict with a "Demo result" banner.
- **Eval**: three evaluation runs with failure thumbnails.
- **Synthetic**: generated bottle defect pairs with masks.
- **Profiles**: product profiles with their reference images.

## Live models (optional)

To run real inspections on your own images, add a key:

```sh
cp .env.example .env
# set META_API_KEY in .env
docker compose up --build
```

## Stop and reset

```sh
docker compose down      # stop, keep data
docker compose down -v   # stop and wipe data; the bundle reseeds on the next start
```

## Data & licensing

The bundled demo set includes a downscaled subset of the [MVTec AD](https://www.mvtec.com/company/research/datasets/mvtec-ad) dataset, (c) MVTec Software GmbH, redistributed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) with attribution (`backend/demo/LICENSE-MVTEC.md`). Non-commercial use only; derivatives keep the same licence. Never commit API keys.

## Development

Manual run, container probes and the submission checklist: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

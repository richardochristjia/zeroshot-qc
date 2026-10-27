# Risks

- `backend/requirements.txt` pins `opencv-python-headless`, `pycocotools`, `numpy`, `Pillow`; whether they install on `python:3.11-slim` without extra system libs or a compiler cannot be settled by reading. Check: Phase 2 `docker build` succeeds.
- `modal`/`vercel` CLI behavior (ASGI construct names, static-output config keys) cannot be settled without the CLIs or docs here. Check: validate `modal_app.py`/`vercel.json` against installed CLI `--help`/docs at push time.
- `Dockerfile` was syntax/read-validated only here — `docker` CLI exists but the daemon is down (`Cannot connect to the Docker daemon`), so no `docker build` ran in this unit. Check: Phase 2 local-verification `docker build` must pass.
- `modal_app.py` decorator shape (`modal.App.function(image=...)(modal.asgi_app()(…))`, `modal.Image.debian_slim()`) written from the plan without the `modal` package or credentials here — import path validated (`modal=None`, same `app` object, clear RuntimeError on deploy path) but the Modal ASGI construct names cannot be settled. Check: `pip install modal` + `modal setup` then `modal serve modal_app.py` at push time; adjust to installed-SDK spelling if names differ.

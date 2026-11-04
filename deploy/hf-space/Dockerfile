# Dockerfile for the Hugging Face Space Xenonsense/zeroshot-qc.
# It is never given META_API_KEY, so the app replays cached verdicts.
# Local check: docker build deploy/hf-space --build-arg REF=<branch>

FROM node:20-alpine AS web
ARG REPO=https://github.com/richardochristjia/zeroshot-qc.git
ARG REF=main
RUN apk add --no-cache git
# Busts the layer cache whenever the branch head moves.
ADD https://api.github.com/repos/richardochristjia/zeroshot-qc/git/refs/heads/${REF} /tmp/ref.json
RUN git clone --depth 1 --branch "$REF" "$REPO" /src
WORKDIR /src/frontend
RUN npm ci && npm run build

FROM python:3.11-slim
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/home/user/data \
    FRONTEND_DIR=/home/user/web \
    SAM_MODEL_ID=sam-3.1 \
    JUDGE_MODEL_ID=muse-spark-1.3 \
    IMAGE_MODEL_ID=muse-image-1.0
WORKDIR /home/user/app
COPY --from=web --chown=user /src/backend /home/user/app
COPY --from=web --chown=user /src/frontend/dist /home/user/web
RUN pip install --no-cache-dir --user -r requirements.txt && mkdir -p /home/user/data
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]

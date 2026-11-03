# Media Downloader Hub - web API + site
# Builds on amd64 and arm64 (Oracle Cloud Ampere A1). Build context: repository root.
FROM denoland/deno:bin AS deno

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HF_HOME=/models \
    DATA_DIR=/data

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*

# yt-dlp needs a JavaScript runtime (Deno) for YouTube's signature challenges
COPY --from=deno /deno /usr/local/bin/deno

RUN useradd --create-home --uid 10001 app \
 && python -m venv /opt/venv \
 && mkdir -p /data /models \
 && chown -R app:app /opt/venv /data /models

WORKDIR /app
COPY --chown=app:app requirements-server.txt .
USER app
RUN pip install -r requirements-server.txt

COPY --chown=app:app downloader/ downloader/
COPY --chown=app:app subtitle/ subtitle/
COPY --chown=app:app backend/ backend/
COPY --chown=app:app web/ web/
COPY --chown=app:app deploy/entrypoint.sh /app/entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

ENTRYPOINT ["/usr/bin/tini", "--", "sh", "/app/entrypoint.sh"]

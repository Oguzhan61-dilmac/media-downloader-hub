#!/bin/sh
# YouTube changes often and yt-dlp follows within days, so update on every start.
# The host restarts this container once a day (cron from the cloud-init script).
if [ "${AUTO_UPDATE_YTDLP:-1}" = "1" ]; then
  if [ "${YTDLP_CHANNEL:-nightly}" = "nightly" ]; then
    PRE="--pre"
  else
    PRE=""
  fi
  echo "[entrypoint] yt-dlp güncelleniyor (${YTDLP_CHANNEL:-nightly})..."
  pip install -q -U $PRE "yt-dlp[default]" bgutil-ytdlp-pot-provider \
    || echo "[entrypoint] Güncelleme başarısız, mevcut sürümle devam ediliyor."
fi
python -c "import yt_dlp; print('[entrypoint] yt-dlp', yt_dlp.version.__version__)"

# --no-access-log: visitor IPs are not written to logs (see web/gizlilik.html)
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --no-access-log \
  --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 30

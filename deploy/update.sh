#!/bin/bash
# Pull the latest code from GitHub and rebuild. Run on the server:
#   sudo bash /opt/media-downloader-hub/deploy/update.sh
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
cd deploy
docker compose up -d --build
docker compose ps

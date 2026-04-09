#!/usr/bin/env bash
set -euo pipefail
source .env 2>/dev/null || true
if [ "${CAPTIONING_ENABLED:-true}" = "false" ]; then
  docker compose up --build gateway docling libreoffice
else
  docker compose up --build
fi

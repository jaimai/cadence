#!/usr/bin/env bash
# Install or update the API on alwaysdata. Run it over SSH, from anywhere:
#
#   ~/cadence/apps/api/deploy/alwaysdata.sh
#
# Safe to run again: it only pulls, installs what changed and applies new migrations.
# Restart the site and the worker service afterwards (admin panel, or the API below).
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Fichier .env manquant : copie deploy/env.alwaysdata.example vers .env et remplis-le." >&2
  exit 1
fi

git pull --ff-only

if [ ! -d .venv ]; then
  python -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

.venv/bin/alembic upgrade head

echo "À jour. Redémarre le site et le service worker pour charger le nouveau code."

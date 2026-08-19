#!/usr/bin/env bash
# รันแอป ระบบรับของบริจาค 7-Eleven (gunicorn)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export GIFT_BIND="${GIFT_BIND:-0.0.0.0}"
export GIFT_PORT="${GIFT_PORT:-8110}"
export GIFT_DB="${GIFT_DB:-$ROOT/data/gift_logger.db}"
export GIFT_DATA_DIR="${GIFT_DATA_DIR:-$ROOT/data}"
if [[ -f /etc/seven-gift-logger.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/seven-gift-logger.env
  set +a
fi
exec "$ROOT/.venv/bin/gunicorn" \
  --workers "${GIFT_WORKERS:-2}" \
  --bind "${GIFT_BIND}:${GIFT_PORT}" \
  --access-logfile - \
  --error-logfile - \
  wsgi:app

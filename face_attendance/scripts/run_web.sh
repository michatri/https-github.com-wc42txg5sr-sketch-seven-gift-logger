#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONPATH="$(cd "$ROOT/.." && pwd)${PYTHONPATH:+:$PYTHONPATH}"
exec python -m uvicorn face_attendance.web.app:app --host 0.0.0.0 --port 8080

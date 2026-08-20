#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"

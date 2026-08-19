#!/usr/bin/env bash
# ตรวจ chatriACC บนเครื่องเซิร์ฟเวอร์ เมื่อ service ขึ้น Failed
set -euo pipefail
PORT="${CHATRIACC_PORT:-8100}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "== hostname =="; hostname; hostname -I; uname -a; python3 --version || true
echo "== unit =="; systemctl cat chatriacc || true
echo "== status =="; systemctl --no-pager --full status chatriacc || true
echo "== journal =="; journalctl -u chatriacc -n 80 --no-pager || true
echo "== listening =="; ss -lntp | grep -E ":${PORT}|:8100|:8110|:80[[:space:]]|:8090" || true
echo "== files ==";
ls -ld "$ROOT" "$ROOT/scripts/chatriacc-run.sh" "$ROOT/.venv/bin/gunicorn" "$ROOT/.venv/bin/python" 2>&1 || true
echo "== import ==";
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -c "from chatriacc.wsgi import app; print('ok', app.name)" || true
else
  echo "ไม่มี $ROOT/.venv/bin/python"
fi
echo "== health ${PORT} =="; curl -sv --max-time 5 "http://127.0.0.1:${PORT}/health" || true
echo "== health 8110 =="; curl -sv --max-time 5 "http://127.0.0.1:8110/health" || true
echo "== env file =="; if [[ -f /etc/chatriacc.env ]]; then grep -v SECRET /etc/chatriacc.env; else echo "ไม่มี /etc/chatriacc.env"; fi
echo "== ufw =="; ufw status || true

#!/usr/bin/env bash
# ตรวจ chatriACC บนเครื่องเซิร์ฟเวอร์
set -euo pipefail
PORT="${CHATRIACC_PORT:-8090}"
echo "== hostname =="; hostname; uname -a
echo "== listening =="; ss -lntp | grep -E ":${PORT}|:80[[:space:]]" || true
echo "== systemd =="; systemctl --no-pager --full status chatriacc || true
echo "== health =="; curl -sv --max-time 5 "http://127.0.0.1:${PORT}/health" || true
echo "== journal =="; journalctl -u chatriacc -n 40 --no-pager || true
echo "== ufw =="; ufw status || true

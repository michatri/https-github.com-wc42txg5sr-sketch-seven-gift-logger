#!/usr/bin/env bash
set -euo pipefail
echo "== hostname: $(hostname)"
echo "== IPs: $(hostname -I 2>/dev/null || true)"
echo "== user: $(id)"
echo "== unit:"
systemctl --no-pager --full status seven-gift-logger || true
echo "== ports:"
ss -lntp | grep -E ':8110|:8120|:8130|:8100|:8090|:8080' || true
echo "== health:"
curl -sS http://127.0.0.1:8110/health || curl -sS http://127.0.0.1:8120/health || true
echo
echo "== env file:"
ls -l /etc/seven-gift-logger.env 2>/dev/null || echo "(no env file)"

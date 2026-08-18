#!/usr/bin/env bash
# คลอนและติดตั้งระบบบัญชีสำหรับ user aaa บน 192.168.10.56
# รันบนเซิร์ฟเวอร์:  bash scripts/bootstrap.sh
set -euo pipefail

BRANCH="cursor/accounting-payslip-cd50"
REPO_URL="https://github.com/michatri/https-github.com-wc42txg5sr-sketch-seven-gift-logger.git"
APP_USER="${SUDO_USER:-${USER}}"
if [[ "$APP_USER" == "root" && -d /home/aaa ]]; then
  APP_USER="aaa"
fi
HOME_DIR="$(getent passwd "$APP_USER" | cut -d: -f6)"
DEST="${ACCOUNTING_HOME:-${HOME_DIR}/accounting}"

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

echo "==> ติดตั้งให้ user ${APP_USER} ที่ ${DEST}"
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq git python3 python3-venv python3-pip curl >/dev/null

if [[ -d "$DEST/.git" ]]; then
  echo "==> อัปเดต repo ที่มีอยู่"
  git -C "$DEST" fetch origin
  git -C "$DEST" checkout "$BRANCH"
  git -C "$DEST" pull --ff-only origin "$BRANCH"
else
  echo "==> clone $BRANCH"
  rm -rf "$DEST"
  git clone -b "$BRANCH" "$REPO_URL" "$DEST"
fi

$SUDO chown -R "$APP_USER:$APP_USER" "$DEST"
chmod +x "$DEST/scripts/install_on_server.sh" "$DEST/scripts/diagnose_server.sh"
$SUDO "$DEST/scripts/install_on_server.sh"

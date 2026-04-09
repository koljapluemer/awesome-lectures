#!/usr/bin/env bash
# Deploy latest code. Run as root on the droplet.
# See deploy/DEPLOY.md for the full guide.
set -euo pipefail

DEPLOY_DIR="/srv/awesome-lectures"
APP_USER="al"

echo "==> Pulling latest code"
cd "$DEPLOY_DIR"
git pull

echo "==> Syncing dependencies"
cd "$DEPLOY_DIR/backend"
sudo -u "$APP_USER" /home/"$APP_USER"/.local/bin/uv sync

echo "==> Restarting service"
systemctl restart al-backend
systemctl status al-backend --no-pager

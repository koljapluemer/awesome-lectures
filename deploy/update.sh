#!/usr/bin/env bash
# Run on the droplet to pull latest code and restart the service.
set -euo pipefail

cd /srv/awesome-lectures
git pull

cd backend
sudo -u al /home/al/.local/bin/uv sync

systemctl restart al-backend
echo ">>> Updated and restarted"

#!/usr/bin/env bash
# Run once on a fresh Ubuntu droplet as root.
set -euo pipefail

# Create dedicated user
useradd -r -s /bin/bash -m al

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | HOME=/home/al sudo -u al bash -s

# Clone repo
git clone https://github.com/koljapluemer/awesome-lectures /srv/awesome-lectures
chown -R al:al /srv/awesome-lectures

# Install Python deps (includes gunicorn)
cd /srv/awesome-lectures/backend
sudo -u al /home/al/.local/bin/uv add gunicorn
sudo -u al /home/al/.local/bin/uv sync

# Create .env (fill in values after running this script)
if [ ! -f /srv/awesome-lectures/backend/.env ]; then
  cp /srv/awesome-lectures/backend/.env.example /srv/awesome-lectures/backend/.env 2>/dev/null || \
  cat > /srv/awesome-lectures/backend/.env <<'EOF'
SECRET_KEY=change-me
ALLOWED_ORIGINS=https://yoursite.netlify.app
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
ALLOWED_MODERATORS=
EOF
  echo ">>> Edit /srv/awesome-lectures/backend/.env before starting the service"
fi

# Install and enable systemd service
cp /srv/awesome-lectures/deploy/al-backend.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable al-backend

# Open port 5000
ufw allow 5000/tcp

echo ">>> Setup done. Fill in .env then: systemctl start al-backend"

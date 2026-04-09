#!/usr/bin/env bash
# Initial server setup. Run once as root on a fresh Ubuntu 22.04+ droplet.
# See deploy/DEPLOY.md for the full guide.
set -euo pipefail

REPO="git@github.com:koljapluemer/awesome-lectures.git"
DEPLOY_DIR="/srv/awesome-lectures"
APP_USER="al"

echo "==> Creating system user '$APP_USER'"
useradd --system --shell /bin/bash --create-home "$APP_USER"

echo "==> Installing uv"
curl -LsSf https://astral.sh/uv/install.sh | HOME="/home/$APP_USER" sudo -u "$APP_USER" bash -s

echo "==> Cloning repository"
git clone "$REPO" "$DEPLOY_DIR"
chown -R "$APP_USER:$APP_USER" "$DEPLOY_DIR"

echo "==> Installing Python dependencies"
cd "$DEPLOY_DIR/backend"
sudo -u "$APP_USER" /home/"$APP_USER"/.local/bin/uv sync

echo "==> Creating .env"
cat > "$DEPLOY_DIR/backend/.env" <<'EOF'
# Generate a strong random value: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=

# Your Netlify frontend URL, e.g. https://awesome-lectures.netlify.app
ALLOWED_ORIGINS=

# GitHub OAuth app credentials (github.com/settings/developers)
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# The repo that holds lecture data, e.g. koljapluemer/awesome-lectures
GITHUB_REPO=
GITHUB_BRANCH=main

# Comma-separated GitHub usernames that can access /admin
ALLOWED_MODERATORS=

# Path to SQLite database file
DATABASE=/srv/awesome-lectures/backend/lectures.db
EOF
chown "$APP_USER:$APP_USER" "$DEPLOY_DIR/backend/.env"
chmod 600 "$DEPLOY_DIR/backend/.env"

echo "==> Installing systemd service"
cp "$DEPLOY_DIR/deploy/al-backend.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable al-backend

echo "==> Configuring firewall"
ufw allow OpenSSH
ufw allow 5000/tcp
ufw --force enable

echo ""
echo "==> Done. Fill in $DEPLOY_DIR/backend/.env, then run:"
echo "    systemctl start al-backend"

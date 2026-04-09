# Deployment Guide

The backend is a Flask app served by gunicorn, running as a systemd service on a Ubuntu 22.04 droplet.

---

## First-time setup

### 1. Create a Digital Ocean droplet

- Ubuntu 22.04 LTS
- Any size (the smallest works)
- Add your SSH key during creation

### 2. Set up a GitHub deploy key

On the droplet (as root):

```bash
ssh-keygen -t ed25519 -f /root/.ssh/deploy_key -N ""
cat /root/.ssh/deploy_key.pub
```

Add the printed public key to GitHub:
**Repository → Settings → Deploy keys → Add deploy key** (read-only, no write access needed).

Then tell SSH to use it. Create `/root/.ssh/config`:

```
Host github.com
    IdentityFile /root/.ssh/deploy_key
    StrictHostKeyChecking accept-new
```

### 3. Run the setup script

```bash
curl -fsSL https://raw.githubusercontent.com/koljapluemer/awesome-lectures/main/deploy/setup.sh | bash
```

This will:
- Create a dedicated `al` system user
- Install uv
- Clone the repo to `/srv/awesome-lectures`
- Install all Python dependencies (including gunicorn)
- Create a `.env` template at `/srv/awesome-lectures/backend/.env`
- Install and enable the systemd service
- Open port 5000 in the firewall

### 4. Fill in the .env

```bash
nano /srv/awesome-lectures/backend/.env
```

All values are documented inside the file. At minimum you must set:
- `SECRET_KEY` — generate with: `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `ALLOWED_ORIGINS` — your Netlify frontend URL

### 5. Start the service

```bash
systemctl start al-backend
```

### 6. Verify it's running

```bash
systemctl status al-backend
curl http://localhost:5000/health
```

The API is now reachable at `http://YOUR_DROPLET_IP:5000`.

---

## Deploying updates

On the droplet (as root):

```bash
bash /srv/awesome-lectures/deploy/update.sh
```

This pulls the latest code, syncs dependencies, and restarts the service.

---

## Useful commands

```bash
# View live logs
journalctl -u al-backend -f

# Restart the service
systemctl restart al-backend

# Check service status
systemctl status al-backend
```

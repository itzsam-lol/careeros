#!/usr/bin/env bash
# One-time (idempotent) setup of a fresh Ubuntu VM for CareerOS. Run on the VM as a sudoer:
#   bash /opt/careeros/current/infrastructure/vm/bootstrap.sh <public-ip> [acme-email]
set -euo pipefail

PUBLIC_IP="${1:?usage: bootstrap.sh <public-ip> [acme-email]}"
ACME_EMAIL="${2:-}"
APP_DIR=/opt/careeros
ENV_FILE="$APP_DIR/.env.production"

echo "==> Docker"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
sudo usermod -aG docker "$USER" || true
sudo systemctl enable --now docker

echo "==> Swap (builds need headroom on small VMs)"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "==> Secrets"
sudo mkdir -p "$APP_DIR/backups"
sudo chown -R "$USER":"$USER" "$APP_DIR"
DOMAIN="$(echo "$PUBLIC_IP" | tr '.' '-').sslip.io"
if [ ! -f "$ENV_FILE" ]; then
  umask 077
  cat >"$ENV_FILE" <<EOF
# Generated on $(date -u +%FT%TZ). Keep this file private; it never leaves the VM.
DOMAIN=$DOMAIN
ACME_EMAIL=$ACME_EMAIL
POSTGRES_PASSWORD=$(openssl rand -hex 24)
AUTH_MODE=password
SIGNING_SECRET=$(openssl rand -base64 48 | tr -d '\n')
ENCRYPTION_KEY=$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')
INTERNAL_AUTH_MODE=token
INTERNAL_API_TOKEN=$(openssl rand -hex 32)
LOG_LEVEL=INFO
EOF
  echo "created $ENV_FILE (DOMAIN=$DOMAIN)"
else
  echo "$ENV_FILE already exists; leaving it untouched"
fi

echo "==> Nightly database backups"
sudo tee /etc/systemd/system/careeros-backup.service >/dev/null <<EOF
[Unit]
Description=CareerOS Postgres backup

[Service]
Type=oneshot
User=$USER
ExecStart=/bin/bash $APP_DIR/current/infrastructure/vm/backup.sh
EOF
sudo tee /etc/systemd/system/careeros-backup.timer >/dev/null <<'EOF'
[Unit]
Description=Nightly CareerOS backup

[Timer]
OnCalendar=*-*-* 02:30:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now careeros-backup.timer

echo "==> Done. Deploy with scripts/deploy.py from your machine."

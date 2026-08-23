#!/usr/bin/env bash
#
# One-command install on a fresh Ubuntu/Debian VPS.
#
#   sudo bash deploy/install.sh yourdomain.com
#
# Sets up: a dedicated system user, the app under /opt, a systemd service,
# Caddy with automatic HTTPS, the email worker on cron, and nightly database
# backups. Safe to re-run - every step checks before it acts.
#
# It will NOT start the public site until preflight.py passes, so an unfilled
# licence number or a default admin key stops the deploy rather than shipping.

set -euo pipefail

DOMAIN="${1:-}"
APP_USER="leadmagnet"
APP_DIR="/opt/coverage-gap-finder"
ENV_FILE="/etc/coverage-gap-finder.env"
BACKUP_DIR="/var/backups/coverage-gap-finder"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

say()  { printf '\n\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\n\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31mXX\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run with sudo."
[[ -n "$DOMAIN" ]] || die "Usage: sudo bash deploy/install.sh yourdomain.com"
[[ -f "$SRC_DIR/server.py" ]] || die "Run this from inside the lead-magnet directory."

# --- 1. packages ---------------------------------------------------------
say "Installing packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 sqlite3 curl rsync gnupg \
    debian-keyring debian-archive-keyring apt-transport-https

if ! command -v caddy >/dev/null 2>&1; then
    say "Installing Caddy"
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
        > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy
else
    say "Caddy already installed"
fi

python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
    || die "Python 3.10+ required; this box has $(python3 -V)."

# --- 2. user and files ---------------------------------------------------
if ! id "$APP_USER" >/dev/null 2>&1; then
    say "Creating system user $APP_USER"
    adduser --system --group --no-create-home --home "$APP_DIR" "$APP_USER"
fi

say "Installing app to $APP_DIR"
mkdir -p "$APP_DIR"
# Preserve a live agency.json and lead database across re-runs.
[[ -f "$APP_DIR/agency.json" ]] && cp "$APP_DIR/agency.json" /tmp/agency.keep.json
rsync -a --delete \
      --exclude '.git' --exclude '__pycache__' --exclude 'leads.db*' \
      --exclude 'agency.json' \
      "$SRC_DIR/" "$APP_DIR/"
if [[ -f /tmp/agency.keep.json ]]; then
    mv /tmp/agency.keep.json "$APP_DIR/agency.json"
    say "Kept your existing agency.json"
else
    cp "$SRC_DIR/agency.json" "$APP_DIR/agency.json"
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# --- 3. secrets ----------------------------------------------------------
if [[ ! -f "$ENV_FILE" ]]; then
    say "Creating $ENV_FILE with a generated ADMIN_KEY"
    ADMIN_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"
    cat > "$ENV_FILE" <<ENVEOF
# Secrets for the Coverage Gap Finder. Keep this file at mode 600.
ADMIN_KEY=$ADMIN_KEY

# Email sending. Fill these in, then: systemctl restart coverage-gap-finder
# See content/EMAIL-SETUP.md - SPF and DKIM must be in DNS first.
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=
ENVEOF
    chmod 600 "$ENV_FILE"
else
    say "Keeping existing $ENV_FILE"
fi

# --- 4. systemd ----------------------------------------------------------
say "Installing systemd service"
install -m 644 "$APP_DIR/deploy/coverage-gap-finder.service" \
        /etc/systemd/system/coverage-gap-finder.service
systemctl daemon-reload

# --- 5. caddy ------------------------------------------------------------
say "Configuring Caddy for $DOMAIN"
sed -e "s/yourdomain\.com, www\.yourdomain\.com/$DOMAIN, www.$DOMAIN/" \
    "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
warn "The Caddyfile IP-gates /admin to 203.0.113.4 (a placeholder)."
warn "Edit /etc/caddy/Caddyfile and put your own IP there, or remove that block."

# --- 6. cron -------------------------------------------------------------
say "Scheduling the email worker and nightly backups"
mkdir -p "$BACKUP_DIR"
chown "$APP_USER:$APP_USER" "$BACKUP_DIR"
cat > /etc/cron.d/coverage-gap-finder <<CRONEOF
# Managed by deploy/install.sh
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

*/15 * * * * $APP_USER cd $APP_DIR && /usr/bin/python3 send_worker.py >> /var/log/coverage-gap-finder-worker.log 2>&1
17 3 * * *   $APP_USER cd $APP_DIR && /usr/bin/sqlite3 leads.db ".backup '$BACKUP_DIR/leads-\$(date +\%F).db'" && find $BACKUP_DIR -name 'leads-*.db' -mtime +30 -delete
CRONEOF
chmod 644 /etc/cron.d/coverage-gap-finder

# --- 7. the gate ---------------------------------------------------------
say "Running preflight"
set +e
( cd "$APP_DIR" && set -a && . "$ENV_FILE" && set +a \
  && sudo -u "$APP_USER" --preserve-env=ADMIN_KEY,SMTP_HOST,SMTP_FROM,SMTP_USER \
     /usr/bin/python3 preflight.py --skip-tests )
PREFLIGHT=$?
set -e

if [[ $PREFLIGHT -ne 0 ]]; then
    warn "Preflight found blocking issues. The site was NOT started."
    echo
    echo "  Fix them, then finish the install:"
    echo "    cd $APP_DIR && sudo -u $APP_USER python3 configure.py"
    echo "    sudo systemctl enable --now coverage-gap-finder"
    echo "    sudo systemctl reload caddy"
    echo
    exit 1
fi

say "Starting services"
systemctl enable --now coverage-gap-finder
systemctl reload caddy || systemctl restart caddy

sleep 2
if systemctl is-active --quiet coverage-gap-finder; then
    say "Live at https://$DOMAIN"
    echo
    echo "  Admin:    https://$DOMAIN/admin?key=\$(sudo grep ADMIN_KEY $ENV_FILE | cut -d= -f2)"
    echo "  Logs:     sudo journalctl -u coverage-gap-finder -f"
    echo "  Backups:  $BACKUP_DIR"
    echo
    echo "  Next: run the smoke test in content/DEPLOY.md before you send"
    echo "        anyone to this link."
else
    die "Service failed to start. Check: journalctl -u coverage-gap-finder -n 50"
fi

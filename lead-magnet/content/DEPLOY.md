# Deploying the Coverage Gap Finder

Three steps, in this order. Don't skip the preflight — it's the gate that stops
a page going live with an unfilled license number or a default admin key.

```bash
python3 configure.py    # 1. your agency details -> agency.json
python3 preflight.py    # 2. verify nothing is left as a placeholder
                        # 3. pick a host below
```

`preflight.py` exits non-zero while anything is blocking, so you can wire it
into a deploy script and it will refuse to ship a misconfigured site.

---

## What you need first

| | Why |
|---|---|
| A domain | Report links in emails are absolute. Without one, nothing in the sequence works. |
| A host | Anything that runs Python 3.10+. The app has no dependencies. |
| An email sender | SMTP credentials, plus SPF and DKIM on the sending domain. See `EMAIL-SETUP.md`. |
| Compliance sign-off | See `COMPLIANCE.md`. This is a human step, not a technical one. |

**Do the SPF/DKIM part before you send to anyone.** Without them the sequence
lands in spam, and a domain that starts out in spam folders is hard to
rehabilitate. `EMAIL-SETUP.md` walks through provider choice, the three DNS
records, and how to verify placement before you promote the link anywhere.

---

## Option A — Ubuntu VPS, one command (recommended)

On a fresh Ubuntu or Debian box, with your domain's A record already pointing
at its IP:

```bash
git clone <your-repo> ~/coverage-gap-finder
cd ~/coverage-gap-finder/lead-magnet
sudo bash deploy/install.sh yourdomain.com
```

That installs Python and Caddy, creates a `leadmagnet` system user, puts the
app in `/opt/coverage-gap-finder`, generates a random `ADMIN_KEY`, installs the
systemd service, configures HTTPS, and schedules the email worker and nightly
database backups.

**It stops before starting the public site if preflight fails** — so an
unfilled license number or a default admin key blocks the deploy rather than
shipping. On a fresh install that's expected: fill in your details, then
finish.

```bash
cd /opt/coverage-gap-finder
sudo -u leadmagnet python3 configure.py
sudo systemctl enable --now coverage-gap-finder
sudo systemctl reload caddy
```

Two things the script deliberately leaves to you:

- **The admin IP gate.** `/etc/caddy/Caddyfile` restricts `/admin` to a
  placeholder IP. Put your own there, or delete the block if you need access
  from anywhere. Then `sudo systemctl reload caddy`.
- **Email credentials.** `/etc/coverage-gap-finder.env` has empty SMTP fields.
  See `EMAIL-SETUP.md` — the DNS records come first.

Re-running the script is safe. It preserves your `agency.json`, your lead
database, and your env file.

## Option B — Docker (works on Railway, Render, Fly, or any Docker host)

Simplest if your host speaks Docker. The lead database lives on a volume, so
redeploys don't destroy it.

```bash
cd deploy
cp coverage-gap-finder.env .env      # then edit it - real values
docker compose up -d
```

That runs two containers: the site, and a worker that drains the email queue
every 15 minutes.

On a PaaS, point the build at `deploy/Dockerfile`, set the same environment
variables in the dashboard, and **attach a persistent volume at `/data`**. Most
PaaS filesystems are ephemeral — without the volume you lose every lead on each
deploy.

## Option C — A VPS, step by step

What `install.sh` does, if you'd rather do it by hand or adapt it.

```bash
# as root on a fresh Ubuntu box
adduser --system --group leadmagnet
git clone <your-repo> /opt/coverage-gap-finder
chown -R leadmagnet:leadmagnet /opt/coverage-gap-finder

cp deploy/coverage-gap-finder.env /etc/coverage-gap-finder.env
chmod 600 /etc/coverage-gap-finder.env      # secrets - lock it down
nano /etc/coverage-gap-finder.env           # fill in real values

cp deploy/coverage-gap-finder.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now coverage-gap-finder
systemctl status coverage-gap-finder
```

Then HTTPS, which Caddy does automatically:

```bash
apt install caddy
cp deploy/Caddyfile /etc/caddy/Caddyfile
nano /etc/caddy/Caddyfile        # your domain, and your IP in the admin block
systemctl reload caddy
```

Point your domain's A record at the server **before** reloading Caddy —
certificate issuance checks DNS.

Finally the email worker and backups:

```bash
sudo -u leadmagnet crontab -e     # paste deploy/crontab.example
```

## Option D — Your existing web host

If you already pay for hosting that supports Python (a cPanel host, a
university box, a home server), it will run this. You need: Python 3.10+, the
ability to keep a long-running process alive, and a reverse proxy for HTTPS.
The systemd unit and Caddyfile in `deploy/` are the reference; adapt to
whatever process manager your host uses.

---

## After it's live — the 10-minute smoke test

Do all of this on the real domain before you send a single person to it.

1. **Run the quiz end to end** with your own email. Every step, submit.
2. **Check the report** renders at the link you were given, and that the footer
   shows your real name, license and address.
3. **Check the email arrives** — and check the spam folder. If it landed there,
   stop and fix SPF/DKIM before promoting the link anywhere.
4. **Click the unsubscribe link** in that email. Confirm it says you're
   unsubscribed and that no further emails arrive.
5. **Open `/admin?key=...`** and confirm your test lead is listed with the right
   score and source.
6. **Export the CSV** and open it.
7. **Delete your test lead** so it doesn't pollute your numbers:
   ```bash
   sqlite3 leads.db "DELETE FROM leads WHERE email='you@example.com';"
   ```
8. **Confirm `/admin` is not publicly reachable** — load it from your phone on
   cellular. It should 404 or demand the key.

---

## Once it's running

**Back up `leads.db`.** It is the entire business asset this system produces.
The cron example does a nightly SQLite backup with 30-day retention; make sure
those copies land somewhere off the server.

**Watch the source column, not the traffic.** `?src=` tags are the whole
analytics stack. After a month, two channels will be producing and four won't
— that's the signal to reallocate your time.

**Re-run preflight after any change** to config or environment.

## When something breaks

| Symptom | Cause |
|---|---|
| Emails never arrive | `SMTP_HOST` unset, or the worker isn't running. Run `python3 send_worker.py --dry-run` to see the queue. |
| Emails land in spam | SPF/DKIM missing or misaligned on the sending domain. |
| Report links 404 | `site_url` in `agency.json` doesn't match the live domain. |
| Leads vanished after deploy | No persistent volume. See Option A. |
| `/admin` returns 403 | Wrong `ADMIN_KEY`, or the process has a stale one — restart the service. |
| Placeholder text on the live page | `agency.json` wasn't deployed, or the service wasn't restarted after editing it. |

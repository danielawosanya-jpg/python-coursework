# Email Setup

**Do this before you send a single email.** A domain that starts out landing in
spam folders is hard to rehabilitate, and the entire nurture sequence — the
thing that turns a download into a conversation — depends on inbox placement.

The short version: pick a sending provider, add three DNS records, verify, warm
up slowly.

---

## 1. Pick a provider

Do **not** send from your own server. A fresh VPS IP has no sending reputation
and most inbox providers treat it as suspicious by default.

| Provider | Free tier | Notes |
|---|---|---|
| **Amazon SES** | 3,000 msgs/mo first year, then ~$0.10/1,000 | Cheapest at any volume. Starts in a sandbox — you must request production access, which takes a day. |
| **Postmark** | 100/mo free | Best deliverability of the group, genuinely good support. ~$15/mo after. |
| **Resend** | 3,000/mo free | Easiest setup, modern dashboard. |
| **Google Workspace** | No | If you already pay for it, you can send via SMTP with an app password. Fine at low volume, but it's a mailbox not a sending service — don't push a large list through it. |

For an agency starting organically, **SES or Resend**. You will not exceed a
free tier for months.

## 2. Add the DNS records

Three records on your sending domain. Your provider's dashboard gives you the
exact values — these are the shapes to expect.

### SPF — says which servers may send as you

```
Type: TXT
Host: @
Value: v=spf1 include:amazonses.com ~all
```

**One SPF record per domain, ever.** If you already have one (from Google
Workspace, say), merge into it — don't add a second:

```
v=spf1 include:_spf.google.com include:amazonses.com ~all
```

Two SPF records is a hard fail, and it's the single most common mistake here.

### DKIM — cryptographically signs your mail

Your provider gives you one to three CNAME records. Copy them exactly:

```
Type: CNAME
Host: abc123._domainkey
Value: abc123.dkim.amazonses.com
```

Don't retype these by hand — a single wrong character silently breaks signing.

### DMARC — tells inboxes what to do when the first two fail

```
Type: TXT
Host: _dmarc
Value: v=DMARC1; p=none; rua=mailto:you@yourdomain.com
```

Start with `p=none`. It monitors without rejecting anything, so a
misconfiguration doesn't silently eat your mail. After a month of clean
reports, move to `p=quarantine`.

## 3. Verify before you trust it

DNS takes minutes to hours to propagate. Check with:

```bash
dig +short TXT yourdomain.com          # should show exactly one v=spf1
dig +short TXT _dmarc.yourdomain.com   # should show v=DMARC1
```

Then the real test — send yourself a message and have it graded:

1. Go to **mail-tester.com**, copy the address it shows you.
2. Put those credentials in `/etc/coverage-gap-finder.env`, restart the service,
   and run the quiz on your live site using that address.
3. Wait for `send_worker.py` to fire (up to 15 minutes), then check your score.

**Anything below 8/10, fix it before promoting the link anywhere.** The report
tells you exactly what's failing.

## 4. Wire it into the app

```bash
sudo nano /etc/coverage-gap-finder.env
```

```
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=<your SMTP username, not your AWS key>
SMTP_PASS=<your SMTP password>
SMTP_FROM=Your Name <you@yourdomain.com>
```

```bash
sudo systemctl restart coverage-gap-finder
cd /opt/coverage-gap-finder && sudo -u leadmagnet python3 preflight.py
```

Preflight should now show email sending as `ok`.

**`SMTP_FROM` must be on the domain you authenticated.** Sending as
`you@gmail.com` through your own domain's SES account fails DMARC alignment
and lands in spam.

## 5. Warm up

New sending domains that suddenly emit hundreds of messages look exactly like
spam. Organic growth handles this naturally — you won't have hundreds of leads
in week one — but if you email your existing book (which the playbook
recommends), **split it**:

- Week 1: 20 sends
- Week 2: 50
- Week 3: 150
- Week 4: the rest

## What actually breaks

| Symptom | Cause |
|---|---|
| Everything lands in spam | Missing DKIM, or two SPF records. Check with mail-tester. |
| Some inboxes fine, Gmail spam | DMARC alignment — `SMTP_FROM` domain doesn't match the DKIM-signed domain. |
| Provider rejects every send | SES sandbox: you can only send to verified addresses until you request production access. |
| Nothing sends at all, no errors | The worker isn't running. `sudo systemctl status cron` and check `/var/log/coverage-gap-finder-worker.log`. |
| `SMTPAuthenticationError` | Using your AWS access key instead of the separate SES *SMTP* credentials. They're different. |
| Mail sends but links 404 | `site_url` in `agency.json` doesn't match the live domain. |

## The one rule

The landing page promises **no phone calls**. Don't append phone numbers from
a data provider and call these leads. Beyond breaking the promise that made
them opt in, TCPA damages run $500–$1,500 per call. Email only, unless they
book a call themselves.

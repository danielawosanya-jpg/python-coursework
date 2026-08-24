# The no-server version

Live today, on hosting you already have, for **$0** — no domain, no VPS, no
sending account, no address.

`build_static.py` produces a `static/` folder that runs the entire quiz in the
browser and captures leads through Netlify Forms. You already have a Netlify
account, so this is a drag-and-drop away.

```bash
python3 build_static.py     # writes static/
```

Then drag the `static/` folder onto <https://app.netlify.com/drop>. That's the
deploy.

---

## What you get

- The full quiz, scored in the browser
- The complete personalized report, rendered on the page
- A **Save as PDF** button so people keep it
- Lead capture into Netlify Forms — you get an email on every submission
- Source attribution: `?src=reddit`, `?src=linkedin`, and so on
- Your branding, licence and disclaimers, identical to the server build

## What you give up

**The automated follow-up sequence.** That is the real cost, and it is not a
small one — the six emails over sixteen days are what turn a download into a
conversation. Without them you get a name, an email, a score and a list of
gaps, and it is on you to reach out.

You also lose the admin dashboard (Netlify's form panel replaces it), the
SQLite database (export CSV from Netlify instead), and the emailed copy of the
report — so the page tells people to save the link or print the PDF, because
that is the only copy they get.

Netlify's free tier covers **100 form submissions a month**. At the lead
volumes in the organic playbook you will not hit that for a long time.

## One honest caveat

With the scoring engine in the browser, a determined visitor could read the gap
detail in the JavaScript without giving an email. The gate is a social
contract here, not a lock.

In practice this costs almost nothing — the people who open devtools were never
going to book a review. The alternative is running a server. It is worth
knowing, not worth worrying about.

## The two engines stay in step

`static/scoring.js` is a hand port of `leadmagnet/scoring.py`. Two
implementations of the same rules drift the moment one is edited, and a drifted
scorer means the number on the screen disagrees with the number in the email.

`tests/test_parity.py` runs the shipped `.js` file under Node against the Python
engine across twenty profiles — including the exact boundary cases where
rounding usually diverges — and fails if any of them score differently. Run it
after touching either engine:

```bash
python3 -m unittest tests.test_parity -v
```

## Getting your leads out

Netlify emails you on each submission. For the full list: **Netlify dashboard →
Forms → coverage-gap-lead → Download CSV**. Every row carries the score, the
band, the total exposure and their worst gap, so you can sort by who needs help
most.

**Anyone under 50 is your call-first list.** They have just handed you a
detailed picture of exactly where they are exposed, and the report gives you
your opening line: *"You scored 36 — that auto liability number is the one I'd
fix first."*

## When you outgrow it

Nothing here is throwaway. The server build is the same code with the same
copy; you switch by buying a domain, running `deploy/install.sh`, and pointing
DNS at it. See `DEPLOY.md`.

The upgrade is worth making when either of these is true:

- you are getting enough leads that following up by hand is slipping, or
- you want the sequence working while you sleep

Until then, this is a real lead magnet on a real site, and it costs nothing.

# Compliance Checklist

**Read this before you put the tool online.** Insurance advertising is
regulated at the state level, and most carriers require pre-approval of
agent-produced marketing. This checklist is a starting point written by a
developer, not a lawyer or a compliance officer — have your carrier's
compliance contact or your own counsel review the live page and the email
sequence before launch.

---

## 1. Licensing and identification

Every state requires that advertising clearly identify the licensed producer.

- [ ] Your legal name (the name on the license) appears on the landing page,
      in the report, and in every email
- [ ] Your license number and state appear in the footer of all three
- [ ] The agency's true name is used — a "doing business as" name usually
      requires separate registration
- [ ] The states you're licensed in are stated, and you do not solicit in
      states where you are not licensed

The placeholders live in one place: `AGENCY` at the top of
`leadmagnet/sequences.py`. The landing page footer and `web/index.html`
carry the same text and must be edited to match.

## 2. Don't create an offer where you meant education

The report is a needs estimate. It must not read as a quote, a binder, or a
promise that a claim will be paid.

- [ ] No specific premiums, rates, or "you'll pay $X" language
- [ ] No implication that any coverage is guaranteed issue or that any claim
      would be paid
- [ ] The disclaimer appears on the landing page, in the report footer, and in
      every email (all three ship with it — don't remove it)
- [ ] "Free" is accurate: nothing about the report costs anything and no
      purchase is required

## 3. Email law (CAN-SPAM, and CASL if you touch Canada)

The shipped sequence complies. If you rewrite it, keep all of this:

- [ ] Working one-click unsubscribe in every message
      (`/unsubscribe?t=TOKEN` — implemented and tested)
- [ ] Opt-outs honored promptly; the code honors them immediately and also
      deletes anything still queued
- [ ] A valid physical postal address in every message
- [ ] Accurate `From` name and address — no disguised senders
- [ ] Subject lines that describe the actual contents
- [ ] Consent captured before the first send — the checkbox is required
      server-side, not just in the browser

`tests/test_leadmagnet.py` asserts the unsubscribe link and postal address
appear in every rendered email. Keep those tests passing.

## 4. Phone calls (TCPA) — the expensive one

The landing page promises **no phone calls**. That promise is both a
conversion feature and a liability shield.

- [ ] Don't collect phone numbers on the quiz (the form doesn't)
- [ ] Don't append phone numbers from third-party data and call the lead
- [ ] Don't call or text anyone who only gave an email
- [ ] If you later add a phone field, add explicit, separate, written express
      consent language for autodialed calls and texts — and keep the record

TCPA damages run $500–$1,500 per call. This is the single most expensive
mistake available in this whole system.

## 5. Data handling

- [ ] Privacy notice on the site explaining what you collect and that you don't
      sell it (the landing page states this — make sure it stays true)
- [ ] `leads.db` is not in a web-accessible directory and is not committed to
      version control (`.gitignore` covers it)
- [ ] `ADMIN_KEY` changed from the default before the site is public
- [ ] HTTPS in front of the app (reverse proxy — see the README)
- [ ] Backups of `leads.db`, stored somewhere access-controlled
- [ ] A deletion process: if someone asks you to delete their data, delete the
      row. Some states (CA, CO, VA, CT, and a growing list) give residents that
      right by statute
- [ ] Retention limit: decide how long you keep non-converting leads and
      actually delete them

## 6. Carrier and appointment rules

- [ ] Marketing pre-approved by your carrier if your appointment requires it
      (most captive and many independent agreements do)
- [ ] Carrier names and logos used only if permitted
- [ ] No comparative claims about named competitors you can't substantiate

## 7. Accuracy of the math

The estimates use standard industry rules of thumb. They're defensible as
education, not as advice.

- [ ] The assumptions block at the top of `leadmagnet/scoring.py`
      (`INCOME_REPLACEMENT_YEARS`, `COLLEGE_COST_PER_CHILD`,
      `MIN_AUTO_LIABILITY`, and the rest) reviewed and adjusted for your market
- [ ] The report's method disclosure stays in the footer, so a reader can see
      what the numbers are based on
- [ ] `MIN_AUTO_LIABILITY` checked against your state's actual minimums

## 8. Accessibility

Not optional if you have any government or large-employer partners, and just
correct regardless.

- [ ] Keyboard navigation through the whole quiz (the form supports it)
- [ ] Labels tied to every input (they are)
- [ ] Color contrast checked if you change the palette
- [ ] The score is announced to screen readers, not conveyed by color alone
      (the report's SVG carries an `aria-label`)

---

## Pre-launch sign-off

```
Reviewed by (compliance/carrier): ______________________  Date: __________
Reviewed by (legal counsel):      ______________________  Date: __________
States approved for solicitation: ______________________________________
Placeholders replaced:            [ ] sequences.py  [ ] index.html
ADMIN_KEY changed:                [ ]
HTTPS confirmed:                  [ ]
Test lead run end to end:         [ ]  (quiz → email → report → unsubscribe)
```

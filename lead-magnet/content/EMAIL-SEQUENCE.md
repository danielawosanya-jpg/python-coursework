# The Follow-Up Sequence

The live copy is in `leadmagnet/sequences.py` — that's the source of truth,
because every email is personalized with the reader's own numbers. This
document explains *why* each email exists so you can rewrite them in your voice
without breaking what makes them work.

## Shape

| Step | Day | Job | Ask |
|------|-----|-----|-----|
| 1 | 0 | Deliver the report. Nothing else. | None |
| 2 | 1 | Explain their single biggest gap | Reply if you want |
| 3 | 3 | Story: why limits matter more than policies | None |
| 4 | 6 | Handle the cost objection before it's spoken | None |
| 5 | 10 | The offer — a real policy review | Book or send dec pages |
| 6 | 16 | Permission to leave; transition to monthly | Unsubscribe or stay |

Six emails, sixteen days, **one ask**. That ratio is the whole strategy.

## The principles behind it

**Deliver instantly and alone.** Email 1 contains the link and nothing else.
Delivery emails get opened at 60–80%; putting a pitch in one trains people to
stop opening.

**Personalize with their data, not their name.** Every email after the first
references their actual top gap, their actual dollar exposure, their actual
score. That's the entire reason the quiz is scored server-side and stored. A
merge-tagged first name fools nobody; "your auto liability is at 25,000" gets
read.

**One ask, late.** Emails 2 through 4 sell nothing. By email 5 you've been
useful four times, so the offer reads as a next step rather than the point.

**Give permission to leave.** Email 6 explicitly invites the unsubscribe. It
costs you people who were never going to convert and raises deliverability for
everyone who stays.

**Reply-to is a human.** "I read every reply myself" only works if it's true.
Replies are the highest-quality conversations this system produces — higher
than booked calls.

## Rewriting it safely

Edit `render_sequence()` in `leadmagnet/sequences.py`. Keep these or you break
compliance and the tests that guard it:

- `_signature(token)` appended to every body — it carries the license, the
  physical address and the unsubscribe link (CAN-SPAM)
- Subject lines that describe the actual contents
- No premiums, rates, or guarantees of coverage or claim payment

Change the timing in `SCHEDULE` (step → days after opt-in). Run
`python3 -m unittest discover -s tests` after any edit; the suite checks that
every step renders, includes the reader's name, and carries both the
unsubscribe link and the postal address.

Preview the whole sequence against a real lead without sending anything:

```bash
python3 send_worker.py --dry-run
```

## After day 16: the monthly

Once the sequence ends, move people to one email a month. The format that
sustains for years:

> **One claim story.** Something you actually saw, anonymized. What was
> covered, what wasn't, why.
>
> **One coverage rule.** A single mechanic explained in a paragraph — the 80%
> coinsurance clause, why flood is separate, what "own occupation" means.
>
> **One link.** Usually the Coverage Gap Finder, occasionally an article.

Three paragraphs. No design, no template, no images — plain text from a person.
It gets opened, it gets replies, and it keeps you in mind for the eighteen
months between someone's first quiz and their actual buying moment.

## What to watch

| Metric | Healthy | If it's low |
|--------|---------|-------------|
| Email 1 open rate | 55–75% | Deliverability problem — check SPF/DKIM |
| Email 2 open rate | 35–50% | Subject line, or email 1 underdelivered |
| Replies across sequence | 3–8% of leads | Your copy sounds like a company |
| Bookings from email 5 | 2–6% of leads | The offer is vague, or too early |
| Unsubscribe rate | Under 3% | You're pitching before you've helped |

A reply rate near zero is the signal that matters most. It means the emails
read as marketing, and no amount of send-volume fixes that.

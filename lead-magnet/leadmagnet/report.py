"""Renders the personalized Coverage Gap Report.

This is what the prospect gets in exchange for their email, so it has to be
worth the trade on its own - specific numbers, named gaps, and a next action
they could take without ever calling you. Generosity here is what makes the
organic distribution work: people only share a thing that helped them.

Output is a standalone HTML page (printable to PDF from the browser), so
there is no PDF dependency to install.
"""

from __future__ import annotations

import html
from typing import Any

from . import config
from .sequences import AGENCY

SEVERITY_LABEL = {
    "critical": "Critical",
    "important": "Important",
    "watch": "Worth checking",
}


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _gap_card(gap: dict[str, Any], index: int) -> str:
    amount = (
        f'<div class="gap-amount">{_money(gap["dollar_gap"])}<span>exposure</span></div>'
        if gap.get("dollar_gap") else ""
    )
    return f"""
    <article class="gap gap--{_esc(gap['severity'])}">
      <header>
        <span class="badge">{index}. {SEVERITY_LABEL.get(gap['severity'], 'Note')}</span>
        <h3>{_esc(gap['title'])}</h3>
      </header>
      {amount}
      <p class="finding">{_esc(gap['finding'])}</p>
      <p class="fix"><strong>What to do:</strong> {_esc(gap['fix'])}</p>
    </article>"""


def render_report(lead: dict[str, Any]) -> str:
    name = (lead.get("first_name") or "").strip()
    result = lead.get("result") or {}
    gaps = result.get("gaps") or []
    score = int(result.get("score") or 0)
    band = result.get("band", "")
    headline = result.get("headline", "")
    total = result.get("total_dollar_gap") or 0
    life_need = result.get("life_need") or 0
    wins = result.get("wins") or []
    token = _esc(lead.get("token", ""))

    greeting = f"{_esc(name)}, here" if name else "Here"
    gap_html = "".join(_gap_card(g, i) for i, g in enumerate(gaps, start=1)) or (
        '<article class="gap gap--clear"><h3>No material gaps found</h3>'
        '<p class="finding">Based on your answers, your coverage lines up with '
        'your income, debts and assets. Re-run this every January or after any '
        'major change - a move, a raise, a birth, a new business.</p></article>'
    )
    wins_html = "".join(f"<li>{_esc(w)}</li>" for w in wins)
    wins_block = (
        f'<section class="wins"><h2>What you already have right</h2>'
        f'<ul>{wins_html}</ul></section>' if wins else ""
    )

    call_to_action = config.cta(AGENCY)

    # score ring geometry
    circumference = 2 * 3.14159 * 54
    dash = circumference * score / 100

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#128737;</text></svg>">
<title>Your Coverage Gap Report</title>
<style>
  :root {{
    /* Awosanya Insurance Group brand palette */
    --navy: #191a3d; --navy-soft: #262758; --gold: #ffd166; --cream: #fdfaef;
    --bg: var(--cream); --card: #ffffff; --ink: var(--navy); --muted: #5b5f7a;
    --line: #e6e3d8; --accent: var(--navy); --crit: #b4342b; --imp: #b5721a;
    --watch: #6a6d92;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width: 780px; margin: 0 auto; padding: 32px 20px 64px; }}
  .masthead {{ font-size:13px; letter-spacing:.12em; text-transform:uppercase;
    color:var(--navy); font-weight:700; margin-bottom:10px;
    padding-bottom:10px; border-bottom:3px solid var(--gold); }}
  h1 {{ font-size:30px; line-height:1.2; margin:0 0 8px; }}
  .lede {{ color:var(--muted); margin:0 0 28px; }}
  .scorecard {{ background:var(--navy); color:#fff; border:1px solid var(--navy);
    border-radius:14px; padding:24px; display:flex; gap:24px; align-items:center;
    flex-wrap:wrap; }}
  .scorecard .scoretext p {{ color:#c9c8d8; }}
  .ring {{ flex:0 0 128px; }}
  .ring text {{ font-weight:700; fill:#fff; }}
  .scoretext h2 {{ margin:0 0 6px; font-size:22px; }}
  .scoretext p {{ margin:0; color:var(--muted); }}
  .totals {{ display:flex; gap:12px; flex-wrap:wrap; margin:20px 0 32px; }}
  .stat {{ flex:1 1 200px; background:var(--card); border:1px solid var(--line);
    border-top:3px solid var(--gold); border-radius:12px; padding:16px; }}
  .stat b {{ display:block; font-size:24px; color:var(--navy); }}
  .stat span {{ color:var(--muted); font-size:13px; }}
  h2.section {{ font-size:20px; margin:32px 0 12px; }}
  .gap {{ background:var(--card); border:1px solid var(--line);
    border-left:5px solid var(--watch); border-radius:12px; padding:20px;
    margin-bottom:14px; }}
  .gap--critical {{ border-left-color:var(--crit); }}
  .gap--important {{ border-left-color:var(--imp); }}
  .gap--clear {{ border-left-color:var(--gold); }}
  .gap h3 {{ margin:6px 0 10px; font-size:19px; }}
  .badge {{ font-size:11px; letter-spacing:.1em; text-transform:uppercase;
    color:var(--muted); font-weight:700; }}
  .gap--critical .badge {{ color:var(--crit); }}
  .gap--important .badge {{ color:var(--imp); }}
  .gap-amount {{ font-size:26px; font-weight:700; margin-bottom:10px; }}
  .gap-amount span {{ font-size:13px; font-weight:400; color:var(--muted);
    margin-left:8px; }}
  .finding {{ margin:0 0 10px; }}
  .fix {{ margin:0; color:var(--muted); }}
  .wins ul {{ background:var(--card); border:1px solid var(--line);
    border-left:5px solid var(--gold); border-radius:12px; padding:16px 16px 16px 36px; }}
  .cta {{ background:var(--navy); color:#fff; border-radius:14px;
    border-bottom:5px solid var(--gold); padding:28px; margin-top:32px; }}
  .cta h2 {{ margin:0 0 10px; }}
  .cta p {{ margin:0 0 16px; opacity:.9; }}
  .cta a {{ display:inline-block; background:var(--gold); color:var(--navy);
    padding:12px 22px; border-radius:8px; text-decoration:none; font-weight:700; }}
  footer {{ margin-top:36px; padding-top:20px; border-top:1px solid var(--line);
    font-size:13px; color:var(--muted); }}
  @media print {{ body {{ background:#fff; }} .cta {{ break-inside:avoid; }} }}
</style>
</head><body><div class="wrap">

  <div class="masthead">{_esc(AGENCY['agency_name'])} &middot; Coverage Gap Report</div>
  <h1>{greeting}&rsquo;s where your protection actually stands.</h1>
  <p class="lede">{_esc(headline)}</p>

  <div class="scorecard">
    <svg class="ring" viewBox="0 0 128 128" width="128" height="128" role="img"
         aria-label="Protection score {score} out of 100">
      <circle cx="64" cy="64" r="54" fill="none" stroke="#3a3b63" stroke-width="12"/>
      <circle cx="64" cy="64" r="54" fill="none" stroke="#ffd166" stroke-width="12"
              stroke-linecap="round" stroke-dasharray="{dash:.1f} {circumference:.1f}"
              transform="rotate(-90 64 64)"/>
      <text x="64" y="72" text-anchor="middle" font-size="32">{score}</text>
    </svg>
    <div class="scoretext">
      <h2>{_esc(band)}</h2>
      <p>Your protection score, out of 100. It drops for every gap we found,
         weighted by how badly that gap would hurt at claim time.</p>
    </div>
  </div>

  <div class="totals">
    <div class="stat"><b>{_money(total)}</b><span>Total estimated exposure</span></div>
    <div class="stat"><b>{_money(life_need)}</b><span>Life coverage your household profile suggests</span></div>
    <div class="stat"><b>{len(gaps)}</b><span>Gaps identified</span></div>
  </div>

  <h2 class="section">Your gaps, worst first</h2>
  {gap_html}

  {wins_block}

  <div class="cta">
    <h2>Want a second set of eyes on the actual policy?</h2>
    <p>This report is built from ten answers. Your declarations page has about
       forty numbers on it. Send yours over and we will read it together. I am
       an independent broker, so "keep what you have" is an answer I am free to
       give - and most reviews end exactly there.</p>
    <a href="{_esc(call_to_action['href'])}">{_esc(call_to_action['button'])}</a>
  </div>

  <footer>
    <p><strong>{_esc(AGENCY['agent_name'])}</strong>, Licensed Independent
       Insurance Broker &middot;
       {_esc(AGENCY['agency_name'])} &middot; {_esc(AGENCY['license'])}<br>
       Licensed in {_esc(AGENCY['states_licensed'])} &middot;
       {_esc(AGENCY['phone'])} &middot; {_esc(AGENCY['mailing_address'])}</p>
    <p>This report is general educational information, not insurance, legal or
       tax advice, and it is not an offer of coverage or a guarantee of
       eligibility, rates or claim payment. Estimates use common industry rules
       of thumb (DIME, income multiples, replacement-cost ratios) applied to the
       answers you provided. Your actual needs depend on facts this quiz does
       not capture. Policy language and your carrier's underwriting govern in
       all cases. Coverage availability varies by state.</p>
    <p><a href="/unsubscribe?t={token}">Unsubscribe from follow-up emails</a></p>
  </footer>

</div></body></html>"""

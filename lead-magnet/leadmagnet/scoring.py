"""The coverage-gap engine.

This is the actual value the lead magnet delivers. A prospect answers 10
questions; this module turns those answers into a dollar-denominated gap
estimate, a 0-100 protection score, and a ranked list of specific gaps.

Everything here is deterministic and dependency-free so it can be unit
tested, run from the CLI, or called by the web server.

DISCLAIMER: the formulas below are industry rules of thumb (DIME, income
multiples, replacement-cost ratios). They produce an *educational estimate*,
not a recommendation to buy or replace any policy. See COMPLIANCE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# --- tunable assumptions -------------------------------------------------
# Kept in one place so an agent can adjust them for their state / book of
# business without touching the logic.

INCOME_REPLACEMENT_YEARS = 10       # DIME "I": years of income to replace
COLLEGE_COST_PER_CHILD = 30_000     # 4-yr in-state public, conservative
EMERGENCY_FUND_MONTHS = 6
MIN_AUTO_LIABILITY = 100_000        # per-person bodily injury floor.
# This is a recommended floor, NOT any state's legal minimum. Actual
# minimums differ by state and change by legislature (Florida, for
# instance, does not mandate bodily-injury liability at all), so the
# report never tells a reader what their state requires.
UMBRELLA_TRIGGER_NET_WORTH = 500_000
DISABILITY_TARGET_PCT = 0.60        # % of income a DI policy should replace
FINAL_EXPENSE = 15_000              # funeral + estate settlement


@dataclass
class Answers:
    """The 10 quiz answers. Everything is optional so partial quizzes score."""

    age: int = 40
    annual_income: float = 0.0
    spouse_income: float = 0.0
    dependents: int = 0
    mortgage_balance: float = 0.0
    other_debt: float = 0.0
    liquid_savings: float = 0.0
    existing_life_coverage: float = 0.0
    auto_liability_limit: float = 0.0
    home_value: float = 0.0
    home_dwelling_coverage: float = 0.0
    has_disability_insurance: bool = False
    has_umbrella: bool = False
    net_worth: float = 0.0
    renter: bool = False
    has_renters_insurance: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "Answers":
        """Build from untrusted JSON, coercing types and clamping ranges."""
        def num(key: str, default: float = 0.0, lo: float = 0.0,
                hi: float = 100_000_000.0) -> float:
            raw = payload.get(key, default)
            if raw in (None, "", "null"):
                return float(default)
            try:
                value = float(str(raw).replace(",", "").replace("$", "").strip())
            except (TypeError, ValueError):
                return float(default)
            return max(lo, min(hi, value))

        def flag(key: str) -> bool:
            return str(payload.get(key, "")).strip().lower() in {
                "1", "true", "yes", "y", "on"
            }

        return cls(
            age=int(num("age", 40, 18, 100)),
            annual_income=num("annual_income"),
            spouse_income=num("spouse_income"),
            dependents=int(num("dependents", 0, 0, 12)),
            mortgage_balance=num("mortgage_balance"),
            other_debt=num("other_debt"),
            liquid_savings=num("liquid_savings"),
            existing_life_coverage=num("existing_life_coverage"),
            auto_liability_limit=num("auto_liability_limit"),
            home_value=num("home_value"),
            home_dwelling_coverage=num("home_dwelling_coverage"),
            has_disability_insurance=flag("has_disability_insurance"),
            has_umbrella=flag("has_umbrella"),
            net_worth=num("net_worth"),
            renter=flag("renter"),
            has_renters_insurance=flag("has_renters_insurance"),
        )


@dataclass
class Gap:
    """One specific, named hole in the prospect's protection."""

    key: str
    title: str
    severity: str          # "critical" | "important" | "watch"
    dollar_gap: float      # 0 when the gap is structural rather than sized
    finding: str           # what we measured
    fix: str               # the next action, in plain language

    # severity drives both the report ordering and the score penalty
    WEIGHTS = {"critical": 22, "important": 12, "watch": 5}

    @property
    def penalty(self) -> int:
        return self.WEIGHTS.get(self.severity, 5)


@dataclass
class Result:
    score: int
    band: str
    total_dollar_gap: float
    life_need: float
    life_gap: float
    gaps: list[Gap] = field(default_factory=list)
    wins: list[str] = field(default_factory=list)
    headline: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["gaps"] = [asdict(g) for g in self.gaps]
        return data


# --- individual checks ---------------------------------------------------

def life_insurance_need(a: Answers) -> float:
    """DIME: Debt + Income replacement + Mortgage + Education, less savings."""
    if a.annual_income <= 0 and a.dependents == 0:
        return 0.0
    income_years = INCOME_REPLACEMENT_YEARS
    # Someone at 60 rarely needs 10 more years of income replaced.
    if a.age >= 55:
        income_years = max(3, INCOME_REPLACEMENT_YEARS - (a.age - 55))
    need = (
        a.other_debt
        + a.annual_income * income_years
        + a.mortgage_balance
        + a.dependents * COLLEGE_COST_PER_CHILD
        + FINAL_EXPENSE
    )
    return max(0.0, need - a.liquid_savings)


def _check_life(a: Answers, need: float) -> Gap | None:
    gap = need - a.existing_life_coverage
    if need <= 0 or gap <= 0:
        return None
    severity = "critical" if a.dependents > 0 or gap > need * 0.5 else "important"
    return Gap(
        key="life",
        title="Life insurance shortfall",
        severity=severity,
        dollar_gap=gap,
        finding=(
            f"Your household needs roughly ${need:,.0f} of death benefit to "
            f"cover debt, {INCOME_REPLACEMENT_YEARS} years of income, the "
            f"mortgage and education. You currently carry "
            f"${a.existing_life_coverage:,.0f}."
        ),
        fix=(
            "A level term policy is the cheapest way to close a gap this size. "
            "Price a term long enough to reach your youngest dependent's "
            "independence or your mortgage payoff, whichever is later."
        ),
    )


def _check_disability(a: Answers) -> Gap | None:
    if a.annual_income <= 0 or a.has_disability_insurance:
        return None
    monthly = a.annual_income * DISABILITY_TARGET_PCT / 12
    return Gap(
        key="disability",
        title="No disability income protection",
        severity="critical" if a.dependents > 0 else "important",
        dollar_gap=a.annual_income * DISABILITY_TARGET_PCT,
        finding=(
            f"You are insuring your car and your house but not the asset that "
            f"pays for both. A disabling injury or illness would stop roughly "
            f"${a.annual_income:,.0f}/yr of income."
        ),
        fix=(
            f"Target about ${monthly:,.0f}/month of own-occupation coverage. "
            "Check what your employer already provides first - group LTD is "
            "usually capped and taxable, which is where the real gap hides."
        ),
    )


def _check_emergency_fund(a: Answers) -> Gap | None:
    household = a.annual_income + a.spouse_income
    if household <= 0:
        return None
    target = household / 12 * EMERGENCY_FUND_MONTHS
    if a.liquid_savings >= target:
        return None
    return Gap(
        key="emergency_fund",
        title="Emergency fund below a 6-month target",
        severity="important" if a.liquid_savings < target / 2 else "watch",
        dollar_gap=target - a.liquid_savings,
        finding=(
            f"Six months of household income is about ${target:,.0f}, the "
            f"usual emergency-fund target. You listed "
            f"${a.liquid_savings:,.0f} in liquid savings."
        ),
        fix=(
            "Until the fund is built, keep deductibles low. Once it is funded, "
            "raising deductibles usually cuts premium enough to pay for the "
            "life or disability coverage above."
        ),
    )


def _check_auto(a: Answers) -> Gap | None:
    if a.auto_liability_limit <= 0:
        return Gap(
            key="auto",
            title="Auto liability limits unknown",
            severity="watch",
            dollar_gap=0.0,
            finding="You did not list an auto bodily-injury limit.",
            fix=(
                "Pull your declarations page. The number after the slash is "
                "what stands between an at-fault accident and your paycheck."
            ),
        )
    if a.auto_liability_limit >= MIN_AUTO_LIABILITY:
        return None
    # $25k is the state minimum in many states; $50k is not, so don't call it
    # one. Getting this wrong is exactly the kind of detail that costs trust.
    at_minimum = a.auto_liability_limit <= 25_000
    title = ("Auto liability at or near state-minimum levels" if at_minimum
             else "Auto liability below the recommended floor")
    return Gap(
        key="auto",
        title=title,
        severity="critical" if at_minimum else "important",
        dollar_gap=MIN_AUTO_LIABILITY - a.auto_liability_limit,
        finding=(
            f"You carry ${a.auto_liability_limit:,.0f} per person in bodily "
            f"injury liability. One ER visit and a week of lost wages clears "
            f"that number."
        ),
        fix=(
            "Moving up to 100/300/100 is one of the cheapest upgrades in "
            "insurance - often under $15/month - because severe claims are "
            "rare but ruinous."
        ),
    )


def _check_home(a: Answers) -> Gap | None:
    if a.renter:
        if a.has_renters_insurance:
            return None
        return Gap(
            key="renters",
            title="No renters insurance",
            severity="important",
            dollar_gap=0.0,
            finding=(
                "Your landlord's policy covers the building, not your "
                "belongings and not your liability if a guest is hurt."
            ),
            fix=(
                "Renters policies commonly run $12-25/month and include "
                "personal liability, which is the part that actually matters."
            ),
        )
    if a.home_value <= 0:
        return None
    if a.home_dwelling_coverage <= 0:
        return Gap(
            key="home",
            title="Dwelling coverage unknown",
            severity="watch",
            dollar_gap=0.0,
            finding="You did not list your Coverage A (dwelling) amount.",
            fix=(
                "Compare Coverage A to today's rebuild cost, not to your "
                "home's market value - construction costs moved faster than "
                "most policies were updated."
            ),
        )
    # Rebuild cost is not market value, but under-insuring vs. value is the
    # signal most people can actually check on their own dec page.
    if a.home_dwelling_coverage >= a.home_value * 0.8:
        return None
    shortfall = a.home_value * 0.8 - a.home_dwelling_coverage
    return Gap(
        key="home",
        title="Possible dwelling under-insurance",
        severity="important",
        dollar_gap=shortfall,
        finding=(
            f"Your dwelling limit of ${a.home_dwelling_coverage:,.0f} is well "
            f"under your ${a.home_value:,.0f} home value. Most policies reduce "
            f"a partial-loss payout when the limit falls below the 80% "
            f"coinsurance threshold."
        ),
        fix=(
            "Ask your carrier to re-run the replacement-cost estimator with "
            "current materials pricing, and confirm whether you have extended "
            "or guaranteed replacement cost."
        ),
    )


def _check_umbrella(a: Answers) -> Gap | None:
    exposed = max(a.net_worth, a.home_value - a.mortgage_balance)
    if a.has_umbrella or exposed < UMBRELLA_TRIGGER_NET_WORTH:
        return None
    return Gap(
        key="umbrella",
        title="Assets above your liability limits",
        severity="important",
        dollar_gap=exposed,
        finding=(
            f"You have roughly ${exposed:,.0f} of exposed assets sitting above "
            f"your auto and home liability limits."
        ),
        fix=(
            "A $1M personal umbrella typically costs $150-300/year and sits on "
            "top of both policies. It is the highest coverage-per-dollar "
            "product on the market for anyone with real assets."
        ),
    )


def _wins(a: Answers, gap_keys: set[str]) -> list[str]:
    """Name what they already got right. Reciprocity beats fear."""
    wins: list[str] = []
    if a.has_disability_insurance:
        wins.append("You already protect your income with disability coverage - "
                    "most people never do.")
    if a.has_umbrella:
        wins.append("You carry an umbrella policy. That single decision covers "
                    "the tail risk most families are exposed to.")
    if "auto" not in gap_keys and a.auto_liability_limit >= MIN_AUTO_LIABILITY:
        wins.append(f"Your auto liability limit of "
                    f"${a.auto_liability_limit:,.0f} is above the level where "
                    f"most at-fault claims turn personal.")
    if "emergency_fund" not in gap_keys and a.liquid_savings > 0:
        wins.append("Your emergency fund is deep enough to absorb deductibles, "
                    "which gives you room to lower premiums.")
    if a.renter and a.has_renters_insurance:
        wins.append("You carry renters insurance - the liability piece alone "
                    "makes it one of the best values in insurance.")
    return wins


def band_for(score: int) -> str:
    if score >= 85:
        return "Well Protected"
    if score >= 70:
        return "Mostly Covered"
    if score >= 50:
        return "Exposed"
    return "Seriously Exposed"


def score(answers: Answers) -> Result:
    """Run every check and assemble the prospect-facing result."""
    need = life_insurance_need(answers)

    checks = [
        _check_life(answers, need),
        _check_disability(answers),
        _check_auto(answers),
        _check_home(answers),
        _check_umbrella(answers),
        _check_emergency_fund(answers),
    ]
    gaps = [g for g in checks if g is not None]

    order = {"critical": 0, "important": 1, "watch": 2}
    gaps.sort(key=lambda g: (order[g.severity], -g.dollar_gap))

    # Diminishing penalties. Straight summation drove ordinary underinsured
    # households into the single digits, which reads as clickbait and costs
    # the report its credibility. The first gap should hurt most.
    decay = [1.0, 0.75, 0.6, 0.5]
    penalty = sum(
        g.penalty * (decay[i] if i < len(decay) else decay[-1])
        for i, g in enumerate(gaps)
    )
    points = max(5, min(100, round(100 - penalty)))

    life_gap = max(0.0, need - answers.existing_life_coverage)
    total = sum(g.dollar_gap for g in gaps)

    critical = [g for g in gaps if g.severity == "critical"]
    if not gaps:
        headline = ("No material gaps found. Your job now is to keep limits "
                    "current as your income and assets grow.")
    elif critical:
        headline = (f"{len(critical)} critical gap"
                    f"{'s' if len(critical) > 1 else ''} would hit your family "
                    f"before any other coverage responded.")
    else:
        headline = (f"No emergencies, but {len(gaps)} gap"
                    f"{'s' if len(gaps) > 1 else ''} would cost you real money "
                    f"at claim time.")

    return Result(
        score=points,
        band=band_for(points),
        total_dollar_gap=total,
        life_need=need,
        life_gap=life_gap,
        gaps=gaps,
        wins=_wins(answers, {g.key for g in gaps}),
        headline=headline,
    )


def score_payload(payload: dict[str, Any]) -> Result:
    return score(Answers.from_payload(payload))


if __name__ == "__main__":  # quick manual check: python -m leadmagnet.scoring
    demo = Answers(
        age=38, annual_income=95_000, spouse_income=60_000, dependents=2,
        mortgage_balance=310_000, other_debt=28_000, liquid_savings=18_000,
        existing_life_coverage=100_000, auto_liability_limit=50_000,
        home_value=520_000, home_dwelling_coverage=350_000, net_worth=240_000,
    )
    r = score(demo)
    print(f"Score {r.score}/100 ({r.band}) - {r.headline}")
    for g in r.gaps:
        print(f"  [{g.severity:>9}] {g.title}: ${g.dollar_gap:,.0f}")

/* Coverage Gap Finder - scoring engine, browser build.
 *
 * A faithful port of leadmagnet/scoring.py. Two implementations of the same
 * rules can drift, so tests/test_parity.py runs this file under Node against
 * the Python engine and fails if any profile scores differently.
 *
 * Works in the browser (attaches to window.CoverageGap) and in Node
 * (module.exports), so the parity test runs the exact file the site ships. */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) { module.exports = api; }
  else { root.CoverageGap = api; }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var INCOME_REPLACEMENT_YEARS = 10;
  var COLLEGE_COST_PER_CHILD = 30000;
  var EMERGENCY_FUND_MONTHS = 6;
  var MIN_AUTO_LIABILITY = 100000;
  var UMBRELLA_TRIGGER_NET_WORTH = 500000;
  var DISABILITY_TARGET_PCT = 0.60;
  var FINAL_EXPENSE = 15000;

  var WEIGHTS = { critical: 22, important: 12, watch: 5 };
  var ORDER = { critical: 0, important: 1, watch: 2 };

  /* Python's round() is half-to-even; JS Math.round is half-up. Match Python
     so the two engines never disagree on a boundary. */
  function roundHalfEven(value) {
    var floor = Math.floor(value);
    var diff = value - floor;
    if (diff > 0.5) { return floor + 1; }
    if (diff < 0.5) { return floor; }
    return floor % 2 === 0 ? floor : floor + 1;
  }

  function money(value) {
    return "$" + roundHalfEven(value).toLocaleString("en-US");
  }

  function num(payload, key, dflt, lo, hi) {
    dflt = dflt === undefined ? 0 : dflt;
    lo = lo === undefined ? 0 : lo;
    hi = hi === undefined ? 100000000 : hi;
    var raw = payload[key];
    if (raw === undefined || raw === null || raw === "" || raw === "null") {
      return dflt;
    }
    var cleaned = String(raw).replace(/,/g, "").replace(/\$/g, "").trim();
    var value = parseFloat(cleaned);
    if (isNaN(value)) { return dflt; }
    return Math.max(lo, Math.min(hi, value));
  }

  function flag(payload, key) {
    var raw = payload[key];
    if (raw === true) { return true; }
    return ["1", "true", "yes", "y", "on"].indexOf(
      String(raw === undefined ? "" : raw).trim().toLowerCase()) !== -1;
  }

  function fromPayload(payload) {
    payload = payload || {};
    return {
      age: Math.trunc(num(payload, "age", 40, 18, 100)),
      annual_income: num(payload, "annual_income"),
      spouse_income: num(payload, "spouse_income"),
      dependents: Math.trunc(num(payload, "dependents", 0, 0, 12)),
      mortgage_balance: num(payload, "mortgage_balance"),
      other_debt: num(payload, "other_debt"),
      liquid_savings: num(payload, "liquid_savings"),
      existing_life_coverage: num(payload, "existing_life_coverage"),
      auto_liability_limit: num(payload, "auto_liability_limit"),
      home_value: num(payload, "home_value"),
      home_dwelling_coverage: num(payload, "home_dwelling_coverage"),
      has_disability_insurance: flag(payload, "has_disability_insurance"),
      has_umbrella: flag(payload, "has_umbrella"),
      net_worth: num(payload, "net_worth"),
      renter: flag(payload, "renter"),
      has_renters_insurance: flag(payload, "has_renters_insurance")
    };
  }

  function lifeInsuranceNeed(a) {
    if (a.annual_income <= 0 && a.dependents === 0) { return 0; }
    var years = INCOME_REPLACEMENT_YEARS;
    if (a.age >= 55) {
      years = Math.max(3, INCOME_REPLACEMENT_YEARS - (a.age - 55));
    }
    var need = a.other_debt
      + a.annual_income * years
      + a.mortgage_balance
      + a.dependents * COLLEGE_COST_PER_CHILD
      + FINAL_EXPENSE;
    return Math.max(0, need - a.liquid_savings);
  }

  function checkLife(a, need) {
    var gap = need - a.existing_life_coverage;
    if (need <= 0 || gap <= 0) { return null; }
    return {
      key: "life",
      title: "Life insurance shortfall",
      severity: (a.dependents > 0 || gap > need * 0.5) ? "critical" : "important",
      dollar_gap: gap,
      finding: "Your household needs roughly " + money(need) + " of death "
        + "benefit to cover debt, " + INCOME_REPLACEMENT_YEARS + " years of "
        + "income, the mortgage and education. You currently carry "
        + money(a.existing_life_coverage) + ".",
      fix: "A level term policy is the cheapest way to close a gap this size. "
        + "Price a term long enough to reach your youngest dependent's "
        + "independence or your mortgage payoff, whichever is later."
    };
  }

  function checkDisability(a) {
    if (a.annual_income <= 0 || a.has_disability_insurance) { return null; }
    var monthly = a.annual_income * DISABILITY_TARGET_PCT / 12;
    return {
      key: "disability",
      title: "No disability income protection",
      severity: a.dependents > 0 ? "critical" : "important",
      dollar_gap: a.annual_income * DISABILITY_TARGET_PCT,
      finding: "You are insuring your car and your house but not the asset "
        + "that pays for both. A disabling injury or illness would stop "
        + "roughly " + money(a.annual_income) + "/yr of income.",
      fix: "Target about " + money(monthly) + "/month of own-occupation "
        + "coverage. Check what your employer already provides first - group "
        + "LTD is usually capped and taxable, which is where the real gap hides."
    };
  }

  function checkEmergencyFund(a) {
    var household = a.annual_income + a.spouse_income;
    if (household <= 0) { return null; }
    var target = household / 12 * EMERGENCY_FUND_MONTHS;
    if (a.liquid_savings >= target) { return null; }
    return {
      key: "emergency_fund",
      title: "Emergency fund below a 6-month target",
      severity: a.liquid_savings < target / 2 ? "important" : "watch",
      dollar_gap: target - a.liquid_savings,
      finding: "Six months of household income is about " + money(target)
        + ", the usual emergency-fund target. You listed "
        + money(a.liquid_savings) + " in liquid savings.",
      fix: "Until the fund is built, keep deductibles low. Once it is funded, "
        + "raising deductibles usually cuts premium enough to pay for the life "
        + "or disability coverage above."
    };
  }

  function checkAuto(a) {
    if (a.auto_liability_limit <= 0) {
      return {
        key: "auto",
        title: "Auto liability limits unknown",
        severity: "watch",
        dollar_gap: 0,
        finding: "You did not list an auto bodily-injury limit.",
        fix: "Pull your declarations page. The number after the slash is what "
          + "stands between an at-fault accident and your paycheck."
      };
    }
    if (a.auto_liability_limit >= MIN_AUTO_LIABILITY) { return null; }
    var atMinimum = a.auto_liability_limit <= 25000;
    return {
      key: "auto",
      title: atMinimum ? "Auto liability at or near state-minimum levels"
                       : "Auto liability below the recommended floor",
      severity: atMinimum ? "critical" : "important",
      dollar_gap: MIN_AUTO_LIABILITY - a.auto_liability_limit,
      finding: "You carry " + money(a.auto_liability_limit) + " per person in "
        + "bodily injury liability. One ER visit and a week of lost wages "
        + "clears that number.",
      fix: "Moving up to 100/300/100 is one of the cheapest upgrades in "
        + "insurance - often under $15/month - because severe claims are rare "
        + "but ruinous."
    };
  }

  function checkHome(a) {
    if (a.renter) {
      if (a.has_renters_insurance) { return null; }
      return {
        key: "renters",
        title: "No renters insurance",
        severity: "important",
        dollar_gap: 0,
        finding: "Your landlord's policy covers the building, not your "
          + "belongings and not your liability if a guest is hurt.",
        fix: "Renters policies commonly run $12-25/month and include personal "
          + "liability, which is the part that actually matters."
      };
    }
    if (a.home_value <= 0) { return null; }
    if (a.home_dwelling_coverage <= 0) {
      return {
        key: "home",
        title: "Dwelling coverage unknown",
        severity: "watch",
        dollar_gap: 0,
        finding: "You did not list your Coverage A (dwelling) amount.",
        fix: "Compare Coverage A to today's rebuild cost, not to your home's "
          + "market value - construction costs moved faster than most policies "
          + "were updated."
      };
    }
    if (a.home_dwelling_coverage >= a.home_value * 0.8) { return null; }
    return {
      key: "home",
      title: "Possible dwelling under-insurance",
      severity: "important",
      dollar_gap: a.home_value * 0.8 - a.home_dwelling_coverage,
      finding: "Your dwelling limit of " + money(a.home_dwelling_coverage)
        + " is well under your " + money(a.home_value) + " home value. Most "
        + "policies reduce a partial-loss payout when the limit falls below "
        + "the 80% coinsurance threshold.",
      fix: "Ask your carrier to re-run the replacement-cost estimator with "
        + "current materials pricing, and confirm whether you have extended or "
        + "guaranteed replacement cost."
    };
  }

  function checkUmbrella(a) {
    var exposed = Math.max(a.net_worth, a.home_value - a.mortgage_balance);
    if (a.has_umbrella || exposed < UMBRELLA_TRIGGER_NET_WORTH) { return null; }
    return {
      key: "umbrella",
      title: "Assets above your liability limits",
      severity: "important",
      dollar_gap: exposed,
      finding: "You have roughly " + money(exposed) + " of exposed assets "
        + "sitting above your auto and home liability limits.",
      fix: "A $1M personal umbrella typically costs $150-300/year and sits on "
        + "top of both policies. It is the highest coverage-per-dollar product "
        + "on the market for anyone with real assets."
    };
  }

  function wins(a, gapKeys) {
    var out = [];
    if (a.has_disability_insurance) {
      out.push("You already protect your income with disability coverage - "
        + "most people never do.");
    }
    if (a.has_umbrella) {
      out.push("You carry an umbrella policy. That single decision covers the "
        + "tail risk most families are exposed to.");
    }
    if (gapKeys.indexOf("auto") === -1
        && a.auto_liability_limit >= MIN_AUTO_LIABILITY) {
      out.push("Your auto liability limit of " + money(a.auto_liability_limit)
        + " is above the level where most at-fault claims turn personal.");
    }
    if (gapKeys.indexOf("emergency_fund") === -1 && a.liquid_savings > 0) {
      out.push("Your emergency fund is deep enough to absorb deductibles, "
        + "which gives you room to lower premiums.");
    }
    if (a.renter && a.has_renters_insurance) {
      out.push("You carry renters insurance - the liability piece alone makes "
        + "it one of the best values in insurance.");
    }
    return out;
  }

  function bandFor(score) {
    if (score >= 85) { return "Well Protected"; }
    if (score >= 70) { return "Mostly Covered"; }
    if (score >= 50) { return "Exposed"; }
    return "Seriously Exposed";
  }

  function score(a) {
    var need = lifeInsuranceNeed(a);
    var gaps = [
      checkLife(a, need), checkDisability(a), checkAuto(a),
      checkHome(a), checkUmbrella(a), checkEmergencyFund(a)
    ].filter(function (g) { return g !== null; });

    gaps.sort(function (x, y) {
      var bySeverity = ORDER[x.severity] - ORDER[y.severity];
      return bySeverity !== 0 ? bySeverity : y.dollar_gap - x.dollar_gap;
    });

    var decay = [1.0, 0.75, 0.6, 0.5];
    var penalty = 0;
    gaps.forEach(function (g, i) {
      penalty += WEIGHTS[g.severity] * (i < decay.length ? decay[i]
                                                         : decay[decay.length - 1]);
    });
    var points = Math.max(5, Math.min(100, roundHalfEven(100 - penalty)));

    var critical = gaps.filter(function (g) { return g.severity === "critical"; });
    var headline;
    if (gaps.length === 0) {
      headline = "No material gaps found. Your job now is to keep limits "
        + "current as your income and assets grow.";
    } else if (critical.length) {
      headline = critical.length + " critical gap"
        + (critical.length > 1 ? "s" : "")
        + " would hit your family before any other coverage responded.";
    } else {
      headline = "No emergencies, but " + gaps.length + " gap"
        + (gaps.length > 1 ? "s" : "")
        + " would cost you real money at claim time.";
    }

    var keys = gaps.map(function (g) { return g.key; });
    return {
      score: points,
      band: bandFor(points),
      total_dollar_gap: gaps.reduce(function (s, g) { return s + g.dollar_gap; }, 0),
      life_need: need,
      life_gap: Math.max(0, need - a.existing_life_coverage),
      gaps: gaps,
      wins: wins(a, keys),
      headline: headline
    };
  }

  return {
    fromPayload: fromPayload,
    lifeInsuranceNeed: lifeInsuranceNeed,
    score: score,
    scorePayload: function (payload) { return score(fromPayload(payload)); },
    bandFor: bandFor,
    money: money,
    MIN_AUTO_LIABILITY: MIN_AUTO_LIABILITY
  };
}));

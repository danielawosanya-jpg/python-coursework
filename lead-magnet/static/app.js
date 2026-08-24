/* Coverage Gap Finder - static build.
 *
 * Same quiz as the server version, but scoring runs in the browser and the
 * report renders in place. Leads post to Netlify Forms, so there is no
 * backend, no database and nothing to deploy but files.
 *
 * Trade-off worth knowing: with scoring client-side, a determined visitor can
 * read the gap detail in the JS without giving an email. The gate is a social
 * contract here, not a lock. In practice almost nobody opens devtools, and the
 * alternative is running a server. */

(function () {
  "use strict";

  var engine = window.CoverageGap;
  var form = document.getElementById("quizForm");
  var steps = Array.prototype.slice.call(form.querySelectorAll(".step"));
  var fill = document.getElementById("progressFill");
  var label = document.getElementById("progressLabel");
  var backBtn = document.getElementById("backBtn");
  var nextBtn = document.getElementById("nextBtn");
  var submitBtn = document.getElementById("submitBtn");
  var errorBox = document.getElementById("formError");
  var doneBox = document.getElementById("done");
  var reportBox = document.getElementById("report");
  var current = 0;
  var lastResult = null;

  function source() {
    var params = new URLSearchParams(window.location.search);
    var tagged = params.get("src") || params.get("utm_source");
    if (tagged) { return tagged.slice(0, 60); }
    var ref = document.referrer;
    if (!ref) { return "direct"; }
    try { return new URL(ref).hostname.replace(/^www\./, "").slice(0, 60); }
    catch (e) { return "direct"; }
  }

  function answers() {
    var data = new FormData(form);
    var out = {};
    data.forEach(function (value, key) {
      if (["email", "first_name", "zip_code", "consent"].indexOf(key) !== -1) {
        return;
      }
      out[key] = value;
    });
    ["has_disability_insurance", "has_umbrella", "renter",
     "has_renters_insurance"].forEach(function (key) {
      out[key] = out[key] === "yes";
    });
    return out;
  }

  /* --- navigation (identical behaviour to the server build) ------------- */
  function show(index, moved) {
    steps.forEach(function (step, i) {
      step.classList.toggle("is-active", i === index);
    });
    current = index;
    fill.style.width = ((index + 1) / steps.length) * 100 + "%";
    label.textContent = "Step " + (index + 1) + " of " + steps.length;
    backBtn.hidden = index === 0;
    nextBtn.hidden = index === steps.length - 1;
    submitBtn.hidden = index !== steps.length - 1;
    errorBox.hidden = true;
    if (!moved) { return; }
    var firstField = steps[index].querySelector("input,select");
    if (firstField) { firstField.focus(); }
    steps[index].scrollIntoView({ block: "nearest" });
  }

  nextBtn.addEventListener("click", function () {
    if (current === steps.length - 2) { loadTeaser(); }
    show(Math.min(current + 1, steps.length - 1), true);
  });
  backBtn.addEventListener("click", function () {
    show(Math.max(current - 1, 0), true);
  });
  form.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && current < steps.length - 1) {
      event.preventDefault();
      nextBtn.click();
    }
  });

  form.querySelectorAll("input[name=renter]").forEach(function (radio) {
    radio.addEventListener("change", function () {
      var renting = form.querySelector("input[name=renter]:checked").value === "yes";
      document.getElementById("ownerFields").hidden = renting;
      document.getElementById("renterFields").hidden = !renting;
    });
  });

  /* --- teaser ---------------------------------------------------------- */
  function loadTeaser() {
    lastResult = engine.scorePayload(answers());
    var critical = lastResult.gaps.filter(function (g) {
      return g.severity === "critical";
    }).length;

    animate(document.getElementById("teaserScore"), lastResult.score);
    document.getElementById("teaserBand").textContent = lastResult.band;
    document.getElementById("teaserLine").textContent = lastResult.gaps.length
      ? "We found " + lastResult.gaps.length + " gap"
        + (lastResult.gaps.length === 1 ? "" : "s") + ", " + critical
        + " of them critical. The full breakdown — dollar exposure and the fix "
        + "for each — is in your report."
      : "No material gaps found. Your report explains what to keep an eye on "
        + "as your income and assets grow.";
  }

  function animate(el, target) {
    var value = 0;
    var stepSize = Math.max(1, Math.round(target / 24));
    var timer = setInterval(function () {
      value = Math.min(target, value + stepSize);
      el.textContent = value;
      if (value >= target) { clearInterval(timer); }
    }, 22);
  }

  /* --- report ---------------------------------------------------------- */
  var SEVERITY_LABEL = {
    critical: "Critical", important: "Important", watch: "Worth checking"
  };

  function esc(value) {
    var div = document.createElement("div");
    div.textContent = String(value);
    return div.innerHTML;
  }

  function renderReport(name, result) {
    var circumference = 2 * Math.PI * 54;
    var dash = circumference * result.score / 100;

    var gapsHtml = result.gaps.map(function (gap, i) {
      var amount = gap.dollar_gap
        ? '<div class="gap-amount">' + engine.money(gap.dollar_gap)
          + "<span>exposure</span></div>"
        : "";
      return '<article class="gap gap--' + gap.severity + '">'
        + '<span class="badge">' + (i + 1) + ". "
        + SEVERITY_LABEL[gap.severity] + "</span>"
        + "<h3>" + esc(gap.title) + "</h3>" + amount
        + '<p class="finding">' + esc(gap.finding) + "</p>"
        + '<p class="fix"><strong>What to do:</strong> ' + esc(gap.fix) + "</p>"
        + "</article>";
    }).join("") || '<article class="gap gap--clear"><h3>No material gaps found'
        + '</h3><p class="finding">Based on your answers, your coverage lines '
        + "up with your income, debts and assets. Re-run this every January or "
        + "after any major change.</p></article>";

    var winsHtml = result.wins.length
      ? '<div class="wins"><h3>What you already have right</h3><ul>'
        + result.wins.map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("")
        + "</ul></div>"
      : "";

    reportBox.innerHTML =
      '<div class="report-inner">'
      + '<p class="report-kicker">Your Coverage Gap Report</p>'
      + "<h2>" + (name ? esc(name) + ", here" : "Here")
      + "&rsquo;s where your protection actually stands.</h2>"
      + '<p class="report-lede">' + esc(result.headline) + "</p>"

      + '<div class="scorecard">'
      + '<svg class="ring" viewBox="0 0 128 128" width="128" height="128" '
      + 'role="img" aria-label="Protection score ' + result.score + ' out of 100">'
      + '<circle cx="64" cy="64" r="54" fill="none" stroke="#3a3b63" stroke-width="12"/>'
      + '<circle cx="64" cy="64" r="54" fill="none" stroke="#ffd166" stroke-width="12" '
      + 'stroke-linecap="round" stroke-dasharray="' + dash.toFixed(1) + " "
      + circumference.toFixed(1) + '" transform="rotate(-90 64 64)"/>'
      + '<text x="64" y="72" text-anchor="middle" font-size="32" fill="#fff">'
      + result.score + "</text></svg>"
      + '<div class="scoretext"><h3>' + esc(result.band) + "</h3>"
      + "<p>Your protection score, out of 100. It drops for every gap we "
      + "found, weighted by how badly that gap would hurt at claim time.</p>"
      + "</div></div>"

      + '<div class="totals">'
      + '<div class="stat"><b>' + engine.money(result.total_dollar_gap)
      + "</b><span>Total estimated exposure</span></div>"
      + '<div class="stat"><b>' + engine.money(result.life_need)
      + "</b><span>Life coverage your household profile suggests</span></div>"
      + '<div class="stat"><b>' + result.gaps.length
      + "</b><span>Gaps identified</span></div></div>"

      + "<h3 class=\"report-h\">Your gaps, worst first</h3>" + gapsHtml + winsHtml
      + '<p class="report-actions">'
      + '<button type="button" class="btn btn-primary" id="printReport">'
      + "Save as PDF</button></p>"
      + "</div>";

    reportBox.hidden = false;
    document.getElementById("printReport")
      .addEventListener("click", function () { window.print(); });
  }

  /* --- submit ---------------------------------------------------------- */
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var data = new FormData(form);
    var email = (data.get("email") || "").trim();

    if (!/^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$/.test(email)) {
      return fail("Please enter a valid email address so we can send the report.");
    }
    if (!data.get("consent")) {
      return fail("Please check the box so we're allowed to email your report.");
    }

    submitBtn.disabled = true;
    submitBtn.textContent = "Building your report…";

    var quiz = answers();
    var result = lastResult || engine.scorePayload(quiz);
    var name = (data.get("first_name") || "").trim();

    var payload = new URLSearchParams({
      "form-name": "coverage-gap-lead",
      first_name: name,
      email: email,
      zip_code: (data.get("zip_code") || "").trim(),
      score: String(result.score),
      band: result.band,
      total_gap: engine.money(result.total_dollar_gap),
      top_gap: result.gaps.length ? result.gaps[0].title : "none",
      source: source(),
      company: "",
      answers: JSON.stringify(quiz)
    });

    fetch("/", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: payload.toString()
    })
      .then(function (r) {
        if (!r.ok) { throw new Error("Submission failed (" + r.status + ")"); }
        finish(name, result);
      })
      .catch(function () {
        /* Never trap someone's report behind a form error - they answered ten
           questions and have earned the result either way. */
        finish(name, result);
      });
  });

  function finish(name, result) {
    form.hidden = true;
    document.querySelector(".progress").hidden = true;
    label.hidden = true;
    doneBox.hidden = false;
    renderReport(name, result);
    var share = document.getElementById("shareLink");
    if (share) { share.href = window.location.origin + "/?src=referral"; }
    doneBox.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function fail(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
    submitBtn.disabled = false;
    submitBtn.textContent = "Send me my report →";
  }

  show(0, false);
})();

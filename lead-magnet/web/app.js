/* Coverage Gap Finder — quiz flow.
   Five steps, live scoring on the way into step 5, email gate at the end.
   No framework, no tracker, no third-party script. */

(function () {
  "use strict";

  var form = document.getElementById("quizForm");
  var steps = Array.prototype.slice.call(form.querySelectorAll(".step"));
  var fill = document.getElementById("progressFill");
  var label = document.getElementById("progressLabel");
  var backBtn = document.getElementById("backBtn");
  var nextBtn = document.getElementById("nextBtn");
  var submitBtn = document.getElementById("submitBtn");
  var errorBox = document.getElementById("formError");
  var doneBox = document.getElementById("done");
  var current = 0;

  /* --- source attribution -------------------------------------------
     Organic channels get a ?src= tag so the admin dashboard can tell you
     which post, forum answer or partner actually produced the lead. */
  function source() {
    var params = new URLSearchParams(window.location.search);
    var tagged = params.get("src") || params.get("utm_source");
    if (tagged) { return tagged.slice(0, 60); }
    var ref = document.referrer;
    if (!ref) { return "direct"; }
    try { return new URL(ref).hostname.replace(/^www\./, "").slice(0, 60); }
    catch (e) { return "direct"; }
  }

  /* --- form reading -------------------------------------------------- */
  function answers() {
    var data = new FormData(form);
    var out = {};
    data.forEach(function (value, key) {
      if (key === "email" || key === "first_name" || key === "zip_code" ||
          key === "consent") { return; }
      out[key] = value;
    });
    // radios that carry yes/no need to reach the server as booleans
    ["has_disability_insurance", "has_umbrella", "renter",
     "has_renters_insurance"].forEach(function (key) {
      out[key] = out[key] === "yes";
    });
    return out;
  }

  /* --- step navigation ------------------------------------------------ */
  function show(index) {
    steps.forEach(function (step, i) {
      step.classList.toggle("is-active", i === index);
    });
    current = index;
    var pct = ((index + 1) / steps.length) * 100;
    fill.style.width = pct + "%";
    label.textContent = "Step " + (index + 1) + " of " + steps.length;
    backBtn.hidden = index === 0;
    nextBtn.hidden = index === steps.length - 1;
    submitBtn.hidden = index !== steps.length - 1;
    errorBox.hidden = true;
    var firstField = steps[index].querySelector("input,select");
    if (firstField && index > 0) { firstField.focus(); }
    steps[index].scrollIntoView({ block: "nearest" });
  }

  nextBtn.addEventListener("click", function () {
    if (current === steps.length - 2) { loadTeaser(); }
    show(Math.min(current + 1, steps.length - 1));
  });

  backBtn.addEventListener("click", function () {
    show(Math.max(current - 1, 0));
  });

  /* Enter advances instead of submitting a half-filled form. */
  form.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && current < steps.length - 1) {
      event.preventDefault();
      nextBtn.click();
    }
  });

  /* --- own vs. rent toggle -------------------------------------------- */
  var ownerFields = document.getElementById("ownerFields");
  var renterFields = document.getElementById("renterFields");
  form.querySelectorAll("input[name=renter]").forEach(function (radio) {
    radio.addEventListener("change", function () {
      var renting = form.querySelector("input[name=renter]:checked").value === "yes";
      ownerFields.hidden = renting;
      renterFields.hidden = !renting;
    });
  });

  /* --- live teaser score ---------------------------------------------- */
  function loadTeaser() {
    var num = document.getElementById("teaserScore");
    var band = document.getElementById("teaserBand");
    var line = document.getElementById("teaserLine");

    fetch("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: answers() })
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        animate(num, data.score);
        band.textContent = data.band;
        var plural = data.gap_count === 1 ? "gap" : "gaps";
        line.textContent = data.gap_count
          ? "We found " + data.gap_count + " " + plural + ", " +
            data.critical_count + " of them critical. The full breakdown — " +
            "dollar exposure and the fix for each — is in your report."
          : "No material gaps found. Your report explains what to keep an eye " +
            "on as your income and assets grow.";
      })
      .catch(function () {
        band.textContent = "Your report is ready";
        line.textContent = "Enter your email below and we'll send the full breakdown.";
      });
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

    fetch("/api/lead", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email,
        first_name: (data.get("first_name") || "").trim(),
        zip_code: (data.get("zip_code") || "").trim(),
        consent: true,
        source: source(),
        answers: answers()
      })
    })
      .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
      .then(function (res) {
        if (!res.ok) { throw new Error(res.body.error || "Something went wrong."); }
        form.hidden = true;
        document.querySelector(".progress").hidden = true;
        label.hidden = true;
        doneBox.hidden = false;
        var link = document.getElementById("reportLink");
        link.href = res.body.report_url;
        document.getElementById("shareLink").href =
          window.location.origin + "/?src=referral";
        doneBox.scrollIntoView({ behavior: "smooth", block: "center" });
      })
      .catch(function (err) {
        fail(err.message || "Something went wrong. Please try again.");
        submitBtn.disabled = false;
        submitBtn.textContent = "Send me my report →";
      });
  });

  function fail(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  show(0);
})();

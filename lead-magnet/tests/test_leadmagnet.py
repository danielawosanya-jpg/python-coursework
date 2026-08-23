"""Tests for the Coverage Gap Finder.

    python3 -m unittest discover -s tests -v
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from leadmagnet import config, report, scoring, sequences, storage  # noqa: E402


class TestScoring(unittest.TestCase):

    def test_dime_need_includes_every_component(self):
        a = scoring.Answers(age=40, annual_income=100_000, dependents=2,
                            mortgage_balance=200_000, other_debt=20_000,
                            liquid_savings=10_000)
        expected = (20_000 + 100_000 * 10 + 200_000
                    + 2 * scoring.COLLEGE_COST_PER_CHILD
                    + scoring.FINAL_EXPENSE - 10_000)
        self.assertEqual(scoring.life_insurance_need(a), expected)

    def test_income_replacement_years_taper_after_55(self):
        young = scoring.Answers(age=40, annual_income=100_000)
        older = scoring.Answers(age=65, annual_income=100_000)
        self.assertLess(scoring.life_insurance_need(older),
                        scoring.life_insurance_need(young))

    def test_need_never_negative(self):
        a = scoring.Answers(annual_income=50_000, liquid_savings=10_000_000)
        self.assertEqual(scoring.life_insurance_need(a), 0.0)

    def test_well_covered_profile_scores_high(self):
        a = scoring.Answers(age=45, annual_income=120_000, dependents=0,
                            mortgage_balance=0, other_debt=0,
                            liquid_savings=120_000,
                            existing_life_coverage=1_500_000,
                            auto_liability_limit=250_000,
                            home_value=400_000, home_dwelling_coverage=400_000,
                            has_disability_insurance=True, has_umbrella=True,
                            net_worth=400_000)
        result = scoring.score(a)
        self.assertEqual(result.gaps, [])
        self.assertEqual(result.score, 100)
        self.assertEqual(result.band, "Well Protected")
        self.assertTrue(result.wins)

    def test_exposed_profile_surfaces_critical_gaps(self):
        a = scoring.Answers(age=38, annual_income=95_000, dependents=2,
                            mortgage_balance=310_000, other_debt=28_000,
                            liquid_savings=5_000, existing_life_coverage=50_000,
                            auto_liability_limit=25_000, home_value=500_000,
                            home_dwelling_coverage=300_000, net_worth=200_000)
        result = scoring.score(a)
        keys = {g.key for g in result.gaps}
        self.assertIn("life", keys)
        self.assertIn("disability", keys)
        self.assertIn("auto", keys)
        self.assertLess(result.score, 50)
        self.assertEqual(result.band, "Seriously Exposed")

    def test_gaps_are_sorted_worst_first(self):
        result = scoring.score(scoring.Answers(
            age=38, annual_income=95_000, dependents=1,
            mortgage_balance=200_000, auto_liability_limit=25_000,
            home_value=300_000, home_dwelling_coverage=300_000))
        order = {"critical": 0, "important": 1, "watch": 2}
        ranks = [order[g.severity] for g in result.gaps]
        self.assertEqual(ranks, sorted(ranks))

    def test_score_is_clamped_to_range(self):
        worst = scoring.score(scoring.Answers(
            age=30, annual_income=200_000, dependents=4,
            mortgage_balance=800_000, other_debt=100_000,
            auto_liability_limit=25_000, home_value=900_000,
            home_dwelling_coverage=100_000, net_worth=900_000))
        self.assertGreaterEqual(worst.score, 5)
        self.assertLessEqual(worst.score, 100)

    def test_renter_without_renters_insurance_is_flagged(self):
        result = scoring.score(scoring.Answers(
            age=28, annual_income=60_000, renter=True,
            has_renters_insurance=False, auto_liability_limit=250_000))
        self.assertIn("renters", {g.key for g in result.gaps})

    def test_renter_is_not_checked_for_dwelling_coverage(self):
        result = scoring.score(scoring.Answers(
            age=28, annual_income=60_000, renter=True,
            has_renters_insurance=True, home_value=400_000,
            auto_liability_limit=250_000))
        self.assertNotIn("home", {g.key for g in result.gaps})

    def test_umbrella_triggers_on_exposed_equity(self):
        result = scoring.score(scoring.Answers(
            age=50, annual_income=150_000, liquid_savings=200_000,
            existing_life_coverage=5_000_000, auto_liability_limit=250_000,
            home_value=900_000, home_dwelling_coverage=900_000,
            mortgage_balance=100_000, has_disability_insurance=True))
        self.assertIn("umbrella", {g.key for g in result.gaps})


class TestAnswerCoercion(unittest.TestCase):

    def test_currency_strings_are_parsed(self):
        a = scoring.Answers.from_payload({"annual_income": "$95,000"})
        self.assertEqual(a.annual_income, 95_000.0)

    def test_garbage_falls_back_to_default(self):
        a = scoring.Answers.from_payload({"annual_income": "abc", "age": ""})
        self.assertEqual(a.annual_income, 0.0)
        self.assertEqual(a.age, 40)

    def test_values_are_clamped(self):
        a = scoring.Answers.from_payload({"age": 300, "dependents": 999})
        self.assertEqual(a.age, 100)
        self.assertEqual(a.dependents, 12)

    def test_booleans_accept_common_truthy_forms(self):
        for truthy in ("yes", "true", "1", "on", True):
            with self.subTest(truthy=truthy):
                a = scoring.Answers.from_payload({"has_umbrella": truthy})
                self.assertTrue(a.has_umbrella)
        self.assertFalse(scoring.Answers.from_payload({"has_umbrella": "no"}).has_umbrella)

    def test_negative_amounts_are_floored_at_zero(self):
        a = scoring.Answers.from_payload({"mortgage_balance": "-50000"})
        self.assertEqual(a.mortgage_balance, 0.0)


class TestStorage(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Path(self.dir.name) / "test.db"
        storage.init_db(self.db)

    def tearDown(self):
        self.dir.cleanup()

    def _save(self, email="alex@example.com"):
        result = scoring.score(scoring.Answers(
            age=38, annual_income=95_000, dependents=2,
            mortgage_balance=310_000, auto_liability_limit=25_000)).to_dict()
        return storage.save_lead(email=email, first_name="Alex", zip_code="30301",
                                 consent=True, source="reddit",
                                 answers={"age": 38}, result=result,
                                 db_path=self.db)

    def test_save_and_fetch_roundtrip(self):
        token = self._save()
        lead = storage.get_lead(token, self.db)
        self.assertEqual(lead["email"], "alex@example.com")
        self.assertEqual(lead["source"], "reddit")
        self.assertTrue(lead["result"]["gaps"])

    def test_email_is_normalized(self):
        token = storage.save_lead(email="  MixedCase@Example.COM ",
                                  consent=True, db_path=self.db)
        self.assertEqual(storage.get_lead(token, self.db)["email"],
                         "mixedcase@example.com")

    def test_invalid_email_rejected(self):
        for bad in ("", "nope", "a@b", "a b@c.com"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    storage.save_lead(email=bad, db_path=self.db)

    def test_resubmitting_reuses_the_original_token(self):
        first = self._save()
        second = self._save()
        self.assertEqual(first, second)
        self.assertEqual(len(storage.list_leads(db_path=self.db)), 1)

    def test_unsubscribe_marks_lead_and_clears_pending_mail(self):
        token = self._save()
        lead = storage.get_lead(token, self.db)
        storage.enqueue(lead["id"], sequences.schedule_for(lead), db_path=self.db)
        self.assertTrue(storage.unsubscribe(token, self.db))
        self.assertIsNotNone(storage.get_lead(token, self.db)["unsubscribed_at"])
        self.assertEqual(storage.due_emails(db_path=self.db), [])
        self.assertFalse(storage.unsubscribe(token, self.db))  # idempotent

    def test_csv_export_has_header_and_rows(self):
        self._save()
        self._save("jordan@example.com")
        csv_text = storage.export_csv(self.db)
        self.assertTrue(csv_text.startswith("id,created_at,first_name,email"))
        self.assertIn("jordan@example.com", csv_text)
        self.assertEqual(len(csv_text.strip().splitlines()), 3)

    def test_stats_counts_hot_leads(self):
        self._save()
        s = storage.stats(self.db)
        self.assertEqual(s["total_leads"], 1)
        self.assertEqual(s["hot_leads"], 1)
        self.assertEqual(s["by_source"][0]["source"], "reddit")


class TestQueue(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Path(self.dir.name) / "q.db"
        storage.init_db(self.db)
        token = storage.save_lead(email="sam@example.com", first_name="Sam",
                                  consent=True, db_path=self.db,
                                  result=scoring.score(scoring.Answers(
                                      annual_income=80_000, dependents=1,
                                      auto_liability_limit=25_000)).to_dict())
        self.lead = storage.get_lead(token, self.db)

    def tearDown(self):
        self.dir.cleanup()

    def test_full_sequence_is_queued_once(self):
        added = storage.enqueue(self.lead["id"],
                                sequences.schedule_for(self.lead), db_path=self.db)
        self.assertEqual(added, len(sequences.SCHEDULE))
        again = storage.enqueue(self.lead["id"],
                                sequences.schedule_for(self.lead), db_path=self.db)
        self.assertEqual(again, 0)

    def test_only_the_first_email_is_due_immediately(self):
        storage.enqueue(self.lead["id"], sequences.schedule_for(self.lead),
                        db_path=self.db)
        due = storage.due_emails(db_path=self.db)
        self.assertEqual([d["step"] for d in due], [1])

    def test_later_steps_come_due_on_schedule(self):
        storage.enqueue(self.lead["id"], sequences.schedule_for(self.lead),
                        db_path=self.db)
        future = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
        self.assertEqual(len(storage.due_emails(future, self.db)),
                         len(sequences.SCHEDULE))

    def test_mark_sent_removes_from_due(self):
        storage.enqueue(self.lead["id"], sequences.schedule_for(self.lead),
                        db_path=self.db)
        storage.mark_sent(storage.due_emails(db_path=self.db)[0]["id"], self.db)
        self.assertEqual(storage.due_emails(db_path=self.db), [])


class TestSequences(unittest.TestCase):

    def setUp(self):
        result = scoring.score(scoring.Answers(
            age=38, annual_income=95_000, dependents=2,
            mortgage_balance=310_000, auto_liability_limit=25_000)).to_dict()
        self.lead = {"first_name": "Alex", "token": "tok123", "result": result}

    def test_every_step_renders(self):
        emails = sequences.render_sequence(self.lead)
        self.assertEqual(len(emails), len(sequences.SCHEDULE))
        for email in emails:
            self.assertTrue(email["subject"])
            self.assertIn("Alex", email["body"])

    def test_mailto_fallback_never_reaches_the_reader_raw(self):
        from leadmagnet import config as cfg
        original = dict(sequences.AGENCY)
        sequences.AGENCY["calendar_url"] = "mailto:daniel@example.com"
        try:
            body = sequences.render_sequence(self.lead)[4]["body"]
            self.assertIn("daniel@example.com", body)
            self.assertNotIn("mailto:", body)
        finally:
            sequences.AGENCY.clear()
            sequences.AGENCY.update(original)

    def test_every_email_carries_an_unsubscribe_link(self):
        for email in sequences.render_sequence(self.lead):
            self.assertIn("/unsubscribe?t=tok123", email["body"])

    def test_every_email_carries_the_physical_address(self):
        # CAN-SPAM requires a valid physical postal address in every message.
        for email in sequences.render_sequence(self.lead):
            self.assertIn(sequences.AGENCY["mailing_address"], email["body"])

    def test_missing_name_degrades_gracefully(self):
        body = sequences.render_sequence(
            {"first_name": "", "token": "t", "result": {}})[0]["body"]
        self.assertTrue(body.startswith("there,"))

    def test_clean_report_uses_the_no_gap_variant(self):
        clean = scoring.score(scoring.Answers(
            age=45, annual_income=120_000, liquid_savings=120_000,
            existing_life_coverage=2_000_000, auto_liability_limit=250_000,
            has_disability_insurance=True, has_umbrella=True)).to_dict()
        body = sequences.render_sequence(
            {"first_name": "Pat", "token": "t", "result": clean})[1]["body"]
        self.assertIn("came back clean", body)


class TestReport(unittest.TestCase):

    def _render(self, answers, name="Alex"):
        return report.render_report({
            "first_name": name, "token": "tok123",
            "result": scoring.score(answers).to_dict()})

    def test_report_contains_score_and_gaps(self):
        html = self._render(scoring.Answers(
            age=38, annual_income=95_000, dependents=2,
            mortgage_balance=310_000, auto_liability_limit=25_000))
        self.assertIn("Coverage Gap Report", html)
        self.assertIn("Life insurance shortfall", html)
        self.assertIn("Alex", html)
        self.assertIn("/unsubscribe?t=tok123", html)

    def test_report_carries_the_required_disclaimer(self):
        html = self._render(scoring.Answers(annual_income=50_000))
        flat = " ".join(html.split())  # the disclaimer wraps across lines
        self.assertIn("not insurance, legal or tax advice", flat)
        self.assertIn("not an offer of coverage", flat)
        self.assertIn("license", flat.lower())

    def test_clean_profile_renders_the_no_gap_state(self):
        html = self._render(scoring.Answers(
            age=45, annual_income=120_000, liquid_savings=120_000,
            existing_life_coverage=2_000_000, auto_liability_limit=250_000,
            has_disability_insurance=True, has_umbrella=True))
        self.assertIn("No material gaps found", html)

    def test_report_carries_the_brand_palette(self):
        # The style block lives inside an f-string with doubled braces, which
        # makes a naive edit silently no-op. Assert the colours actually land.
        html = self._render(scoring.Answers(annual_income=50_000))
        for token in ("--navy: #191a3d", "--gold: #ffd166", "--cream: #fdfaef"):
            self.assertIn(token, html)
        self.assertIn("background:var(--navy)", html)   # scorecard and CTA
        self.assertNotIn("#0f5c4a", html)               # the old accent colour

    def test_name_is_html_escaped(self):
        html = self._render(scoring.Answers(annual_income=50_000),
                            name="<script>alert(1)</script>")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestConfig(unittest.TestCase):
    """The agency details are legally significant, so guard the loader."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "agency.json"

    def tearDown(self):
        self.dir.cleanup()

    def _real(self, **overrides):
        values = {
            "agent_name": "Dana Reyes", "agency_name": "Reyes Insurance",
            "license": "GA license #1234567", "phone": "404-555-0100",
            "calendar_url": "https://cal.com/dana", "site_url": "https://reyes.example",
            "mailing_address": "12 Peachtree St, Atlanta, GA 30301",
            "states_licensed": "GA, FL",
        }
        values.update(overrides)
        return values

    def test_missing_file_falls_back_to_placeholders(self):
        loaded = config.load(self.path)
        self.assertEqual(loaded, config.DEFAULTS)
        self.assertFalse(config.is_configured(loaded))

    def test_roundtrip(self):
        config.save(self._real(), self.path)
        self.assertEqual(config.load(self.path)["license"], "GA license #1234567")
        self.assertTrue(config.is_configured(config.load(self.path)))

    def test_blank_values_fall_back_rather_than_shipping_empty(self):
        config.save(self._real(phone="   "), self.path)
        self.assertEqual(config.load(self.path)["phone"], config.DEFAULTS["phone"])

    def test_partial_config_reports_exactly_what_is_missing(self):
        config.save(self._real(license=config.DEFAULTS["license"]), self.path)
        self.assertEqual(config.placeholders_remaining(config.load(self.path)),
                         ["license"])

    def test_trailing_slash_stripped_so_report_urls_stay_clean(self):
        config.save(self._real(site_url="https://reyes.example/"), self.path)
        self.assertEqual(config.load(self.path)["site_url"], "https://reyes.example")

    def test_corrupt_json_raises_rather_than_silently_shipping_placeholders(self):
        self.path.write_text("{not json")
        with self.assertRaises(RuntimeError):
            config.load(self.path)

    def test_cta_url_form_offers_a_booking(self):
        values = self._real(calendar_url="https://cal.com/dana/review")
        cta = config.cta(values)
        self.assertEqual(cta["kind"], "url")
        self.assertIn("Book", cta["button"])
        self.assertIn("cal.com", cta["offer"])

    def test_cta_mailto_does_not_promise_a_booking(self):
        cta = config.cta(self._real(calendar_url="mailto:dana@reyes.example"))
        self.assertEqual(cta["kind"], "mailto")
        self.assertNotIn("Book", cta["button"])
        # A raw "mailto:" pasted mid-sentence looks broken to a reader.
        self.assertNotIn("mailto:", cta["offer"])
        self.assertIn("dana@reyes.example", cta["offer"])

    def test_cta_mailto_gets_a_subject_but_keeps_an_existing_one(self):
        plain = config.cta(self._real(calendar_url="mailto:d@x.example"))
        self.assertIn("subject=", plain["href"])
        custom = config.cta(
            self._real(calendar_url="mailto:d@x.example?subject=Hello"))
        self.assertTrue(custom["href"].endswith("subject=Hello"))

    def test_render_substitutes_every_token(self):
        values = self._real()
        markup = config.render(
            "<p>{{agency_name}} - {{license}} - {{mailing_address}}</p>", values)
        self.assertIn("Reyes Insurance", markup)
        self.assertIn("GA license #1234567", markup)
        self.assertNotIn("{{", markup)

    def test_render_leaves_unknown_tokens_alone(self):
        self.assertIn("{{not_a_field}}",
                      config.render("{{not_a_field}}", self._real()))

    def test_landing_page_has_no_hardcoded_agency_details(self):
        # The licence and address must come from agency.json, not the markup.
        markup = (Path(__file__).resolve().parent.parent
                  / "web" / "index.html").read_text()
        for stale in ("[Your Agency]", "[Your Name]", "[State] license",
                      "[Street, City", "[ST, ST]"):
            self.assertNotIn(stale, markup)
        self.assertIn("{{agency_name}}", markup)
        self.assertIn("{{license}}", markup)


class TestSenderGuards(unittest.TestCase):
    """Guards against the two ways a sending address silently breaks."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        import preflight
        self.preflight = preflight

    def test_sender_domain_parses_both_address_forms(self):
        parse = self.preflight._sender_domain
        self.assertEqual(parse("dana@reyes.example"), "reyes.example")
        self.assertEqual(parse("Dana Reyes <dana@Reyes.Example>"), "reyes.example")
        self.assertEqual(parse("  dana@reyes.example  "), "reyes.example")

    def test_consumer_domains_are_recognised(self):
        for address in ("a@gmail.com", "Someone <b@yahoo.com>", "c@outlook.com"):
            with self.subTest(address=address):
                self.assertIn(self.preflight._sender_domain(address),
                              self.preflight.CONSUMER_MAIL_DOMAINS)

    def test_business_domain_is_not_flagged_as_consumer(self):
        self.assertNotIn(self.preflight._sender_domain("dana@reyes.example"),
                         self.preflight.CONSUMER_MAIL_DOMAINS)


class TestApiContract(unittest.TestCase):
    """The teaser endpoint must never leak the gap detail the email buys."""

    def test_teaser_shape_excludes_gap_detail(self):
        result = scoring.score_payload({"annual_income": "95000",
                                        "dependents": "2"}).to_dict()
        teaser = {
            "score": result["score"], "band": result["band"],
            "gap_count": len(result["gaps"]),
            "critical_count": sum(1 for g in result["gaps"]
                                  if g["severity"] == "critical"),
            "total_dollar_gap": result["total_dollar_gap"],
            "headline": result["headline"],
        }
        self.assertNotIn("gaps", teaser)
        self.assertTrue(json.dumps(teaser))  # JSON-serializable
        self.assertGreater(teaser["gap_count"], 0)


if __name__ == "__main__":
    unittest.main()

"""The browser engine must agree with the Python engine, exactly.

static/scoring.js is a hand port of leadmagnet/scoring.py. Two implementations
of the same rules drift the moment someone edits one of them, and a drifted
scorer means the number on the screen disagrees with the number in the email.

This runs the shipped .js file under Node against the Python engine over a
spread of profiles, including the boundary cases where rounding usually
diverges. Skips (does not fail) when Node is unavailable.
"""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from leadmagnet import scoring  # noqa: E402

ENGINE = ROOT / "static" / "scoring.js"

PROFILES = [
    {},                                                   # empty
    {"age": 38, "annual_income": "95000", "spouse_income": "60000",
     "dependents": 2, "mortgage_balance": "310000", "other_debt": "28000",
     "liquid_savings": "18000", "existing_life_coverage": "100000",
     "auto_liability_limit": "50000", "home_value": "520000",
     "home_dwelling_coverage": "350000", "net_worth": "240000"},
    {"age": 45, "annual_income": "120000", "liquid_savings": "120000",
     "existing_life_coverage": "2000000", "auto_liability_limit": "250000",
     "home_value": "400000", "home_dwelling_coverage": "400000",
     "has_disability_insurance": "yes", "has_umbrella": "yes",
     "net_worth": "400000"},                              # clean sheet
    {"age": 28, "annual_income": "60000", "renter": "yes",
     "has_renters_insurance": "no", "auto_liability_limit": "25000"},
    {"age": 28, "annual_income": "60000", "renter": "yes",
     "has_renters_insurance": "yes", "auto_liability_limit": "250000",
     "liquid_savings": "40000"},
    {"age": 65, "annual_income": "80000", "dependents": 0,
     "auto_liability_limit": "100000"},                   # income taper
    {"age": 55, "annual_income": "80000", "auto_liability_limit": "100000"},
    {"age": 30, "annual_income": "200000", "dependents": 4,
     "mortgage_balance": "800000", "other_debt": "100000",
     "auto_liability_limit": "25000", "home_value": "900000",
     "home_dwelling_coverage": "100000", "net_worth": "900000"},  # worst case
    {"annual_income": "50000", "liquid_savings": "10000000"},     # need floors at 0
    {"annual_income": "$95,000", "dependents": "2"},              # currency string
    {"age": 300, "dependents": 999, "annual_income": "abc"},      # clamped/garbage
    {"age": 50, "annual_income": "150000", "liquid_savings": "200000",
     "existing_life_coverage": "5000000", "auto_liability_limit": "250000",
     "home_value": "900000", "home_dwelling_coverage": "900000",
     "mortgage_balance": "100000", "has_disability_insurance": "yes"},  # umbrella
    {"annual_income": "100000", "auto_liability_limit": "99999"},  # just under floor
    {"annual_income": "100000", "auto_liability_limit": "100000"}, # exactly floor
    {"annual_income": "100000", "auto_liability_limit": "25000"},  # exactly minimum
    {"annual_income": "100000", "auto_liability_limit": "25001"},  # just over
    {"annual_income": "80000", "home_value": "500000",
     "home_dwelling_coverage": "400000"},                  # exactly 80% coinsurance
    {"annual_income": "80000", "net_worth": "500000"},     # exactly umbrella trigger
    {"annual_income": "80000", "net_worth": "499999"},     # just under
]


def node_score(payload: dict) -> dict:
    script = (
        f"const cg=require({str(ENGINE)!r});"
        f"const r=cg.scorePayload({json.dumps(payload)});"
        "process.stdout.write(JSON.stringify(r));"
    )
    out = subprocess.run([shutil.which("node"), "-e", script],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "Node is not installed")
class TestEngineParity(unittest.TestCase):

    def assert_same(self, payload):
        py = scoring.score_payload(payload).to_dict()
        js = node_score(payload)

        self.assertEqual(js["score"], py["score"], f"score differs for {payload}")
        self.assertEqual(js["band"], py["band"], f"band differs for {payload}")
        self.assertEqual(js["headline"], py["headline"])
        self.assertAlmostEqual(js["life_need"], py["life_need"], places=4)
        self.assertAlmostEqual(js["life_gap"], py["life_gap"], places=4)
        self.assertAlmostEqual(js["total_dollar_gap"], py["total_dollar_gap"],
                               places=4)

        self.assertEqual([g["key"] for g in js["gaps"]],
                         [g["key"] for g in py["gaps"]],
                         f"gap order differs for {payload}")
        for got, want in zip(js["gaps"], py["gaps"]):
            self.assertEqual(got["severity"], want["severity"])
            self.assertEqual(got["title"], want["title"])
            self.assertAlmostEqual(got["dollar_gap"], want["dollar_gap"], places=4)
            # Findings embed formatted currency, so this catches rounding drift.
            self.assertEqual(got["finding"], want["finding"])
            self.assertEqual(got["fix"], want["fix"])

        self.assertEqual(js["wins"], py["wins"], f"wins differ for {payload}")

    def test_every_profile_scores_identically(self):
        for index, payload in enumerate(PROFILES):
            with self.subTest(profile=index):
                self.assert_same(payload)

    def test_engine_file_is_the_one_the_site_ships(self):
        self.assertTrue(ENGINE.is_file())
        markup = (ROOT / "static" / "index.html").read_text()
        self.assertIn("scoring.js", markup)


if __name__ == "__main__":
    unittest.main()

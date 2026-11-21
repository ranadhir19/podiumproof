"""podiumproof test suite.

The core tests are evidentiary: the synthetic fixtures plant known
defects (and one known-good run), and the audit must catch exactly what
was planted and clear exactly what was not.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from podiumproof import checks, judgemodel  # noqa: E402
from podiumproof.fixture import build_fixture  # noqa: E402
from podiumproof.ingest import AuditError, load_run  # noqa: E402
from podiumproof.oracle import (extract_answer, load_oracle,  # noqa: E402
                                normalize_answer)


def audit_dir(path, **kw):
    run = load_run(path)
    oracle = load_oracle(run, oracle_path=kw.get("oracle_path"),
                         correct_answer=kw.get("correct_answer"))
    return run, oracle, checks.run_checks(run, oracle)


def verdicts(result):
    return {c["id"]: c["verdict"] for c in result["claims"]}


class FixtureBase(unittest.TestCase):
    scenario = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="podiumproof-test-")
        cls.dir = build_fixture(os.path.join(cls.tmp, cls.scenario),
                                cls.scenario)
        cls.rundata, cls.oracle, cls.result = audit_dir(
            cls.dir, oracle_path=os.path.join(cls.dir, "oracle.json"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestFlawedFixture(FixtureBase):
    scenario = "flawed"

    def test_ingest(self):
        self.assertEqual(self.rundata.champion, "a012")
        self.assertEqual(self.rundata.agents_n, 16)
        self.assertEqual(self.rundata.rounds_count, 4)
        self.assertEqual(len([m for m in self.rundata.matches if m.played]), 15)
        self.assertEqual(self.result["calls"]["total"], 91)

    def test_verdicts_catch_every_planted_defect(self):
        self.assertEqual(verdicts(self.result), {
            "C1a": "REFUTED",   # champion is not the pool's best
            "C1b": "SUPPORTED",  # but the pool genuinely had headroom
            "C2": "REFUTED",    # champion does not reproduce under re-seeding
            "C3a": "REFUTED",   # judge accuracy at/below chance
            "C3b": "REFUTED",   # material position bias
            "C3c": "REFUTED",   # fatal-flaw canary reached the final
            "C4": "REFUTED",    # champion below a random pick's expectation
        })

    def test_stamp(self):
        self.assertEqual(self.result["stamp"], "JUDGE ARTEFACT")

    def test_champion_rank_and_regret(self):
        c1a = next(c for c in self.result["claims"] if c["id"] == "C1a")
        self.assertEqual(c1a["evidence"]["champion_pool_rank"], 7)
        self.assertAlmostEqual(c1a["evidence"]["regret"], 0.66, places=2)
        self.assertEqual(c1a["evidence"]["champion_final_answer_score"], 0.0)

    def test_judge_model(self):
        fit = self.result["fit"]
        self.assertTrue(fit.ok)
        self.assertAlmostEqual(fit.accuracy, 7.0 / 15.0, places=3)
        self.assertGreater(fit.alpha, 0.5)       # planted first-position bias
        self.assertLess(fit.beta, 1.0)           # verdicts barely track quality
        self.assertLess(fit.swap_consistency, 0.8)

    def test_stability(self):
        rep = self.result["replay"]
        self.assertLess(rep["champion_reproduction_rate"], 0.2)
        self.assertGreater(rep["distinct_champions"], 8)

    def test_canary(self):
        c3c = next(c for c in self.result["claims"] if c["id"] == "C3c")
        self.assertEqual(c3c["evidence"]["canary_fates"]["a007"],
                         "reached the final round")
        self.assertEqual(
            c3c["evidence"]["matches_where_judge_flagged_the_flaw"]["a007"], 0)

    def test_cost_ledger(self):
        led = self.result["cost_ledger"]
        self.assertAlmostEqual(led["baselines"]["random_pick_expected"],
                               0.3656, places=3)
        self.assertAlmostEqual(led["baselines"]["majority_vote"],
                               0.2667, places=3)
        self.assertLess(led["premiums"]["random_pick_expected"], 0.0)
        self.assertEqual(led["majority_modal_answer"], "42")


class TestSoundFixture(FixtureBase):
    scenario = "sound"

    def test_ingest(self):
        self.assertEqual(self.rundata.champion, "a005")
        self.assertEqual(self.result["calls"]["total"], 43)

    def test_verdicts_clear_the_sound_run(self):
        self.assertEqual(verdicts(self.result), {
            "C1a": "SUPPORTED", "C1b": "SUPPORTED", "C2": "SUPPORTED",
            "C3a": "SUPPORTED", "C3b": "SUPPORTED", "C3c": "SUPPORTED",
            "C4": "SUPPORTED",
        })

    def test_stamp(self):
        self.assertEqual(self.result["stamp"], "PREMIUM REAL")

    def test_numbers(self):
        fit = self.result["fit"]
        self.assertEqual(fit.accuracy, 1.0)
        self.assertGreater(fit.swap_consistency, 0.9)
        self.assertGreater(
            self.result["replay"]["champion_reproduction_rate"], 0.9)
        c3c = next(c for c in self.result["claims"] if c["id"] == "C3c")
        self.assertEqual(c3c["evidence"]["canary_fates"]["a006"],
                         "eliminated in round 1")
        self.assertGreaterEqual(
            c3c["evidence"]["matches_where_judge_flagged_the_flaw"]["a006"], 1)


class TestNoOracle(unittest.TestCase):
    def test_everything_unverifiable_but_audit_runs(self):
        tmp = tempfile.mkdtemp(prefix="podiumproof-test-")
        try:
            d = build_fixture(os.path.join(tmp, "flawed"), "flawed")
            os.remove(os.path.join(d, "oracle.json"))
            run = load_run(d)
            oracle = load_oracle(run)
            self.assertFalse(oracle.has_scores)
            result = checks.run_checks(run, oracle)
            self.assertTrue(all(v == "UNVERIFIABLE"
                                for v in verdicts(result).values()))
            self.assertEqual(result["stamp"], "UNVERIFIABLE")
            self.assertEqual(result["calls"]["total"], 91)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCorrectAnswerMode(unittest.TestCase):
    def test_binary_ground_truth_still_catches_the_wrong_champion(self):
        tmp = tempfile.mkdtemp(prefix="podiumproof-test-")
        try:
            d = build_fixture(os.path.join(tmp, "flawed"), "flawed")
            run = load_run(d)
            oracle = load_oracle(run, correct_answer="8")
            self.assertEqual(oracle.scores["a003"], 1.0)
            self.assertEqual(oracle.scores["a012"], 0.0)
            result = checks.run_checks(run, oracle)
            v = verdicts(result)
            self.assertEqual(v["C1a"], "REFUTED")
            self.assertEqual(v["C4"], "REFUTED")
            # binary scores separate too few matches to fit a judge model:
            # the audit must say so rather than invent one
            self.assertEqual(v["C3a"], "UNVERIFIABLE")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestUnits(unittest.TestCase):
    def test_extract_answer(self):
        self.assertEqual(extract_answer("work\n\nANSWER: 8\n"), "8")
        self.assertEqual(extract_answer("#### 42\n"), "42")
        self.assertEqual(extract_answer("ANSWER: 5\nlater\nANSWER: 8"), "8")
        self.assertIsNone(extract_answer("no marker here"))

    def test_normalize_answer(self):
        self.assertEqual(normalize_answer("8.0"), "8")
        self.assertEqual(normalize_answer("$1,008"), "1008")
        self.assertEqual(normalize_answer(" 42. "), "42")
        self.assertEqual(normalize_answer("Eight"), "eight")

    def test_wilson(self):
        lo, hi = judgemodel.wilson(7, 7)
        self.assertGreater(lo, 0.5)
        lo, hi = judgemodel.wilson(0, 10)
        self.assertLess(hi, 0.35)
        self.assertEqual(judgemodel.wilson(0, 0), (0.0, 1.0))

    def test_missing_arena_json(self):
        tmp = tempfile.mkdtemp(prefix="podiumproof-test-")
        try:
            with self.assertRaises(AuditError):
                load_run(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCli(unittest.TestCase):
    def test_end_to_end(self):
        tmp = tempfile.mkdtemp(prefix="podiumproof-test-")
        try:
            d = os.path.join(tmp, "flawed")
            root = os.path.join(os.path.dirname(__file__), "..")
            env = dict(os.environ, PYTHONPATH=root)
            r = subprocess.run(
                [sys.executable, "-m", "podiumproof", "make-fixture", d,
                 "--scenario", "flawed"],
                capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = os.path.join(tmp, "out")
            r = subprocess.run(
                [sys.executable, "-m", "podiumproof", "audit", d,
                 "--out", out],
                capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("JUDGE ARTEFACT", r.stdout)
            with open(os.path.join(out, "ledger.json")) as fh:
                ledger = json.load(fh)
            self.assertEqual(ledger["stamp"], "JUDGE ARTEFACT")
            self.assertEqual(ledger["run"]["champion"], "a012")
            with open(os.path.join(out, "report.md")) as fh:
                report = fh.read()
            self.assertIn("Summary stamp: JUDGE ARTEFACT", report)
            # a directory with no arena.json is a clean error, exit 2
            r = subprocess.run(
                [sys.executable, "-m", "podiumproof", "audit", tmp,
                 "--out", out],
                capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

# podiumproof

**Did the tournament's winner actually deserve to win?**

Multi-sample selection is everywhere now: sample 100 answers, run them
through a single-elimination bracket judged by an LLM, crown the
survivor. The winner arrives with a record of the attacks it survived —
and no evidence at all that it was the best answer in its own pool,
because nobody ever scores the pool. The judge is usually the same
model as the contestants, judging each match once, in one presentation
order, with no swaps and no panel. And the bill — 595 sub-agent calls
for a 100-agent bracket — is justified against no baseline whatsoever.

podiumproof is the missing instrument: a **selection audit**. Point it
at a finished tournament and it stamps every claim the tournament
implicitly makes — **SUPPORTED**, **REFUTED**, or **UNVERIFIABLE** —
with the measurement attached, and rolls them into one summary stamp:
`PREMIUM REAL`, `WITHIN NOISE`, `JUDGE ARTEFACT`, or `NO HEADROOM`.

Pure Python standard library. Offline. **No model calls** — the audit
never re-judges anything; it measures what the run itself recorded,
against ground truth you supply.

## Install

Nothing to install. Clone and run with any Python 3.9+:

```bash
git clone https://github.com/ranadhir19/podiumproof.git
cd podiumproof
python3 -m podiumproof --help
```

(Or `pip install .` if you want the `podiumproof` command.)

## Use

The first target format is the serialized state of the
[Arena skill](https://github.com/Jakeschincariol/arena-skill) — a run
directory holding `arena.json`, per-round verdict files, and solution
files. Supply ground truth as an oracle file (a template ships with
every fixture; see *The oracle* below), or score checkable tasks
directly from an answer key:

```bash
# with an oracle file (defaults to <run_dir>/oracle.json when present)
python3 -m podiumproof audit path/to/.arena/run-7

# with just an answer key: final answers are extracted from the
# candidates' own solution files and scored against it
python3 -m podiumproof audit path/to/.arena/run-7 --correct-answer 8
```

Output: `report.md` (the one-page audit) and `ledger.json` (the same
verdicts, machine-readable) in `<run_dir>/audit/`, plus a summary on
stdout. Without any ground truth the audit still runs — and stamps
everything UNVERIFIABLE, which is itself the finding: an unauditable
win proves nothing.

## The four checks

1. **Winner vs oracle.** Every candidate in the spawn pool is scored
   against ground truth. The audit reports the champion's rank in its
   own pool, the regret (best score minus champion's score), and the
   pool's headroom — best minus first sample — which is the most any
   selector could possibly have earned. If headroom ≈ 0, the stamp is
   NO HEADROOM and nothing else matters: selection cannot create
   quality the pool does not contain.
2. **Champion stability.** The recorded pool is replayed through 200
   re-seeded brackets, each match judged by a judge model *fitted to
   this run's own recorded matches*. How often does the recorded
   champion win again? A title that reproduces 5% of the time is a
   seeding artefact, not a result. (Model-based estimate, labelled as
   such — a true replay would need the judge itself.)
3. **Judge validity, in situ.** From the run's own decisive matches:
   the judge's accuracy against the oracle with a Wilson interval; a
   two-parameter logistic fit giving **position bias** (alpha: the
   log-odds head start the side read first enjoys) and **gap
   sensitivity** (beta: whether verdicts track quality at all); an
   estimated **swap consistency** (would the same matches, judged in
   the opposite order, crown the same winners?); and a **planted-flaw
   canary** — declare a candidate carrying a known fatal defect and
   the audit tracks how far the bracket let it travel and whether the
   judge ever flagged it.
4. **Cost ledger.** The run's sub-agent calls, counted from its own
   state, weighed against the honest baselines on the same pool:
   first sample, random pick (expected score), majority vote over the
   candidates' final answers, and — for scale — best-of-N by
   execution, the oracle ceiling. The tournament premium is printed
   as signed numbers, not adjectives.

## See it catch a bad tournament

Two synthetic tournaments with known ground truth ship in `examples/`
(regenerate them any time with `make-fixture`). The **flawed** one
plants a pool with real headroom and a bad judge: the best candidate
is eliminated in round 1, a candidate with a planted fatal arithmetic
flaw reaches the final unflagged, and a mediocre candidate takes the
title.

```bash
python3 -m podiumproof make-fixture /tmp/flawed --scenario flawed
python3 -m podiumproof audit /tmp/flawed
```

```
champion: a012
  C1a  REFUTED   The champion is the best candidate in its own pool.
  C1b  SUPPORTED The pool held headroom worth selecting over...
  C2   REFUTED   The champion is the stable outcome of this bracket...
  C3a  REFUTED   The judge picked the better candidate more often than chance.
  C3b  REFUTED   The judge's verdicts are free of material position bias...
  C3c  REFUTED   A candidate carrying a known fatal flaw is stopped well before the final.
  C4   REFUTED   The champion beat the honest baselines the spend had to justify...
stamp: JUDGE ARTEFACT
```

The measurements behind the stamps: champion ranks **7th of 16** in
its own pool (regret 0.66); judge accuracy **0.467** on decisive
matches; position bias alpha = **+1.00** with gap sensitivity beta ≈
**−0.09** (verdicts essentially unrelated to quality); estimated swap
consistency **0.39**; the champion reproduces in **5.5%** of re-seeded
replays, which produce 16 distinct champions; and the champion's score
sits *below* a random pick's expectation — after 91 sub-agent calls.

The **sound** fixture is the same shape with a competent judge, and
the audit clears it on every claim: accuracy 1.0, swap consistency
0.95, champion reproduction 99.5%, stamp **PREMIUM REAL**. The harness
is not a machine for saying no; it is a machine for telling the
difference.

## The oracle

```json
{
  "task": "free text",
  "correct_answer": "8",
  "scores":  {"a001": 0.30, "a002": 0.25},
  "answers": {"a001": "42", "a002": "42"},
  "fatal_flaw": ["a007"],
  "baseline_score": 0.0
}
```

- `scores` — ground-truth quality in [0, 1] for each spawn candidate
  (a test-pass fraction, a graded rubric you trust, an execution
  result). This is the input that makes the strong checks possible.
- `answers` + `correct_answer` — if `scores` is absent, binary scores
  are derived from the answers; answers are also what majority vote
  votes over. Missing answers are extracted from the candidates'
  solution files (`ANSWER: x` or `#### x` markers).
- `fatal_flaw` — agent ids of planted canaries (candidates carrying a
  known fatal defect), for check C3c.
- `baseline_score` — the oracle score of a rejected baseline answer,
  when the run started from one.

## Honesty notes

- Swap consistency and champion stability are **model-based
  estimates**: the judge model is fitted to the run's own recorded
  matches, and its parameters are printed in the ledger. A true
  swapped re-judgement requires the judge; podiumproof makes no model
  calls, so it says UNVERIFIABLE rather than pretend otherwise when a
  fit is impossible (too few decisive matches, binary-only ground
  truth).
- Candidates in the target format *revise* between rounds, so pool
  ranks are computed on the spawn pool, like-for-like; the champion's
  revised final answer is scored separately whenever a key exists.
- Verdict thresholds (Wilson interval entirely above 0.5 for judge
  accuracy; 0.02 noise band on scores; 50% reproduction for stability)
  are constants in `podiumproof/checks.py`, named and commented.

## Why this exists

The selectors with *measured* premiums on checkable tasks are the
boring ones — majority vote and ground-truth-trained verifiers. The
bracket-with-LLM-judge format has spread widely (the reference skill
passed 1,500 GitHub stars in eight weeks) with no published
winner-quality evaluation anywhere: not by its author, not by anyone.
JudgeBench puts prompted frontier judges at 51–64% on ground-truth
pairs; tournament theory has known for decades that single elimination
compounds per-match error multiplicatively; and at least one careful
study of selection found the *oracle* gain — perfect selection, zero
judge error — to be ≈ 0 in its setting. The gap in the landscape is
not a better tournament. It is the audit. That is what this is.

## Development

```bash
python3 validate.py   # files, stdlib-only scan, full test suite, end-to-end fixture audits
```

## License

MIT. See `LICENSE`. The name-collision record is in `NAME_CHECK.md`;
the IP/legal compliance record is in `COMPLIANCE.md`.

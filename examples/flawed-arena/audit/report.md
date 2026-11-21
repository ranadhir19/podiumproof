# Tournament audit — podiumproof

**Summary stamp: JUDGE ARTEFACT.** The pool held a better answer and the judging process is why it did not win. The crown is an artefact of the referee, not of the pool.

Run: 16 agents, 4 rounds, 15 matches, champion **a012**, 91 sub-agent calls.
Ground truth: oracle file oracle.json.

## The claims

| # | Claim | Verdict | Key evidence |
|---|-------|---------|--------------|
| C1a | The champion is the best candidate in its own pool. | **REFUTED** | rank 7 of 16, regret 0.660 |
| C1b | The pool held headroom worth selecting over: its best candidate beats its first sample by more than noise. | **SUPPORTED** | headroom 0.700 |
| C2 | The champion is the stable outcome of this bracket, not a seeding artefact. | **REFUTED** | champion reproduces in 0.055 of replays |
| C3a | The judge picked the better candidate more often than chance. | **REFUTED** | accuracy 0.467 on 15 decisive matches |
| C3b | The judge's verdicts are free of material position bias (presentation order does not decide matches). | **REFUTED** | position bias alpha 1.002, swap consistency ~0.393 |
| C3c | A candidate carrying a known fatal flaw is stopped well before the final. | **REFUTED** | a007: reached the final round |
| C4 | The champion beat the honest baselines the spend had to justify (first sample, random pick, majority vote). | **REFUTED** | premiums: first_sample 0.040, random_pick_expected -0.026, majority_vote 0.073 |

## Check 1 — winner vs oracle

The champion's spawn candidate ranks **7 of 16** in its own pool (oracle score 0.340; the pool's best was 1.000; regret 0.660). Its revised final answer scores 0.000 against the key.
Pool headroom (best minus first sample, a001): **0.700**. That is the most any selector could have earned here.

## Check 2 — champion stability

Replaying the pool through 200 re-seeded brackets (judge model fitted to this run's own matches), the recorded champion wins again **0.055** of the time; the oracle's best candidate wins 0.055; the modal replay champion is a009 (0.115); 16 distinct champions appear.

This is a model-based estimate, not a re-run of the real judge — podiumproof makes no model calls.

## Check 3 — the judge, in situ

On the 15 matches where the oracle separates the candidates, the judge picked the better one **0.467** of the time (95% Wilson interval 0.248–0.699; chance is 0.5). Fitted judge model: position bias alpha = 1.002 (the side read first gets a 1.002 log-odds head start), gap sensitivity beta = -0.085. First-listed candidates won 0.733 of all matches. Estimated swap consistency: 0.393 — the share of decisive matches expected to crown the same winner if judged again in the opposite presentation order (model estimate; a true swapped re-judgement requires the judge itself).

Planted-flaw canary: a007 reached the final round. Matches where the judge flagged the flaw: {'a007': 0}.

## Check 4 — cost ledger

Sub-agent calls: 16 spawn + 15 matches x 5 = **91 total**.

| Baseline (same pool) | Oracle score | Champion's premium |
|---|---|---|
| First sample (1 call) | 0.300 | 0.040 |
| Random pick, expected (1 call) | 0.366 | -0.026 |
| Majority vote over answers | 0.267 | 0.073 |
| Best-of-N by execution (oracle ceiling) | 1.000 | — |

Majority vote is computed over the candidates' extracted final answers. Best-of-N by execution is the oracle ceiling — what checking every candidate directly would have found — printed for scale, not as a baseline the tournament had to beat.

## Notes

- (C1a) Ranked on spawn-pool oracle scores, like-for-like. The champion's revised final answer is scored separately when a key exists.
- (C2) Model-based replay: brackets re-seeded 200 times, matches judged by the judge model fitted to this run's own recorded matches. Not a re-run of the real judge.
- (C3a) Decisive = the oracle separates the two candidates. SUPPORTED needs the whole 95% Wilson interval above 0.5; a point estimate at or below 0.5 is REFUTED; between them the run is too small to tell.
- (C3b) A true swapped re-judgement needs the judge itself; offline, swap consistency is estimated from the fitted judge model and labelled as an estimate.
- (C4) Best-of-N by execution (the oracle ceiling) is printed for scale; it is not a baseline the tournament had to beat, it is what checking every candidate directly would have found.
- Verdicts use a noise band of 0.02 on oracle scores; differences at or below it are not evidence.

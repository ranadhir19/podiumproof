# Tournament audit — podiumproof

**Summary stamp: PREMIUM REAL.** The champion is (near) the best its pool held and beat every cheap baseline by more than noise. The spend bought something real.

Run: 8 agents, 3 rounds, 7 matches, champion **a005**, 43 sub-agent calls.
Ground truth: oracle file oracle.json.

## The claims

| # | Claim | Verdict | Key evidence |
|---|-------|---------|--------------|
| C1a | The champion is the best candidate in its own pool. | **SUPPORTED** | rank 1 of 8, regret 0.000 |
| C1b | The pool held headroom worth selecting over: its best candidate beats its first sample by more than noise. | **SUPPORTED** | headroom 0.750 |
| C2 | The champion is the stable outcome of this bracket, not a seeding artefact. | **SUPPORTED** | champion reproduces in 0.995 of replays |
| C3a | The judge picked the better candidate more often than chance. | **SUPPORTED** | accuracy 1.000 on 7 decisive matches |
| C3b | The judge's verdicts are free of material position bias (presentation order does not decide matches). | **SUPPORTED** | position bias alpha 0.335, swap consistency ~0.949 |
| C3c | A candidate carrying a known fatal flaw is stopped well before the final. | **SUPPORTED** | a006: eliminated in round 1 |
| C4 | The champion beat the honest baselines the spend had to justify (first sample, random pick, majority vote). | **SUPPORTED** | premiums: first_sample 0.750, random_pick_expected 0.509, majority_vote 0.217 |

## Check 1 — winner vs oracle

The champion's spawn candidate ranks **1 of 8** in its own pool (oracle score 1.000; the pool's best was 1.000; regret 0.000). Its revised final answer scores 1.000 against the key.
Pool headroom (best minus first sample, a001): **0.750**. That is the most any selector could have earned here.

## Check 2 — champion stability

Replaying the pool through 200 re-seeded brackets (judge model fitted to this run's own matches), the recorded champion wins again **0.995** of the time; the oracle's best candidate wins 0.995; the modal replay champion is a005 (0.995); 2 distinct champions appear.

This is a model-based estimate, not a re-run of the real judge — podiumproof makes no model calls.

## Check 3 — the judge, in situ

On the 7 matches where the oracle separates the candidates, the judge picked the better one **1.000** of the time (95% Wilson interval 0.646–1.000; chance is 0.5). Fitted judge model: position bias alpha = 0.335 (the side read first gets a 0.335 log-odds head start), gap sensitivity beta = 22.311. First-listed candidates won 0.571 of all matches. Estimated swap consistency: 0.949 — the share of decisive matches expected to crown the same winner if judged again in the opposite presentation order (model estimate; a true swapped re-judgement requires the judge itself).

Planted-flaw canary: a006 eliminated in round 1. Matches where the judge flagged the flaw: {'a006': 1}.

## Check 4 — cost ledger

Sub-agent calls: 8 spawn + 7 matches x 5 = **43 total**.

| Baseline (same pool) | Oracle score | Champion's premium |
|---|---|---|
| First sample (1 call) | 0.250 | 0.750 |
| Random pick, expected (1 call) | 0.491 | 0.509 |
| Majority vote over answers | 0.783 | 0.217 |
| Best-of-N by execution (oracle ceiling) | 1.000 | — |

Majority vote is computed over the candidates' extracted final answers. Best-of-N by execution is the oracle ceiling — what checking every candidate directly would have found — printed for scale, not as a baseline the tournament had to beat.

## Notes

- (C1a) Ranked on spawn-pool oracle scores, like-for-like. The champion's revised final answer is scored separately when a key exists.
- (C2) Model-based replay: brackets re-seeded 200 times, matches judged by the judge model fitted to this run's own recorded matches. Not a re-run of the real judge.
- (C3a) Decisive = the oracle separates the two candidates. SUPPORTED needs the whole 95% Wilson interval above 0.5; a point estimate at or below 0.5 is REFUTED; between them the run is too small to tell.
- (C3b) A true swapped re-judgement needs the judge itself; offline, swap consistency is estimated from the fitted judge model and labelled as an estimate.
- (C4) Best-of-N by execution (the oracle ceiling) is printed for scale; it is not a baseline the tournament had to beat, it is what checking every candidate directly would have found.
- Verdicts use a noise band of 0.02 on oracle scores; differences at or below it are not evidence.

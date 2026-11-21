"""The four audit checks, and the claims they stamp.

Every tournament implicitly makes claims. podiumproof writes them down
and stamps each one SUPPORTED, REFUTED or UNVERIFIABLE, with the
measurement attached:

  C1a  the champion is the best candidate in its own pool
  C1b  the pool held headroom worth selecting over
  C1c  the champion beat the rejected baseline answer (when one exists)
  C2   the champion is the stable outcome of the bracket, not a seeding
       artefact
  C3a  the judge picked the better candidate more often than chance
  C3b  the judge's verdicts are free of material position bias
  C3c  a candidate carrying a known fatal flaw is stopped well before
       the final
  C4   the champion beat the honest baselines the spend had to justify

The four numbers roll up into one summary stamp:

  PREMIUM REAL    the champion is (near) the pool's best and beat every
                  cheap baseline by more than noise
  WITHIN NOISE    something was gained, but not separably from what a
                  cheaper selector or a luckier draw would have given
  JUDGE ARTEFACT  the pool had a better answer and the judging process
                  is why it did not win
  NO HEADROOM     the pool's best was barely better than its first
                  sample; no selector could have earned the spend
"""

from . import judgemodel, replay as replay_mod
from .oracle import champion_final_score, normalize_answer

EPS = 0.02            # score differences at or below this are noise
STABLE = 0.50         # champion reproduction rate needed to call a title stable
SWAP_GOOD = 0.90      # estimated swap consistency at/above: order does not matter
SWAP_BAD = 0.80       # at/below: order decides matches


def _claim(cid, check, text, verdict, evidence, note=None):
    return {"id": cid, "check": check, "claim": text, "verdict": verdict,
            "evidence": evidence, "note": note}


def _rank(scores, aid):
    """Competition rank (1 = best); ties share the better rank."""
    s = scores[aid]
    return 1 + sum(1 for v in scores.values() if v > s)


def run_checks(run, oracle, replays=200, replay_seed=20261120):
    claims = []
    calls = run.count_calls()
    fit = judgemodel.fit_judge(run.matches, oracle)
    rep = None
    champ = run.champion
    scores = oracle.scores

    pool_scores = {a: scores[a] for a in run.agents if a in scores}
    first_id = run.agents[0] if run.agents else None

    # ---------------- Check 1: winner vs oracle -----------------------
    headroom = None
    regret = None
    champ_rank = None
    if champ and pool_scores.get(champ) is not None and len(pool_scores) >= 2:
        best = max(pool_scores.values())
        champ_score = pool_scores[champ]
        regret = best - champ_score
        champ_rank = _rank(pool_scores, champ)
        verdict = "SUPPORTED" if regret <= EPS else "REFUTED"
        claims.append(_claim(
            "C1a", "winner-vs-oracle",
            "The champion is the best candidate in its own pool.",
            verdict,
            {"champion": champ, "champion_spawn_score": champ_score,
             "champion_pool_rank": champ_rank, "pool_size": len(pool_scores),
             "oracle_best_score": best, "regret": round(regret, 4),
             "champion_final_answer_score": champion_final_score(run, oracle)},
            "Ranked on spawn-pool oracle scores, like-for-like. The "
            "champion's revised final answer is scored separately when a "
            "key exists."))
        if first_id in pool_scores:
            headroom = best - pool_scores[first_id]
            verdict = "SUPPORTED" if headroom > EPS else "REFUTED"
            claims.append(_claim(
                "C1b", "winner-vs-oracle",
                "The pool held headroom worth selecting over: its best "
                "candidate beats its first sample by more than noise.",
                verdict,
                {"oracle_best_score": best,
                 "first_sample": first_id,
                 "first_sample_score": pool_scores[first_id],
                 "headroom": round(headroom, 4)}))
    else:
        claims.append(_claim(
            "C1a", "winner-vs-oracle",
            "The champion is the best candidate in its own pool.",
            "UNVERIFIABLE",
            {"champion": champ},
            "No oracle scores for the pool (supply --oracle or "
            "--correct-answer). The tournament's central claim cannot be "
            "checked without ground truth, which is itself the finding."))
        claims.append(_claim(
            "C1b", "winner-vs-oracle",
            "The pool held headroom worth selecting over: its best "
            "candidate beats its first sample by more than noise.",
            "UNVERIFIABLE", {}, "No oracle scores for the pool."))

    # C1c: the final check against a rejected baseline, when it exists
    fin = run.final
    if fin and fin.get("result"):
        if oracle.baseline_score is not None and champ:
            final_score = champion_final_score(run, oracle)
            if final_score is not None:
                verdict = ("SUPPORTED" if final_score > oracle.baseline_score
                           else "REFUTED")
                claims.append(_claim(
                    "C1c", "winner-vs-oracle",
                    "The champion beat the rejected baseline answer.",
                    verdict,
                    {"champion_final_answer_score": final_score,
                     "baseline_score": oracle.baseline_score,
                     "run_final_check_said": fin["result"].get("better")}))
            else:
                claims.append(_claim(
                    "C1c", "winner-vs-oracle",
                    "The champion beat the rejected baseline answer.",
                    "UNVERIFIABLE", {},
                    "Baseline score known but the champion's final answer "
                    "could not be scored."))
        else:
            claims.append(_claim(
                "C1c", "winner-vs-oracle",
                "The champion beat the rejected baseline answer.",
                "UNVERIFIABLE",
                {"run_final_check_said": fin["result"].get("better")},
                "The run's own final check is the only evidence; no "
                "oracle score for the baseline was supplied."))

    # ---------------- Check 2: champion stability ---------------------
    if fit.ok and champ and len(pool_scores) >= 2:
        rep = replay_mod.replay_brackets(pool_scores, fit, champ,
                                         k=replays, seed=replay_seed)
        rate = rep["champion_reproduction_rate"]
        verdict = "SUPPORTED" if rate >= STABLE else "REFUTED"
        claims.append(_claim(
            "C2", "champion-stability",
            "The champion is the stable outcome of this bracket, not a "
            "seeding artefact.",
            verdict,
            {"champion_reproduction_rate": round(rate, 4),
             "oracle_best_win_rate": round(rep["oracle_best_win_rate"], 4),
             "modal_champion": rep["modal_champion"],
             "modal_rate": round(rep["modal_rate"], 4),
             "distinct_champions_in_replays": rep["distinct_champions"],
             "replays": rep["replays"]},
            "Model-based replay: brackets re-seeded %d times, matches "
            "judged by the judge model fitted to this run's own recorded "
            "matches. Not a re-run of the real judge." % rep["replays"]))
    else:
        claims.append(_claim(
            "C2", "champion-stability",
            "The champion is the stable outcome of this bracket, not a "
            "seeding artefact.",
            "UNVERIFIABLE", {},
            fit.reason or "No oracle scores for the pool."))

    # ---------------- Check 3: judge in situ --------------------------
    if fit.ok:
        lo, hi = fit.accuracy_ci
        if lo > 0.5:
            verdict = "SUPPORTED"
        elif fit.accuracy <= 0.5:
            verdict = "REFUTED"
        else:
            verdict = "UNVERIFIABLE"
        claims.append(_claim(
            "C3a", "judge-validity",
            "The judge picked the better candidate more often than "
            "chance.",
            verdict,
            {"judge_accuracy_on_decisive_matches": round(fit.accuracy, 4),
             "wilson_95_ci": [round(lo, 4), round(hi, 4)],
             "decisive_matches": fit.n_decisive},
            "Decisive = the oracle separates the two candidates. "
            "SUPPORTED needs the whole 95% Wilson interval above 0.5; a "
            "point estimate at or below 0.5 is REFUTED; between them the "
            "run is too small to tell."))
        # position bias: alpha with its standard error, plus the swap estimate
        z = None
        if fit.se_alpha:
            z = fit.alpha / fit.se_alpha
        biased = (z is not None and abs(z) > judgemodel.Z95 and fit.alpha > 0.25)
        if fit.swap_consistency is not None and fit.swap_consistency <= SWAP_BAD:
            verdict = "REFUTED"
        elif biased:
            verdict = "REFUTED"
        elif fit.swap_consistency is not None and fit.swap_consistency >= SWAP_GOOD \
                and not (z is not None and abs(z) > judgemodel.Z95):
            verdict = "SUPPORTED"
        else:
            verdict = "UNVERIFIABLE"
        claims.append(_claim(
            "C3b", "judge-validity",
            "The judge's verdicts are free of material position bias "
            "(presentation order does not decide matches).",
            verdict,
            {"position_bias_alpha": round(fit.alpha, 4),
             "alpha_standard_error": (round(fit.se_alpha, 4)
                                      if fit.se_alpha else None),
             "alpha_z": (round(z, 3) if z is not None else None),
             "first_listed_win_rate": (round(fit.first_win_rate, 4)
                                       if fit.first_win_rate is not None else None),
             "estimated_swap_consistency": (round(fit.swap_consistency, 4)
                                            if fit.swap_consistency is not None
                                            else None),
             "gap_sensitivity_beta": round(fit.beta, 4)},
            "A true swapped re-judgement needs the judge itself; offline, "
            "swap consistency is estimated from the fitted judge model and "
            "labelled as an estimate."))
    else:
        for cid, text in (("C3a", "The judge picked the better candidate "
                                  "more often than chance."),
                          ("C3b", "The judge's verdicts are free of "
                                  "material position bias (presentation "
                                  "order does not decide matches).")):
            claims.append(_claim(cid, "judge-validity", text, "UNVERIFIABLE",
                                 {}, fit.reason or "No judge model could be "
                                 "fitted."))

    # C3c: the planted-flaw canary
    if oracle.fatal_flaws:
        by_id = {a: (run.state.get("agents") or {}).get(a) or {}
                 for a in oracle.fatal_flaws}
        fates = {}
        worst = "SUPPORTED"
        final_round = run.rounds_count
        for aid, agent in by_id.items():
            if aid == champ:
                fate, bad = "champion", True
            elif agent.get("eliminated_in") is None:
                fate, bad = "never eliminated", True
            elif agent.get("eliminated_in") >= final_round:
                fate, bad = "reached the final round", True
            elif agent.get("eliminated_in") <= max(1, final_round // 2):
                fate, bad = "eliminated in round %d" % agent["eliminated_in"], False
            else:
                fate, bad = ("eliminated in round %d of %d"
                             % (agent["eliminated_in"], final_round)), True
            fates[aid] = fate
            if bad:
                worst = "REFUTED"
        # corroboration: did the judge ever flag the flaw in a verdict file?
        flagged = {}
        for aid in oracle.fatal_flaws:
            flags = 0
            for m in run.matches:
                if aid in (m.a, m.b):
                    ff = m.fatal_flags()
                    if ff.get(aid):
                        flags += 1
            flagged[aid] = flags
        claims.append(_claim(
            "C3c", "judge-validity",
            "A candidate carrying a known fatal flaw is stopped well "
            "before the final.",
            worst,
            {"canary_fates": fates,
             "matches_where_judge_flagged_the_flaw": flagged,
             "total_rounds": final_round}))
    else:
        claims.append(_claim(
            "C3c", "judge-validity",
            "A candidate carrying a known fatal flaw is stopped well "
            "before the final.",
            "UNVERIFIABLE", {},
            "No canary was planted or declared (oracle fatal_flaw list "
            "is empty). Plant one candidate with a known fatal defect "
            "and declare it; the audit will track how far it gets."))

    # ---------------- Check 4: cost ledger ----------------------------
    ledger = {"calls": calls, "baselines": {}, "premiums": {}}
    if champ and pool_scores.get(champ) is not None:
        champ_score = pool_scores[champ]
        vals = list(pool_scores.values())
        baselines = {}
        baselines["first_sample"] = pool_scores.get(first_id)
        baselines["random_pick_expected"] = sum(vals) / float(len(vals))
        # majority vote over answers, when answers exist for the pool
        modal_score = None
        if oracle.answers and oracle.correct_answer is not None:
            from collections import Counter
            votes = Counter()
            members = {}
            for aid in run.agents:
                if aid in oracle.answers and aid in pool_scores:
                    key = normalize_answer(oracle.answers[aid])
                    votes[key] += 1
                    members.setdefault(key, []).append(aid)
            if votes:
                top = max(votes.values())
                modes = [k for k, v in votes.items() if v == top]
                # plurality tie: the mode whose earliest member comes first
                modes.sort(key=lambda k: min(run.agents.index(a)
                                             for a in members[k]))
                chosen = modes[0]
                modal_score = (sum(pool_scores[a] for a in members[chosen])
                               / float(len(members[chosen])))
                ledger["majority_modal_answer"] = chosen
                ledger["majority_votes"] = dict(votes)
        baselines["majority_vote"] = modal_score
        baselines["best_of_n_by_execution"] = max(vals)
        ledger["baselines"] = {k: (round(v, 4) if v is not None else None)
                               for k, v in baselines.items()}
        ledger["premiums"] = {
            k: (round(champ_score - v, 4) if v is not None else None)
            for k, v in baselines.items() if k != "best_of_n_by_execution"}
        computable = [v for k, v in baselines.items()
                      if k != "best_of_n_by_execution" and v is not None]
        if computable:
            verdict = ("SUPPORTED" if all(champ_score - v > EPS
                                          for v in computable)
                       else "REFUTED")
            claims.append(_claim(
                "C4", "cost-ledger",
                "The champion beat the honest baselines the spend had "
                "to justify (first sample, random pick, majority vote).",
                verdict,
                {"champion_spawn_score": champ_score,
                 "baselines": ledger["baselines"],
                 "premiums": ledger["premiums"],
                 "total_sub_agent_calls": calls["total"]},
                "Best-of-N by execution (the oracle ceiling) is printed "
                "for scale; it is not a baseline the tournament had to "
                "beat, it is what checking every candidate directly "
                "would have found."))
        else:
            claims.append(_claim(
                "C4", "cost-ledger",
                "The champion beat the honest baselines the spend had "
                "to justify (first sample, random pick, majority vote).",
                "UNVERIFIABLE", {"total_sub_agent_calls": calls["total"]},
                "No computable baseline without pool scores."))
    else:
        claims.append(_claim(
            "C4", "cost-ledger",
            "The champion beat the honest baselines the spend had "
            "to justify (first sample, random pick, majority vote).",
            "UNVERIFIABLE", {"total_sub_agent_calls": calls["total"]},
            "No oracle scores for the pool; the spend is counted but "
            "cannot be weighed."))

    stamp = _stamp(headroom, regret, fit, rep, claims, ledger)
    return {"claims": claims, "stamp": stamp, "calls": calls,
            "fit": fit, "replay": rep, "cost_ledger": ledger,
            "headroom": headroom, "regret": regret,
            "champion_rank": champ_rank}


def _stamp(headroom, regret, fit, rep, claims, ledger):
    if headroom is not None and headroom <= EPS:
        return "NO HEADROOM"
    if regret is not None and regret > EPS:
        judge_bad = (fit.ok and fit.accuracy is not None
                     and fit.accuracy <= 0.55)
        unstable = (rep is not None
                    and rep["champion_reproduction_rate"] < STABLE)
        if judge_bad or unstable:
            return "JUDGE ARTEFACT"
    c4 = next((c for c in claims if c["id"] == "C4"), None)
    if (regret is not None and regret <= EPS and c4 is not None
            and c4["verdict"] == "SUPPORTED"):
        return "PREMIUM REAL"
    if headroom is None:
        return "UNVERIFIABLE"
    return "WITHIN NOISE"

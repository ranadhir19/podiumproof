"""Render an audit as report.md (for humans) and ledger.json (for tools)."""

import json
import os

from . import __version__

STAMP_BLURB = {
    "PREMIUM REAL": "The champion is (near) the best its pool held and "
                    "beat every cheap baseline by more than noise. The "
                    "spend bought something real.",
    "WITHIN NOISE": "Something may have been gained, but this audit "
                    "cannot separate it from what a cheaper selector or "
                    "a luckier draw would have produced.",
    "JUDGE ARTEFACT": "The pool held a better answer and the judging "
                      "process is why it did not win. The crown is an "
                      "artefact of the referee, not of the pool.",
    "NO HEADROOM": "The pool's best candidate was barely better than "
                   "its first sample. No selector could have earned "
                   "this spend; the tournament answered a question the "
                   "pool did not pose.",
    "UNVERIFIABLE": "Ground truth was not supplied, so the tournament's "
                    "claims cannot be stamped either way. An "
                    "unauditable win is the finding.",
}


def build_ledger(run, oracle, result):
    fit = result["fit"]
    return {
        "tool": "podiumproof",
        "version": __version__,
        "run": {
            "dir": run.run_dir,
            "agents": run.agents_n,
            "rounds": run.rounds_count,
            "matches": len([m for m in run.matches if m.played]),
            "champion": run.champion,
            "seed": run.seed,
        },
        "oracle_sources": oracle.sources,
        "stamp": result["stamp"],
        "claims": result["claims"],
        "judge_model": {
            "fitted": fit.ok,
            "reason": fit.reason,
            "alpha_position_bias": fit.alpha if fit.ok else None,
            "beta_gap_sensitivity": fit.beta if fit.ok else None,
            "accuracy": fit.accuracy,
            "accuracy_ci": fit.accuracy_ci,
            "decisive_matches": fit.n_decisive,
            "first_listed_win_rate": fit.first_win_rate,
            "estimated_swap_consistency": fit.swap_consistency,
        },
        "replay": result["replay"],
        "cost_ledger": result["cost_ledger"],
    }


def _fmt(v, digits=3):
    if v is None:
        return "—"
    if isinstance(v, float):
        return "%.*f" % (digits, v)
    return str(v)


def render_markdown(run, oracle, result, ledger):
    claims = {c["id"]: c for c in result["claims"]}
    fit = result["fit"]
    calls = result["calls"]
    lines = []
    lines.append("# Tournament audit — podiumproof")
    lines.append("")
    lines.append("**Summary stamp: %s.** %s"
                 % (result["stamp"], STAMP_BLURB[result["stamp"]]))
    lines.append("")
    lines.append("Run: %d agents, %d rounds, %d matches, champion **%s**, "
                 "%d sub-agent calls."
                 % (run.agents_n, run.rounds_count,
                    len([m for m in run.matches if m.played]),
                    run.champion, calls["total"]))
    if oracle.sources:
        lines.append("Ground truth: %s." % "; ".join(oracle.sources))
    else:
        lines.append("Ground truth: **none supplied** — every claim that "
                     "needs it is UNVERIFIABLE below.")
    lines.append("")
    lines.append("## The claims")
    lines.append("")
    lines.append("| # | Claim | Verdict | Key evidence |")
    lines.append("|---|-------|---------|--------------|")
    for c in result["claims"]:
        ev = c["evidence"]
        key = ""
        if c["id"] == "C1a":
            key = "rank %s of %s, regret %s" % (
                _fmt(ev.get("champion_pool_rank"), 0),
                _fmt(ev.get("pool_size"), 0), _fmt(ev.get("regret")))
        elif c["id"] == "C1b":
            key = "headroom %s" % _fmt(ev.get("headroom"))
        elif c["id"] == "C2":
            key = "champion reproduces in %s of replays" % _fmt(
                ev.get("champion_reproduction_rate"))
        elif c["id"] == "C3a":
            key = "accuracy %s on %s decisive matches" % (
                _fmt(ev.get("judge_accuracy_on_decisive_matches")),
                _fmt(ev.get("decisive_matches"), 0))
        elif c["id"] == "C3b":
            key = "position bias alpha %s, swap consistency ~%s" % (
                _fmt(ev.get("position_bias_alpha")),
                _fmt(ev.get("estimated_swap_consistency")))
        elif c["id"] == "C3c":
            key = "; ".join("%s: %s" % kv for kv in
                            (ev.get("canary_fates") or {}).items())
        elif c["id"] == "C4":
            key = "premiums: %s" % ", ".join(
                "%s %s" % (k, _fmt(v)) for k, v in
                (ev.get("premiums") or {}).items())
        lines.append("| %s | %s | **%s** | %s |"
                     % (c["id"], c["claim"], c["verdict"], key))
    lines.append("")
    lines.append("## Check 1 — winner vs oracle")
    lines.append("")
    c = claims.get("C1a", {})
    ev = c.get("evidence", {})
    if ev.get("champion_pool_rank") is not None:
        lines.append("The champion's spawn candidate ranks **%s of %s** in "
                     "its own pool (oracle score %s; the pool's best was "
                     "%s; regret %s). Its revised final answer scores %s "
                     "against the key."
                     % (ev["champion_pool_rank"], ev["pool_size"],
                        _fmt(ev.get("champion_spawn_score")),
                        _fmt(ev.get("oracle_best_score")),
                        _fmt(ev.get("regret")),
                        _fmt(ev.get("champion_final_answer_score"))))
    else:
        lines.append("Not checkable: no oracle scores for the pool.")
    c = claims.get("C1b", {})
    ev = c.get("evidence", {})
    if ev.get("headroom") is not None:
        lines.append("Pool headroom (best minus first sample, %s): **%s**. "
                     "That is the most any selector could have earned here."
                     % (ev.get("first_sample"), _fmt(ev.get("headroom"))))
    lines.append("")
    lines.append("## Check 2 — champion stability")
    lines.append("")
    rep = result["replay"]
    if rep:
        lines.append("Replaying the pool through %d re-seeded brackets "
                     "(judge model fitted to this run's own matches), the "
                     "recorded champion wins again **%s** of the time; the "
                     "oracle's best candidate wins %s; the modal replay "
                     "champion is %s (%s); %d distinct champions appear."
                     % (rep["replays"],
                        _fmt(rep["champion_reproduction_rate"]),
                        _fmt(rep["oracle_best_win_rate"]),
                        rep["modal_champion"], _fmt(rep["modal_rate"]),
                        rep["distinct_champions"]))
        lines.append("")
        lines.append("This is a model-based estimate, not a re-run of the "
                     "real judge — podiumproof makes no model calls.")
    else:
        lines.append("Not checkable: %s"
                     % (claims.get("C2", {}).get("note") or "no judge model."))
    lines.append("")
    lines.append("## Check 3 — the judge, in situ")
    lines.append("")
    if fit.ok:
        lo, hi = fit.accuracy_ci
        lines.append("On the %d matches where the oracle separates the "
                     "candidates, the judge picked the better one **%s** "
                     "of the time (95%% Wilson interval %s–%s; chance is "
                     "0.5). Fitted judge model: position bias alpha = %s "
                     "(the side read first gets a %s log-odds head start), "
                     "gap sensitivity beta = %s. First-listed candidates "
                     "won %s of all matches. Estimated swap consistency: "
                     "%s — the share of decisive matches expected to crown "
                     "the same winner if judged again in the opposite "
                     "presentation order (model estimate; a true swapped "
                     "re-judgement requires the judge itself)."
                     % (fit.n_decisive, _fmt(fit.accuracy), _fmt(lo),
                        _fmt(hi), _fmt(fit.alpha), _fmt(fit.alpha),
                        _fmt(fit.beta), _fmt(fit.first_win_rate),
                        _fmt(fit.swap_consistency)))
    else:
        lines.append("Not checkable: %s" % (fit.reason or "no fit."))
    c = claims.get("C3c", {})
    ev = c.get("evidence", {})
    if ev.get("canary_fates"):
        lines.append("")
        lines.append("Planted-flaw canary: %s. Matches where the judge "
                     "flagged the flaw: %s."
                     % ("; ".join("%s %s" % kv for kv in
                                  ev["canary_fates"].items()),
                        ev.get("matches_where_judge_flagged_the_flaw")))
    lines.append("")
    lines.append("## Check 4 — cost ledger")
    lines.append("")
    lines.append("Sub-agent calls: %d spawn + %d matches x %d = **%d "
                 "total**." % (calls["spawn"], calls["matches"],
                               calls["per_match"], calls["total"]))
    lines.append("")
    baselines = result["cost_ledger"].get("baselines") or {}
    premiums = result["cost_ledger"].get("premiums") or {}
    if baselines:
        lines.append("| Baseline (same pool) | Oracle score | Champion's premium |")
        lines.append("|---|---|---|")
        label = {"first_sample": "First sample (1 call)",
                 "random_pick_expected": "Random pick, expected (1 call)",
                 "majority_vote": "Majority vote over answers",
                 "best_of_n_by_execution": "Best-of-N by execution (oracle ceiling)"}
        for k in ("first_sample", "random_pick_expected", "majority_vote",
                  "best_of_n_by_execution"):
            if k in baselines:
                lines.append("| %s | %s | %s |"
                             % (label[k], _fmt(baselines[k]),
                                _fmt(premiums.get(k))))
        lines.append("")
        lines.append("Majority vote is computed over the candidates' "
                     "extracted final answers. Best-of-N by execution is "
                     "the oracle ceiling — what checking every candidate "
                     "directly would have found — printed for scale, not "
                     "as a baseline the tournament had to beat.")
    else:
        lines.append("The spend is counted above; without pool scores it "
                     "cannot be weighed against any baseline.")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    seen = set()
    for c in result["claims"]:
        if c.get("note") and c["note"] not in seen:
            seen.add(c["note"])
            lines.append("- (%s) %s" % (c["id"], c["note"]))
    lines.append("- Verdicts use a noise band of 0.02 on oracle scores; "
                 "differences at or below it are not evidence.")
    lines.append("")
    return "\n".join(lines)


def write_outputs(out_dir, run, oracle, result):
    os.makedirs(out_dir, exist_ok=True)
    ledger = build_ledger(run, oracle, result)
    with open(os.path.join(out_dir, "ledger.json"), "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2, sort_keys=True)
    md = render_markdown(run, oracle, result, ledger)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(md)
    return ledger

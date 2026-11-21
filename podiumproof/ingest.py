"""Ingest a finished tournament run directory.

The first (and currently only) target format is the serialized state of
the Arena skill (github.com/Jakeschincariol/arena-skill, MIT): a run
directory holding one ``arena.json`` state file, per-round verdict files
``r<N>/<match_id>.verdict.json`` and solution files (spawn solutions in
``r0/``, revised solutions per round). Only the fields the audit needs
are read; unknown fields are ignored so newer state versions keep
working.
"""

import json
import os


class AuditError(Exception):
    """Raised when a run directory cannot be audited at all."""


CALLS_PER_MATCH = 5  # 2 attacks, 2 defences, 1 judge (the format's own accounting)


class Match(object):
    def __init__(self, raw, rnd):
        self.id = raw.get("id")
        self.round = rnd
        self.a = raw.get("a")
        self.b = raw.get("b")
        self.winner = raw.get("winner")
        self.loser = raw.get("loser")
        self.scores = raw.get("scores")  # {agent_id: weighted total} or None
        self.reason = raw.get("reason")
        self.survived = raw.get("survived") or []
        self.source = raw.get("source")
        self.verdict = None  # parsed verdict JSON, filled by load_verdicts

    @property
    def played(self):
        return self.winner is not None

    def fatal_flags(self):
        """{agent_id: bool} from the verdict file's per-criterion scores."""
        out = {}
        if isinstance(self.verdict, dict):
            scores = self.verdict.get("scores") or {}
            if isinstance(scores, dict):
                for aid, per in scores.items():
                    if isinstance(per, dict) and "fatal" in per:
                        v = per.get("fatal")
                        if isinstance(v, str):
                            v = v.strip().lower() in ("true", "yes", "1")
                        out[str(aid).strip().lower()] = bool(v)
        return out


class RunData(object):
    def __init__(self, run_dir, state):
        self.run_dir = run_dir
        self.state = state
        self.agents = sorted(state.get("agents") or {},
                             key=lambda aid: (len(aid), aid))
        self.champion = state.get("champion")
        self.seed = state.get("seed")
        self.agents_n = state.get("agents_n") or len(self.agents)
        self.has_baseline = bool(state.get("has_baseline"))
        self.final = state.get("final")
        self.matches = []
        for rd in state.get("rounds") or []:
            for raw in rd.get("matches") or []:
                self.matches.append(Match(raw, rd.get("n")))
        self.rounds_count = len(state.get("rounds") or [])

    # -- paths ---------------------------------------------------------
    def _resolve(self, stored, fallback_rel):
        """Resolve a solution path stored in state, tolerating runs that
        were moved after completion (stored paths are absolute)."""
        candidates = []
        if stored:
            candidates.append(stored)
            candidates.append(os.path.join(self.run_dir, stored))
            candidates.append(os.path.join(self.run_dir,
                                           os.path.basename(stored)))
        if fallback_rel:
            candidates.append(os.path.join(self.run_dir, fallback_rel))
        for cand in candidates:
            if cand and os.path.isfile(cand):
                return cand
        return None

    def spawn_solution_path(self, aid):
        return self._resolve(None, os.path.join("r0", aid + ".md"))

    def final_solution_path(self, aid):
        agent = (self.state.get("agents") or {}).get(aid) or {}
        return self._resolve(agent.get("solution"), None)

    def read_spawn_solution(self, aid):
        path = self.spawn_solution_path(aid)
        if path is None:
            return None
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def read_final_solution(self, aid):
        path = self.final_solution_path(aid)
        if path is None:
            return None
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()

    # -- verdict files ---------------------------------------------------
    def load_verdicts(self):
        for m in self.matches:
            path = os.path.join(self.run_dir, "r%d" % (m.round or 0),
                                "%s.verdict.json" % m.id)
            if os.path.isfile(path):
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        m.verdict = json.load(fh)
                except ValueError:
                    m.verdict = None
        return self

    # -- accounting ------------------------------------------------------
    def count_calls(self):
        played = [m for m in self.matches if m.played]
        calls = {
            "spawn": self.agents_n,
            "matches": len(played),
            "per_match": CALLS_PER_MATCH,
            "match_calls": CALLS_PER_MATCH * len(played),
        }
        calls["final_check"] = 1 if (self.final and self.final.get("result")) else 0
        calls["total"] = calls["spawn"] + calls["match_calls"] + calls["final_check"]
        return calls


def load_run(run_dir):
    run_dir = os.path.abspath(run_dir)
    state_path = os.path.join(run_dir, "arena.json")
    if not os.path.isfile(state_path):
        raise AuditError("no arena.json in %s (not an Arena-format run directory)"
                         % run_dir)
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except ValueError as exc:
        raise AuditError("arena.json is not valid JSON: %s" % exc)
    if not isinstance(state, dict) or not state.get("agents"):
        raise AuditError("arena.json has no agents table")
    run = RunData(run_dir, state)
    run.load_verdicts()
    return run

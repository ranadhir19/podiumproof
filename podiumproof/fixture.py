"""Synthetic tournaments with known ground truth.

``make-fixture`` writes a complete Arena-format run directory whose
oracle is known by construction, so the audit's verdicts can be checked
against the truth that was planted:

``flawed`` (16 agents)
    A pool with real headroom (one genuinely best candidate) ruined by
    a bad judge: the best candidate is eliminated in round 1, a
    candidate carrying a planted fatal arithmetic flaw reaches the
    final unflagged, the judge's decisive-match accuracy is below
    chance, presentation order decides most matches, and the crowned
    champion scores below a random pick from its own pool. The honest
    audit verdict is REFUTED on nearly every claim, stamp JUDGE
    ARTEFACT.

``sound`` (8 agents)
    The same shape with a competent judge: every decisive match goes
    to the better candidate, the fatal flaw is flagged and its carrier
    eliminated in round 1, and the true best takes the title. The
    honest audit verdict is SUPPORTED throughout, stamp PREMIUM REAL.

The fixtures are generated deterministically; the tests assert the
audit catches the planted defects and clears the sound run.
"""

import json
import os
import random

WEIGHTS = (("correctness", 30), ("completeness", 25), ("specificity", 15),
           ("robustness", 20), ("clarity", 10))

_REASONING = [
    ("first-principles", "First principles", "Strip the problem to what is given and rebuild."),
    ("worked-example", "Worked example", "Solve a small case by hand, then generalize."),
    ("inversion", "Inversion", "Work backwards from the quantity asked for."),
]
_WORKFLOWS = [
    ("draft-revise", "Draft, then revise", "Write a full draft, then attack it yourself."),
    ("test-first", "Test first", "State the checks the answer must pass before solving."),
]
_STRATEGIES = [
    ("simplest", "Simplest thing that works", "Prefer the shortest correct path."),
    ("edge-cases", "Edge cases first", "Hunt the boundary cases before the main line."),
]


def _card(i):
    return {
        "reasoning": dict(zip(("id", "name", "how"), _REASONING[i % 3])),
        "workflow": dict(zip(("id", "name", "how"), _WORKFLOWS[i % 2])),
        "strategy": dict(zip(("id", "name", "how"), _STRATEGIES[(i // 2) % 2])),
    }


def _criteria(rng, level, bump=0.0):
    crit = {}
    for key, _w in WEIGHTS:
        v = level + bump + rng.uniform(-0.5, 0.5)
        crit[key] = round(max(0.0, min(10.0, v)), 1)
    crit["fatal"] = False
    return crit


def _total(crit):
    return round(sum(crit[k] * w for k, w in WEIGHTS) / 10.0, 2)


# ---------------------------------------------------------------- scenarios
# Each agent: (oracle score, final answer, solution body)
# Each match: (first-listed, second-listed, winner, judge flags second-listed
#              or first-listed fatal where noted in the scenario builder)

FLAWED_TASK = ("Maya buys 14 notebooks at $3 each and pays with a $50 bill. "
               "How much change does she get?")
FLAWED_AGENTS = {
    "a001": (0.30, "42", "14 notebooks at $3 come to $42, so the change is $42."),
    "a002": (0.25, "42", "The notebooks cost 14 x 3 = 42 dollars. Change: 42."),
    "a003": (1.00, "8", "The notebooks cost 14 x 3 = 42 dollars. Maya pays 50, "
                        "so her change is 50 - 42 = 8 dollars."),
    "a004": (0.40, "12", "14 x 3 = 42 spent. She also gets a loyalty discount "
                         "of 4, so 50 - 42 + 4 = 12."),
    "a005": (0.20, "42", "Multiply: 14 x 3 = 42. That is the change."),
    "a006": (0.55, "38", "Cost is 42. The till gives change in tens first: "
                         "50 - 42 = 8, but rounding to the register's steps "
                         "the answer recorded is 38."),
    "a007": (0.20, "12", "The notebooks cost 14 x 3 = 38 dollars. Change: "
                         "50 - 38 = 12."),
    "a008": (0.35, "42", "14 x 3 = 42. Maya's change equals the amount "
                         "spent, 42."),
    "a009": (0.15, "2", "She buys 14, pays 50, change is 2 after fees."),
    "a010": (0.50, "45", "Notebooks are about $3 each, 14 of them about $45 "
                         "with tax; change is quoted as 45."),
    "a011": (0.28, "42", "Total spend 42, so change 42."),
    "a012": (0.34, "38", "Spend is 42; the shop keeps a 4 dollar deposit, "
                         "so change is 50 - 12 = 38."),
    "a013": (0.22, "42", "14 times 3 is 42, the change."),
    "a014": (0.33, "20", "She gets two ten-dollar bills back: 20."),
    "a015": (0.18, "5", "Change is a five dollar bill: 5."),
    "a016": (0.60, "35", "Cost 42, change 8; with the 27 dollar gift card "
                         "balance the effective change is 35."),
}
# (round, first, second, winner) — winners scripted; see module docstring.
FLAWED_MATCHES = [
    (1, "a008", "a003", "a008"), (1, "a001", "a016", "a016"),
    (1, "a007", "a009", "a007"), (1, "a006", "a005", "a006"),
    (1, "a012", "a002", "a012"), (1, "a013", "a010", "a013"),
    (1, "a011", "a004", "a011"), (1, "a014", "a015", "a015"),
    (2, "a008", "a016", "a008"), (2, "a007", "a006", "a007"),
    (2, "a012", "a013", "a012"), (2, "a015", "a011", "a015"),
    (3, "a007", "a008", "a007"), (3, "a015", "a012", "a012"),
    (4, "a007", "a012", "a012"),
]
FLAWED_CANARY = ["a007"]

SOUND_TASK = ("A baker makes 9 trays with 12 rolls on each tray. He sells "
              "73 rolls. How many rolls are left?")
SOUND_AGENTS = {
    "a001": (0.25, "108", "9 trays of 12 rolls is 108 rolls. Left: 108."),
    "a002": (0.80, "35", "9 x 12 = 108 rolls baked. After selling 73, "
                         "108 - 73 = 35 remain."),
    "a003": (0.30, "81", "9 x 12 = 108; he sells about a quarter, leaving 81."),
    "a004": (0.45, "29", "108 rolls; 73 sold and some dropped, leaving 29."),
    "a005": (1.00, "35", "Total baked: 9 x 12 = 108 rolls. Sold: 73. "
                         "Remaining: 108 - 73 = 35 rolls. Check: 73 + 35 = 108."),
    "a006": (0.20, "23", "9 trays x 12 rolls = 96 rolls. After selling 73: "
                         "96 - 73 = 23."),
    "a007": (0.55, "35", "108 baked, 73 sold, so 35 left."),
    "a008": (0.38, "26", "Roughly 100 rolls, minus 73 sold, about 26 left."),
}
SOUND_MATCHES = [
    (1, "a005", "a006", "a005"), (1, "a003", "a002", "a002"),
    (1, "a007", "a004", "a007"), (1, "a001", "a008", "a008"),
    (2, "a002", "a005", "a005"), (2, "a007", "a008", "a007"),
    (3, "a005", "a007", "a005"),
]
SOUND_CANARY = ["a006"]
SOUND_FLAGGED = {("r1-m01", "a006")}  # (match id, agent) the judge flags fatal


def _build(dest, task, agents, matches, canary, flagged, seed, correct):
    os.makedirs(dest, exist_ok=True)
    ids = sorted(agents, key=lambda a: (len(a), a))
    rng = random.Random("podiumproof-fixture:%d" % seed)

    # spawn solutions
    os.makedirs(os.path.join(dest, "r0"), exist_ok=True)
    with open(os.path.join(dest, "task.md"), "w", encoding="utf-8") as fh:
        fh.write(task + "\n")
    for aid in ids:
        _score, ans, body = agents[aid]
        with open(os.path.join(dest, "r0", aid + ".md"), "w",
                  encoding="utf-8") as fh:
            fh.write("%s\n\nANSWER: %s\n" % (body, ans))

    # matches, grouped by round
    rounds = {}
    for rnd, a, b, winner in matches:
        rounds.setdefault(rnd, []).append((a, b, winner))
    alive = list(ids)
    state_agents = {}
    for i, aid in enumerate(ids):
        state_agents[aid] = {"card": _card(i), "solution": "r0/%s.md" % aid,
                             "alive": True, "eliminated_in": None,
                             "eliminated_by": None, "byes": 0}
    state_rounds = []
    champion = None
    for rnd in sorted(rounds):
        ms = rounds[rnd]
        width = max(2, len(str(len(ms))))
        match_objs = []
        survivors = []
        for j, (a, b, winner) in enumerate(ms):
            mid = "r%d-m%0*d" % (rnd, width, j + 1)
            loser = b if winner == a else a
            # rubric criteria: level from oracle score, winner bumped so
            # the recorded totals agree with the recorded winner
            ca = _criteria(rng, 2.0 + 7.0 * agents[a][0])
            cb = _criteria(rng, 2.0 + 7.0 * agents[b][0])
            crit = {a: ca, b: cb}
            win_crit, lose_crit = crit[winner], crit[loser]
            bump = 0.0
            while _total(win_crit) <= _total(lose_crit) and bump < 3.0:
                bump += 0.5
                win_crit["correctness"] = min(10.0, win_crit["correctness"] + 0.5)
                win_crit["completeness"] = min(10.0, win_crit["completeness"] + 0.5)
            for mid_agent in (a, b):
                if (mid, mid_agent) in flagged:
                    crit[mid_agent]["fatal"] = True
            verdict = {"winner": winner,
                       "scores": {a: ca, b: cb},
                       "standing": {a: [], b: []},
                       "reason": "Higher rubric total on the revised "
                                 "solutions.",
                       "survived": ["attack on the arithmetic was answered"]}
            rdir = os.path.join(dest, "r%d" % rnd)
            os.makedirs(rdir, exist_ok=True)
            with open(os.path.join(rdir, mid + ".verdict.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(verdict, fh, indent=2, sort_keys=True)
            # revised solutions for both sides; state pointers advance
            for aid in (a, b):
                _s, ans, body = agents[aid]
                rel = "r%d/%s.%s.solution.md" % (rnd, mid, aid)
                with open(os.path.join(dest, rel), "w", encoding="utf-8") as fh:
                    fh.write("%s\n\nRevision after defence: the attacks "
                             "were answered and the working tightened.\n\n"
                             "ANSWER: %s\n" % (body, ans))
                state_agents[aid]["solution"] = rel
            totals = {a: _total(ca), b: _total(cb)}
            match_objs.append({"id": mid, "a": a, "b": b, "winner": winner,
                               "loser": loser,
                               "reason": verdict["reason"],
                               "survived": verdict["survived"],
                               "scores": totals, "source": "judge"})
            state_agents[loser]["alive"] = False
            state_agents[loser]["eliminated_in"] = rnd
            state_agents[loser]["eliminated_by"] = winner
            survivors.append(winner)
        state_rounds.append({"n": rnd, "alive": alive, "matches": match_objs,
                             "bye": None, "closed": True})
        alive = sorted(survivors, key=lambda a: (len(a), a))
    if len(alive) == 1:
        champion = alive[0]

    state = {"version": 1, "created": "2026-11-20 12:00:00", "seed": seed,
             "agents_n": len(ids), "cards_available": 2160, "wave": 10,
             "dir": ".", "has_baseline": False, "agents": state_agents,
             "rounds": state_rounds, "champion": champion, "final": None}
    with open(os.path.join(dest, "arena.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)

    oracle = {"task": task, "correct_answer": correct,
              "scores": {a: agents[a][0] for a in ids},
              "answers": {a: agents[a][1] for a in ids},
              "fatal_flaw": list(canary)}
    with open(os.path.join(dest, "oracle.json"), "w", encoding="utf-8") as fh:
        json.dump(oracle, fh, indent=2, sort_keys=True)
    return dest


def build_fixture(dest, scenario):
    if scenario == "flawed":
        return _build(dest, FLAWED_TASK, FLAWED_AGENTS, FLAWED_MATCHES,
                      FLAWED_CANARY, set(), seed=7, correct="8")
    if scenario == "sound":
        return _build(dest, SOUND_TASK, SOUND_AGENTS, SOUND_MATCHES,
                      SOUND_CANARY, SOUND_FLAGGED, seed=3, correct="35")
    raise ValueError("unknown scenario %r (one of: flawed, sound)" % scenario)

"""Ground truth for an audit: the oracle.

An oracle says, for every candidate in the spawn pool, how good that
candidate actually was. podiumproof never invents ground truth; it takes
it from exactly three sources, in this order:

1. An oracle JSON file (``--oracle``)::
       {"scores": {"a001": 0.3, ...},          # 0..1 per spawn candidate
        "answers": {"a001": "42", ...},        # optional extracted answers
        "correct_answer": "8",                 # optional
        "fatal_flaw": ["a007"],                # optional planted-flaw canaries
        "baseline_score": 0.0}                 # optional rejected-baseline score

2. Answer extraction (``--correct-answer`` or the oracle file's
   ``correct_answer``): final answers are pulled from the spawn solution
   files (``ANSWER: x`` or ``#### x``) and scored 1/0 against the key.

3. Nothing. Then every check that needs ground truth reports
   UNVERIFIABLE instead of guessing. That is the point of the tool.
"""

import json
import os
import re

_ANSWER_PATTERNS = (
    re.compile(r"ANSWER\s*:\s*(.+)", re.IGNORECASE),
    re.compile(r"####\s*(.+)"),
)


def normalize_answer(text):
    if text is None:
        return None
    s = str(text).strip().lower()
    s = s.rstrip(".")
    s = s.replace(",", "").replace("$", "").replace(" ", "")
    # 8.0 and 8 are the same answer; 08 is too
    try:
        f = float(s)
        if f == int(f):
            s = str(int(f))
    except ValueError:
        pass
    return s


def extract_answer(solution_text):
    """The last ANSWER:/#### marker wins (solutions revise as they go)."""
    if not solution_text:
        return None
    found = None
    for line in solution_text.splitlines():
        for pat in _ANSWER_PATTERNS:
            m = pat.search(line)
            if m:
                found = m.group(1).strip()
    return found


class Oracle(object):
    def __init__(self):
        self.scores = {}          # agent_id -> float in [0, 1], spawn pool
        self.answers = {}         # agent_id -> raw extracted/given answer
        self.correct_answer = None
        self.fatal_flaws = []     # agent ids carrying a known fatal flaw
        self.baseline_score = None
        self.sources = []         # human-readable provenance notes

    @property
    def has_scores(self):
        return bool(self.scores)

    def score(self, aid):
        return self.scores.get(aid)


def load_oracle(run, oracle_path=None, correct_answer=None):
    oracle = Oracle()
    data = {}
    if oracle_path:
        with open(oracle_path, encoding="utf-8") as fh:
            data = json.load(fh)
        oracle.sources.append("oracle file %s" % os.path.basename(oracle_path))

    if data.get("correct_answer") is not None:
        oracle.correct_answer = data["correct_answer"]
    if correct_answer is not None:
        oracle.correct_answer = correct_answer
        oracle.sources.append("--correct-answer")

    for aid, ans in (data.get("answers") or {}).items():
        oracle.answers[aid] = ans
    for aid, val in (data.get("scores") or {}).items():
        try:
            oracle.scores[aid] = float(val)
        except (TypeError, ValueError):
            pass
    oracle.fatal_flaws = [str(a) for a in (data.get("fatal_flaw") or [])]
    if data.get("baseline_score") is not None:
        try:
            oracle.baseline_score = float(data["baseline_score"])
        except (TypeError, ValueError):
            pass

    # Fill answers by extracting from the spawn solutions we can read.
    extracted = 0
    for aid in run.agents:
        if aid not in oracle.answers:
            ans = extract_answer(run.read_spawn_solution(aid))
            if ans is not None:
                oracle.answers[aid] = ans
                extracted += 1
    if extracted:
        oracle.sources.append("answers extracted from %d spawn solutions"
                              % extracted)

    # Derive binary scores from answers when no explicit scores exist.
    if oracle.correct_answer is not None:
        key = normalize_answer(oracle.correct_answer)
        derived = 0
        for aid, ans in oracle.answers.items():
            if aid not in oracle.scores:
                oracle.scores[aid] = 1.0 if normalize_answer(ans) == key else 0.0
                derived += 1
        if derived:
            oracle.sources.append("scores derived from answers vs the key "
                                  "(%d candidates)" % derived)
    return oracle


def champion_final_score(run, oracle):
    """Score the champion's *revised final* solution, when derivable.

    The pool checks rank the champion's spawn candidate like-for-like;
    this is the corroborating number for the answer that actually came
    back. Returns None when it cannot be derived honestly.
    """
    if oracle.correct_answer is None or not run.champion:
        return None
    ans = extract_answer(run.read_final_solution(run.champion))
    if ans is None:
        return None
    key = normalize_answer(oracle.correct_answer)
    return 1.0 if normalize_answer(ans) == key else 0.0

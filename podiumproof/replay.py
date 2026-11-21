"""Champion stability: replay the recorded pool under re-seeded brackets.

The recorded run happened once, with one seeding. Whether its champion
is a property of the candidate pool or an accident of the draw is a
measurable question: replay the same spawn pool through fresh random
brackets, judging each simulated match with the judge model fitted to
the run's own recorded matches (see judgemodel), and count how often
the recorded champion wins again, and how often the oracle's best
candidate wins at all.

This is a model-based estimate, not a re-run of the real judge — the
real judge is a model call, and podiumproof makes none. The report
labels it as such.
"""

import random
from collections import Counter


def _play_bracket(alive, scores, fit, rng):
    alive = list(alive)
    while len(alive) > 1:
        rng.shuffle(alive)
        nxt = []
        i = 0
        if len(alive) % 2 == 1:
            nxt.append(alive[0])  # one bye, as the format gives
            i = 1
        while i < len(alive):
            x, y = alive[i], alive[i + 1]
            gap = scores[x] - scores[y]
            p = fit.win_prob_first(gap)
            nxt.append(x if rng.random() < p else y)
            i += 2
        alive = nxt
    return alive[0]


def replay_brackets(scores, fit, champion, k=200, seed=20261120):
    """scores: {agent_id: oracle score} for the full spawn pool."""
    pool = sorted(scores)
    best_score = max(scores.values())
    oracle_best = set(a for a in pool if scores[a] == best_score)
    rng = random.Random(seed)
    champs = Counter()
    for _ in range(k):
        champs[_play_bracket(pool, scores, fit, rng)] += 1
    modal, modal_n = champs.most_common(1)[0]
    return {
        "replays": k,
        "seed": seed,
        "champion_reproduction_rate": champs.get(champion, 0) / float(k),
        "oracle_best_win_rate": sum(champs[a] for a in oracle_best) / float(k),
        "modal_champion": modal,
        "modal_rate": modal_n / float(k),
        "distinct_champions": len(champs),
    }

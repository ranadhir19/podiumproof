"""A judge model fitted to a run's own recorded matches.

For every recorded match where the oracle separates the two candidates,
we know the presentation order (the format lists the side the judge read
first as ``a``), the oracle gap, and who won. A two-parameter logistic
model describes that judge:

    P(first-listed wins) = sigmoid(alpha + beta * gap)

``alpha`` is the position bias: alpha > 0 means the side read first wins
more often than the quality gap justifies. ``beta`` is discrimination:
how strongly the judge's verdicts track the true quality gap at all.
Both are fitted by Newton-Raphson on the run's own matches with a light
L2 penalty, so the audit describes *this* judge in *this* run, not a
judge in general.

From the fitted model we also estimate swap consistency: for each
recorded pair, the probability that judging it again with the
presentation order swapped would crown the same winner. A true swapped
re-judgement needs the judge itself; offline, the model-based estimate
is what exists, and the report says so.
"""

import math

Z95 = 1.959964


def sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def wilson(k, n, z=Z95):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 1.0)
    p = k / float(n)
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


class JudgeFit(object):
    def __init__(self):
        self.ok = False
        self.reason = None
        self.alpha = 0.0        # position bias (log-odds for the first-listed)
        self.beta = 0.0         # gap sensitivity
        self.se_alpha = None
        self.n_decisive = 0
        self.accuracy = None    # fraction of decisive matches the judge got right
        self.accuracy_ci = None
        self.first_win_rate = None
        self.swap_consistency = None  # model-estimated, averaged over decisive matches

    def win_prob_first(self, gap):
        """P(the first-listed side wins) for a pair with this oracle gap."""
        return sigmoid(self.alpha + self.beta * gap)


def _fit_logistic(rows):
    """rows: list of (gap, first_won 0/1). Returns (alpha, beta, se_alpha)."""
    alpha, beta = 0.0, 1.0
    lam = 1e-3
    for _ in range(200):
        ga = gb = haa = hab = hbb = 0.0
        for gap, y in rows:
            p = sigmoid(alpha + beta * gap)
            w = max(p * (1.0 - p), 1e-9)
            r = y - p
            ga += r
            gb += r * gap
            haa += w
            hab += w * gap
            hbb += w * gap * gap
        gb -= lam * beta
        hbb += lam
        det = haa * hbb - hab * hab
        if abs(det) < 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        # damped step, clamped so separated data cannot run away
        step = max(-2.0, min(2.0, da)), max(-2.0, min(2.0, db))
        alpha += step[0]
        beta += step[1]
        alpha = max(-8.0, min(8.0, alpha))
        beta = max(-50.0, min(50.0, beta))
        if abs(step[0]) < 1e-9 and abs(step[1]) < 1e-9:
            break
    # standard error of alpha from the inverse Hessian at the optimum
    haa = hab = hbb = 0.0
    for gap, y in rows:
        p = sigmoid(alpha + beta * gap)
        w = max(p * (1.0 - p), 1e-9)
        haa += w
        hab += w * gap
        hbb += w * gap * gap
    hbb += lam
    det = haa * hbb - hab * hab
    se_alpha = math.sqrt(hbb / det) if det > 1e-12 else None
    return alpha, beta, se_alpha


def fit_judge(matches, oracle):
    """Fit the judge model on a run's recorded matches. ``matches`` are
    ingest.Match objects; ``oracle`` supplies spawn-pool scores."""
    fit = JudgeFit()
    rows = []
    correct = 0
    first_wins = 0
    played = 0
    for m in matches:
        if not m.played:
            continue
        played += 1
        if m.winner == m.a:
            first_wins += 1
        sa, sb = oracle.score(m.a), oracle.score(m.b)
        if sa is None or sb is None or sa == sb:
            continue
        rows.append((sa - sb, 1 if m.winner == m.a else 0))
        better = m.a if sa > sb else m.b
        if m.winner == better:
            correct += 1
    fit.n_decisive = len(rows)
    if played:
        fit.first_win_rate = first_wins / float(played)
    if len(rows) < 4:
        fit.reason = ("only %d decisive matches (oracle-separated) — too few "
                      "to fit a judge model" % len(rows))
        return fit
    fit.accuracy = correct / float(len(rows))
    fit.accuracy_ci = wilson(correct, len(rows))
    fit.alpha, fit.beta, fit.se_alpha = _fit_logistic(rows)
    # model-estimated swap consistency, averaged over the decisive matches
    total = 0.0
    for gap, _y in rows:
        p_first_order1 = sigmoid(fit.alpha + fit.beta * gap)
        p_first_order2 = 1.0 - sigmoid(fit.alpha - fit.beta * gap)
        total += (p_first_order1 * p_first_order2
                  + (1.0 - p_first_order1) * (1.0 - p_first_order2))
    fit.swap_consistency = total / float(len(rows))
    fit.ok = True
    return fit

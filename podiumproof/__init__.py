"""podiumproof: audit a finished LLM tournament against ground truth.

The tournament crowned a champion. podiumproof checks whether the crown
was earned: it scores the whole candidate pool against an oracle, fits a
judge model to the run's own recorded matches, replays the bracket under
re-seeding, inspects the judge in situ, and prints a cost ledger against
the honest baselines the spend had to beat. Every implicit claim the
tournament makes comes back SUPPORTED, REFUTED or UNVERIFIABLE, with the
measurement attached.

Pure Python standard library. Offline. No model calls.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]

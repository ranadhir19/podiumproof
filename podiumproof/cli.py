"""podiumproof command line.

    python3 -m podiumproof audit <run_dir> [--oracle oracle.json]
                               [--correct-answer 8] [--replays 200]
                               [--out DIR]
    python3 -m podiumproof make-fixture <dir> --scenario flawed|sound

``audit`` writes report.md and ledger.json (default: <run_dir>/audit/)
and prints the summary stamp. Exit code 0 means the audit ran — a
REFUTED verdict is a successful audit, not a failure. Exit code 2
means the run could not be ingested at all.
"""

import argparse
import os
import sys

from . import __version__
from .checks import run_checks
from .fixture import build_fixture
from .ingest import AuditError, load_run
from .oracle import load_oracle
from .report import write_outputs


def _audit(args):
    try:
        run = load_run(args.run_dir)
    except AuditError as exc:
        print("podiumproof: %s" % exc, file=sys.stderr)
        return 2
    oracle_path = args.oracle
    if oracle_path is None:
        candidate = os.path.join(run.run_dir, "oracle.json")
        if os.path.isfile(candidate):
            oracle_path = candidate
    oracle = load_oracle(run, oracle_path=oracle_path,
                         correct_answer=args.correct_answer)
    result = run_checks(run, oracle, replays=args.replays,
                        replay_seed=args.seed)
    out_dir = args.out or os.path.join(run.run_dir, "audit")
    write_outputs(out_dir, run, oracle, result)
    print("champion: %s" % run.champion)
    for c in result["claims"]:
        print("  %s  %-9s %s" % (c["id"], c["verdict"], c["claim"]))
    print("stamp: %s" % result["stamp"])
    print("wrote %s and %s" % (os.path.join(out_dir, "report.md"),
                               os.path.join(out_dir, "ledger.json")))
    return 0


def _make_fixture(args):
    build_fixture(args.dir, args.scenario)
    print("wrote %s fixture to %s (oracle.json included)"
          % (args.scenario, args.dir))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="podiumproof",
        description="Audit a finished LLM tournament against ground truth.")
    parser.add_argument("--version", action="version",
                        version="podiumproof %s" % __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="audit a tournament run directory")
    p_audit.add_argument("run_dir")
    p_audit.add_argument("--oracle", default=None,
                         help="oracle JSON (default: <run_dir>/oracle.json "
                              "when present)")
    p_audit.add_argument("--correct-answer", default=None,
                         help="score candidates by extracting final answers "
                              "and comparing to this key")
    p_audit.add_argument("--replays", type=int, default=200,
                         help="bracket replays for champion stability "
                              "(default 200)")
    p_audit.add_argument("--seed", type=int, default=20261120,
                         help="replay RNG seed (default 20261120)")
    p_audit.add_argument("--out", default=None,
                         help="output directory (default <run_dir>/audit)")
    p_audit.set_defaults(func=_audit)

    p_fix = sub.add_parser("make-fixture",
                           help="write a synthetic tournament with known "
                                "ground truth")
    p_fix.add_argument("dir")
    p_fix.add_argument("--scenario", choices=("flawed", "sound"),
                       required=True)
    p_fix.set_defaults(func=_make_fixture)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

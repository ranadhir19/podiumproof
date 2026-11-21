#!/usr/bin/env python3
"""validate.py — the pre-push gate for podiumproof.

Runs, in order:
  1. required-file checks (LICENSE, README, COMPLIANCE, NAME_CHECK)
  2. a standard-library-only import scan of the package
  3. the full unittest suite
  4. end-to-end CLI audits of both synthetic fixtures, asserting the
     summary stamps (JUDGE ARTEFACT for the planted-defect run,
     PREMIUM REAL for the sound run)

Exit 0 only if everything passes. Failures are fixed, never edited
away in the tests.
"""

import ast
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
REQUIRED = ("LICENSE", "README.md", "COMPLIANCE.md", "NAME_CHECK.md",
            "pyproject.toml")


def check_files():
    missing = [f for f in REQUIRED
               if not os.path.isfile(os.path.join(ROOT, f))]
    if missing:
        print("FAIL: missing required files: %s" % ", ".join(missing))
        return False
    print("ok: required files present (%s)" % ", ".join(REQUIRED))
    return True


def check_stdlib_only():
    stdlib = getattr(sys, "stdlib_module_names", None)
    if stdlib is None:
        print("skip: sys.stdlib_module_names unavailable on this Python")
        return True
    bad = []
    pkg = os.path.join(ROOT, "podiumproof")
    for name in sorted(os.listdir(pkg)):
        if not name.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(pkg, name)).read())
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".")[0]
                    if mod not in stdlib and mod != "podiumproof":
                        bad.append("%s: import %s" % (name, mod))
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    mod = node.module.split(".")[0]
                    if mod not in stdlib and mod != "podiumproof":
                        bad.append("%s: from %s import" % (name, mod))
    if bad:
        print("FAIL: non-stdlib imports:\n  %s" % "\n  ".join(bad))
        return False
    print("ok: package imports are standard library only")
    return True


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def check_tests():
    r = run([sys.executable, "-m", "unittest", "discover", "-s",
             os.path.join(ROOT, "tests"), "-v"], cwd=ROOT)
    sys.stdout.write(r.stderr if r.stderr else r.stdout)
    if r.returncode != 0:
        print("FAIL: unittest suite")
        return False
    print("ok: unittest suite passed")
    return True


def check_end_to_end():
    env = dict(os.environ, PYTHONPATH=ROOT)
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for scenario, stamp in (("flawed", "JUDGE ARTEFACT"),
                                ("sound", "PREMIUM REAL")):
            d = os.path.join(tmp, scenario)
            r = run([sys.executable, "-m", "podiumproof", "make-fixture",
                     d, "--scenario", scenario], env=env)
            if r.returncode != 0:
                print("FAIL: make-fixture %s: %s" % (scenario, r.stderr))
                ok = False
                continue
            r = run([sys.executable, "-m", "podiumproof", "audit", d],
                    env=env)
            if r.returncode != 0 or ("stamp: %s" % stamp) not in r.stdout:
                print("FAIL: audit %s did not stamp %s\n%s%s"
                      % (scenario, stamp, r.stdout, r.stderr))
                ok = False
            else:
                print("ok: %s fixture audits to %s" % (scenario, stamp))
    return ok


def main():
    results = [check_files(), check_stdlib_only(), check_tests(),
               check_end_to_end()]
    if all(results):
        print("VALIDATE: ALL CHECKS PASSED")
        return 0
    print("VALIDATE: FAILURES PRESENT")
    return 1


if __name__ == "__main__":
    sys.exit(main())

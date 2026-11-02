#!/usr/bin/env python3
"""
Deterministic regression guard for check_call_reparse in analyze_batch.py.

Runs the analyzer against callreparse_regression.cmd and asserts the EXACT set of
call-reparse lines, both directions:

  * every line whose text contains MUSTFLAG is reported call-reparse, and
  * NO other line is - the SAFE twins must stay clean.

The MUSTFLAG lines include three emitters an ADB front-end shipped verbatim, which
wrote every captured phone setting into a restore file as `call :dcx_do "... '<value>'"`
- and `call` parsed each value a second time on restore. The SAFE twins are the shapes
a careless version of the check would flag: the fix itself (value in a `set` line,
bare call), literal arguments, a variable NAME, a literal %% percent, prose that starts
with "Call", a direct call in the file (a review rule, not this check), an emitter
behind an inline rem (nothing ends a rem, so it is comment too) and a commented-out
emitter.

Run:  python tests/test_callreparse_regression.py
Exit: 0 = pass, 1 = a detection regression or a new false positive.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "callreparse_regression.cmd"


def analyze(path):
    out = subprocess.run([sys.executable, str(ANALYZER), str(path), "--json"],
                         capture_output=True, text=True)
    findings = json.loads(out.stdout)[str(path)]["findings"]
    return {f["line"] for f in findings if f["code"] == "call-reparse"}


def lines_with(text, token):
    """1-based line numbers of non-comment lines containing `token`."""
    out = set()
    for i, ln in enumerate(text.splitlines(), 1):
        s = ln.lstrip().lower()
        if s[:2] == "::" or s == "rem" or s.startswith(("rem ", "rem\t")):
            continue
        if token in ln:
            out.add(i)
    return out


def main():
    for p in (ANALYZER, FIXTURE):
        if not p.exists():
            print(f"FAIL: missing {p}")
            return 1

    text = FIXTURE.read_bytes().decode("ascii")
    got = analyze(FIXTURE)
    expect = lines_with(text, "MUSTFLAG")
    safe = lines_with(text, "SAFE:")

    problems = []
    if len(expect) < 8 or len(safe) < 8:
        problems.append(f"fixture lost cases: {len(expect)} MUSTFLAG, {len(safe)} SAFE")
    missed = sorted(expect - got)
    extra = sorted(got - expect)
    if missed:
        problems.append(f"NOT flagged (blind spot reopened): {missed}")
    if extra:
        problems.append(f"falsely flagged (new false positive): {extra}")

    if not problems:
        print(f"PASS  call-reparse={sorted(got)}  ({len(safe)} safe cases held clean)")
        return 0
    print("FAIL")
    for p in problems:
        print("  -", p)
    return 1


if __name__ == "__main__":
    sys.exit(main())

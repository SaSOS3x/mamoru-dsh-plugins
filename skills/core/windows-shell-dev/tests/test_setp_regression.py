#!/usr/bin/env python3
"""
Deterministic regression guard for check_setp_stale in analyze_batch.py.

Runs the analyzer against setp_regression.cmd and asserts the EXACT set of
setp-stale lines, both directions:

  * every prompt line whose text contains MUSTFLAG is reported setp-stale, and
  * NO other prompt is - the SAFE twins must stay clean.

Every prompt in the fixture is dispatch-style (value compared vs >=2 literals)
so each finding is an exact per-line assertion (a summary count could hide a
set-changing regression). The SAFE twins are the exact patterns that used to
false-positive: a var cleared at the routine's *top* (beyond the old 8-line
window), a default-value assignment (`set "s3=1"`), a compound
`set "x=" & set /p x=`, and an adjacent clear - plus a re-stale case (clear at
top, first prompt safe, second prompt of the same var flagged) so the "stop at
an earlier prompt" logic holds.

Run:  python tests/test_setp_regression.py
Exit: 0 = pass, 1 = a detection regression or a new false positive.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "setp_regression.cmd"


def lines_with(token):
    """1-based line numbers of non-comment fixture lines containing `token`."""
    text = FIXTURE.read_bytes().decode("ascii")
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

    out = subprocess.run(
        [sys.executable, str(ANALYZER), str(FIXTURE), "--json"],
        capture_output=True, text=True)
    findings = json.loads(out.stdout)[str(FIXTURE)]["findings"]

    got = {f["line"] for f in findings if f["code"] == "setp-stale"}
    expect = lines_with("MUSTFLAG")

    problems = []
    missed = sorted(expect - got)
    extra = sorted(got - expect)
    if missed:
        problems.append(f"NOT flagged (blind spot reopened): {missed}")
    if extra:
        problems.append(f"falsely flagged (new false positive): {extra}")

    if not problems:
        safe_n = FIXTURE.read_bytes().decode("ascii").count("SAFE:")
        print(f"PASS  setp-stale={sorted(got)}  ({safe_n} safe cases held clean)")
        return 0
    print("FAIL")
    for p in problems:
        print("  -", p)
    return 1


if __name__ == "__main__":
    sys.exit(main())

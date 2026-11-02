#!/usr/bin/env python3
"""
Deterministic regression guard for scripts/menuscan.py.

Runs the scan against menuscan_regression.cmd and asserts the EXACT set of flagged prompt
lines, both directions:

  * every prompt line whose text contains MUSTFLAG(text) is flagged, and its finding
    contains `text` (so the reason is pinned, not just the line), and
  * NO other prompt is - the SAFE twins must stay clean.

The SAFE twins are the shapes that false-positived on two production scripts before the
rules were tuned: a conditional `if ... echo` row, a dispatch past 40 lines behind negated
guards and an internal label, a loop-printed list, a [2] mentioned inside a sentence, an [i]
marker line, a `set /p x=<file` read between the rows, a Y/N row and a 3-wide grid, the
:Menu / :Menu_ask split, a computed goto, a value prompt, and the last option handled by a
catch-all goto that leaves the menu.

Run:  python tests/test_menuscan_regression.py
Exit: 0 = pass, 1 = a detection regression or a new false positive.
"""

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAN = HERE.parent / "scripts" / "menuscan.py"
FIXTURE = HERE / "menuscan_regression.cmd"
MARK = re.compile(r"MUSTFLAG\((.*?)\)")


def main():
    for p in (SCAN, FIXTURE):
        if not p.exists():
            print(f"FAIL: missing {p}")
            return 1

    text = FIXTURE.read_bytes().decode("ascii")
    expect = {}
    for i, ln in enumerate(text.splitlines(), 1):
        s = ln.lstrip().lower()
        if s.startswith("rem") or s.startswith("::"):
            continue
        m = MARK.search(ln)
        if m:
            expect[i] = m.group(1)

    out = subprocess.run([sys.executable, str(SCAN), str(FIXTURE)],
                         capture_output=True, text=True)
    got = {}
    for ln in out.stdout.splitlines():
        m = re.match(r"\s*(\d+) :", ln)          # a finding starts with the prompt line and its label
        if m:
            got[int(m.group(1))] = ln

    problems = []
    missed = sorted(set(expect) - set(got))
    extra = sorted(set(got) - set(expect))
    if missed:
        problems.append(f"NOT flagged (blind spot reopened): {missed}")
    if extra:
        problems.append(f"falsely flagged (new false positive): {extra} -> " +
                        " | ".join(got[i].strip() for i in extra))
    for i in sorted(set(expect) & set(got)):
        if expect[i] not in got[i]:
            problems.append(f"line {i}: flagged for the wrong reason: wanted '{expect[i]}' in: {got[i].strip()}")
    if out.returncode != 1:
        problems.append(f"exit code {out.returncode}, expected 1 when menus are flagged")
    safe_n = text.count("SAFE:")
    if safe_n < 10:
        problems.append(f"only {safe_n} SAFE cases in the fixture - was it truncated?")

    if not problems:
        print(f"PASS  flagged={sorted(got)}  ({safe_n} safe cases held clean)")
        return 0
    print("FAIL")
    for p in problems:
        print("  -", p)
    print(out.stdout)
    return 1


if __name__ == "__main__":
    sys.exit(main())

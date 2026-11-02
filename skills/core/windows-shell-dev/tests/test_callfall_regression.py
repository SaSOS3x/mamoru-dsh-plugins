#!/usr/bin/env python3
"""
Deterministic regression guard for the call-fallthrough and comment-in-block
rules in analyze_batch.py.

Runs the analyzer against callfall_regression.cmd and asserts the EXACT set of
flagged lines in both directions:

  * every line under "rem --- FLAG-CF:" must be reported call-fallthrough, and
    every line under "rem --- FLAG-CB:" must be reported comment-in-block
    (guards that the detectors still fire - a routine called from directly above
    its own label runs twice and its exit /b then ends the whole batch, which
    presents as "the menu never opens" rather than as a crash), and

  * NO other line may be flagged. That half is the harder one and is why the
    fixture carries five clean shapes: a call guarded by a goto, a call that
    transfers control on its own line (`|| goto`), a call with real work between
    it and the label, an echo that merely mentions a call, and - for the block
    rule - `rem` inside a block, `::` at top level, and `::` indented under the
    `if not X goto skip` idiom, which LOOKS like it is inside a block and is not.
    That last one is why the rule reads block depth from the parser simulation
    instead of from indentation.

Run:  python tests/test_callfall_regression.py
"""
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "callfall_regression.cmd"

RULES = {"CF": "call-fallthrough", "CB": "comment-in-block"}


def main():
    lines = FIXTURE.read_bytes().decode("ascii").split("\r\n")
    expected = {}
    for i, ln in enumerate(lines, 1):
        m = re.match(r"rem --- FLAG-(CF|CB):", ln)
        if m:
            expected[i + 1] = RULES[m.group(1)]

    out = subprocess.run([sys.executable, str(ANALYZER), str(FIXTURE)],
                         capture_output=True, text=True).stdout
    got = {}
    for m in re.finditer(r"\[(?:ERROR|WARN)\s*\]\s+L(\d+)\s+(call-fallthrough|comment-in-block)", out):
        got[int(m.group(1))] = m.group(2)

    rc = 0
    for i, rule in sorted(expected.items()):
        if got.get(i) != rule:
            print(f"FAIL: L{i} should be {rule} but got {got.get(i)!r}: {lines[i-1]!r}")
            rc = 1
    for i, rule in sorted(got.items()):
        if i not in expected:
            print(f"FAIL: L{i} flagged {rule} but is a clean shape: {lines[i-1]!r}")
            rc = 1
    if rc:
        return rc
    print(f"OK: {len(expected)} flagged as expected, 0 false positives "
          f"across {sum(1 for l in lines if l.startswith('rem --- CLEAN'))} clean shapes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
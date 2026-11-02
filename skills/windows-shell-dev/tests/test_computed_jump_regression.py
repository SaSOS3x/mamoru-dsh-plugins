#!/usr/bin/env python3
"""
Deterministic regression guard for computed jump targets in check_labels
(analyze_batch.py).

`goto :do_%CHOICE%` finishes its label name at run time, so the analyzer can
only see the fixed prefix `do_`. Reading that prefix as the whole label name
reported working menu dispatch - the very shape pitfall 4 recommends - as a
dangling-jump ERROR. Runs the analyzer against computed_jump_regression.cmd and
asserts the EXACT set of flagged lines, in both directions:

  * every line whose text contains MUSTERR must be reported goto-undefined or
    call-undefined: a computed target that NO label starts with can never land,
    whatever the variable holds, and a plain dangling jump is still caught; and
  * NO other line may be flagged: computed targets (%VAR%, !VAR!, %%a, %~1)
    whose prefix some label starts with, matched case-insensitively, plus an
    echoed computed jump.

Run:  python tests/test_computed_jump_regression.py
"""
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "computed_jump_regression.cmd"


def main():
    lines = FIXTURE.read_bytes().decode("ascii").split("\r\n")
    expected = {i for i, ln in enumerate(lines, 1)
                if "MUSTERR" in ln and not ln.lstrip().lower().startswith("rem")}
    if not expected:
        print("FAIL: the fixture has no MUSTERR lines - this test would pass vacuously.")
        return 1

    out = subprocess.run([sys.executable, str(ANALYZER), str(FIXTURE)],
                         capture_output=True, text=True).stdout
    got = {int(m.group(1)) for m in
           re.finditer(r"\[ERROR\]\s+L(\d+)\s+(?:goto|call)-undefined", out)}

    missed = sorted(expected - got)
    false_pos = sorted(got - expected)
    for i in missed:
        print(f"FAIL: L{i} can never land but was NOT flagged: {lines[i-1].strip()}")
    for i in false_pos:
        print(f"FAIL: L{i} was flagged but a label completes it: {lines[i-1].strip()}")
    if missed or false_pos:
        print(f"\n{len(missed)} missed, {len(false_pos)} false positive(s).")
        return 1
    print(f"OK: {len(expected)} jump(s) that can never land flagged, "
          f"0 false positives on computed targets that resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

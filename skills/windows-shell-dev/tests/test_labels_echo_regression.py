#!/usr/bin/env python3
"""
Deterministic regression guard for check_labels' echoed-text handling
(strip_echoed) in analyze_batch.py.

Runs the analyzer against labels_echo_regression.cmd and asserts the EXACT set
of flagged lines - in both directions, which is the point:

  * every line whose text contains MUSTERR must be reported goto-undefined or
    call-undefined (guards that the detector still fires - a dangling jump is
    exactly the bug this check exists to catch), and
  * NO other line may be flagged (guards against false positives - a batch file
    that GENERATES a batch file writes lines like `echo goto :done`, which is
    data, not control flow; five confident errors on a correct file is how
    people learn to ignore the analyser).

The traps are paired deliberately: an echoed goto sits next to a real one, and
`echo hi & goto :x` / `echo. & call :y` / `if 1==1 (echo x) else goto :z` are
cases where the echo stops at a separator and the jump after it is real. A rem is
the opposite - nothing ends it, so `echo x & rem note & goto :x` never jumps and
must stay clean - and "rem" inside a word (`call :lorem ipsum`) is not a rem.

Run:  python tests/test_labels_echo_regression.py
"""
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "labels_echo_regression.cmd"


def main():
    lines = FIXTURE.read_bytes().decode("ascii").split("\r\n")
    expected = {i for i, ln in enumerate(lines, 1)
                if "MUSTERR" in ln and not ln.lstrip().lower().startswith("rem")}

    out = subprocess.run([sys.executable, str(ANALYZER), str(FIXTURE)],
                         capture_output=True, text=True).stdout
    got = {int(m.group(1)) for m in
           re.finditer(r"\[ERROR\]\s+L(\d+)\s+(?:goto|call)-undefined", out)}

    missed = sorted(expected - got)
    false_pos = sorted(got - expected)
    for i in missed:
        print(f"FAIL: L{i} is a real dangling jump but was NOT flagged: {lines[i-1].strip()}")
    for i in false_pos:
        print(f"FAIL: L{i} was flagged but is echoed text or resolves: {lines[i-1].strip()}")
    if missed or false_pos:
        print(f"\n{len(missed)} missed, {len(false_pos)} false positive(s).")
        return 1
    print(f"OK: {len(expected)} real dangling jump(s) flagged, "
          f"0 false positives on echoed text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

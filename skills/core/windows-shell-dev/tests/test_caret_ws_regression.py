#!/usr/bin/env python3
"""
Deterministic regression guard for check_caret_ws in analyze_batch.py.

Runs the analyzer against caret_ws_regression.cmd and asserts the EXACT set of
flagged lines - in both directions, which is the point:

  * every line whose text contains MUSTFLAG must be reported caret-trailing-ws
    (guards that the detector still fires - a `^` followed by whitespace silently
    stops continuing the line, and nothing in an editor shows you that), and
  * NO other line may be flagged (guards against false positives - a caret at true
    end-of-line IS a real continuation, `^ ` mid-line is a deliberately escaped
    space, `^^` is an escaped caret, and a caret inside quotes is just text).

Note the marker sits in the *section comment above* each flagged line, because the
flagged line must end in whitespace and nothing else. Expectations are derived from
lines starting "rem --- FLAG:" + 1, not from a bare MUSTFLAG search - the fixture's
own header explains the convention and would otherwise count itself.

Run:  python tests/test_caret_ws_regression.py
"""
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "caret_ws_regression.cmd"


def main():
    lines = FIXTURE.read_bytes().decode("ascii").split("\r\n")
    # marker is on the section comment; the offending line is the next one
    expected = {i + 1 for i, ln in enumerate(lines, 1)
                if ln.startswith("rem --- FLAG:")}

    out = subprocess.run([sys.executable, str(ANALYZER), str(FIXTURE)],
                         capture_output=True, text=True).stdout
    got = {int(m.group(1)) for m in
           re.finditer(r"\[WARN\s*\]\s+L(\d+)\s+caret-trailing-ws", out)}

    missed = sorted(expected - got)
    false_pos = sorted(got - expected)
    for i in missed:
        print(f"FAIL: L{i} has a caret killed by trailing whitespace but was NOT flagged: {lines[i-1]!r}")
    for i in false_pos:
        print(f"FAIL: L{i} flagged but its caret is fine: {lines[i-1]!r}")
    if missed or false_pos:
        print(f"\n{len(missed)} missed, {len(false_pos)} false positive(s).")
        return 1
    print(f"OK: {len(expected)} dead continuation(s) flagged, "
          f"0 false positives on real continuations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

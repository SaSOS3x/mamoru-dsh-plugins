#!/usr/bin/env python3
"""
Deterministic regression guard for the three injection/identity detectors in
analyze_batch.py: check_pipe_validate (36), check_var_case_collision (38) and
check_shift_selfpath (40).

Runs the analyzer against injection_regression.cmd and asserts the EXACT set of
(line, code) pairs it reports - in both directions, which is the point:

  * every line marked "rem  FLAG:<code>" must be reported with that code (guards
    that the detectors still fire - all three are silent-corruption bugs that a
    reader's eye slides straight over), and
  * NOTHING else may be reported at any level (guards against false positives,
    which is not hypothetical here: the shift check originally flagged `%%~dp0`
    inside a generated batch file, where the doubling is an escape and the path
    correctly means the GENERATED file's directory, not this script's).

The fixture pairs each defect with the lookalike that must stay clean: a piped
literal vs. a piped variable, a matched-case set/clear vs. a case-differing pair,
and an emitted `%%~dp0` vs. a live `%~dp0`. A detector that fires on the whole
pair is as useless as one that fires on neither.

Expectations come from the marker comments, so the fixture is the single source
of truth - add a case to the .cmd and this test picks it up.

Run:  python tests/test_injection_regression.py
"""
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "injection_regression.cmd"
MARKER = "rem  FLAG:"


def main():
    lines = FIXTURE.read_bytes().decode("ascii").split("\r\n")
    # marker sits on the comment line above; the offending line is the next one
    expected = {(i + 1, ln[len(MARKER):].strip())
                for i, ln in enumerate(lines, 1) if ln.startswith(MARKER)}

    out = subprocess.run([sys.executable, str(ANALYZER), str(FIXTURE)],
                         capture_output=True, text=True).stdout
    got = {(int(m.group(1)), m.group(2)) for m in
           re.finditer(r"\[(?:ERROR|WARN|INFO)\s*\]\s+L(\d+)\s+([a-z0-9-]+):", out)}

    missed = sorted(expected - got)
    false_pos = sorted(got - expected)
    for i, code in missed:
        print(f"FAIL: L{i} should be reported {code} but was not: {lines[i-1]!r}")
    for i, code in false_pos:
        print(f"FAIL: L{i} reported {code} but that line is correct: {lines[i-1]!r}")
    if missed or false_pos:
        print(f"\n{len(missed)} missed, {len(false_pos)} false positive(s).")
        return 1
    print(f"OK: {len(expected)} defect(s) flagged with the right code, "
          f"0 false positives on the lookalikes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

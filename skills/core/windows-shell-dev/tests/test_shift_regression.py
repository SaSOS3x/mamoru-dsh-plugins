#!/usr/bin/env python3
"""
Deterministic regression guard for check_shift_selfpath in analyze_batch.py.

Runs the analyzer against shift_regression.cmd and asserts the EXACT set of
flagged lines in both directions:

  * every line under "rem --- FLAG:" must be reported shift-selfpath (guards that
    the detector still fires - after a top-level shift, %~dp0 is resolved from an
    argument - the current directory, or the drive root for a /switch - and every
    bundled file is looked for in the wrong place), and

  * NO other line may be flagged. This half is why the fixture exists at all: two
    false-positive shapes shipped before it did.

      - An ANSI-colour menu digit. `echo %g%[%w%0%g%] Back` prints a 0 between
        colour variables, and the % that CLOSES %w% reads as the % of a %0. These
        scripts are built out of that shape, so the rule blanks %VAR% references
        before looking for a parameter.
      - A shift inside a CALLED helper. `:walk_args` / shift / goto renumbers that
        call frame's parameters, not the script's, so it must not anchor warnings
        about the script's own %0.

    Plus two the rule already handled and must keep handling: a doubled %%~dp0
    (emitted text for a generated file - pitfall 27) and %10, which is parameter
    ten rather than %1 followed by a zero.

    A third false positive turned up later: the same helper reached by a COMPUTED
    call. `call :walk_%MODE%` can land on any label that starts with walk_, and
    reading the prefix as a label name left those helpers looking top-level.

Run:  python tests/test_shift_regression.py
"""
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "shift_regression.cmd"


def main():
    lines = FIXTURE.read_bytes().decode("ascii").split("\r\n")
    expected = {i + 1 for i, ln in enumerate(lines, 1)
                if ln.startswith("rem --- FLAG:")}

    out = subprocess.run([sys.executable, str(ANALYZER), str(FIXTURE)],
                         capture_output=True, text=True).stdout
    got = {int(m.group(1)) for m in
           re.finditer(r"\[ERROR\s*\]\s+L(\d+)\s+shift-selfpath", out)}

    missed = sorted(expected - got)
    false_pos = sorted(got - expected)
    for i in missed:
        print(f"FAIL: L{i} uses %0 after a real shift but was NOT flagged: {lines[i-1]!r}")
    for i in false_pos:
        print(f"FAIL: L{i} flagged but its %0 is fine: {lines[i-1]!r}")
    if missed or false_pos:
        print(f"\n{len(missed)} missed, {len(false_pos)} false positive(s).")
        return 1
    clean = sum(1 for l in lines if l.startswith("rem --- CLEAN"))
    print(f"OK: {len(expected)} real self-path use(s) flagged, "
          f"0 false positives across {clean} clean shapes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
Deterministic regression guard for check_prompt_width in analyze_batch.py.

Runs the analyzer against promptwidth_regression.cmd and asserts the EXACT set of
prompt-width lines, both directions:

  * every set /p line whose text contains MUSTFLAG is reported prompt-width, and
  * NO other prompt is - the SAFE twins must stay clean.

The SAFE twins are the shapes that would false-positive if the check were written
carelessly: a prompt one column under the limit, a short one, the fixed form with the
explanation moved to an echo line above, the `set /p VAR=<file` read-from-file idiom
(which has no prompt at all), a commented-out long prompt, and one where `%%` renders
as a single percent so the visible text is shorter than the source.

A second pass strips the `mode con` line and asserts the check goes completely silent -
a script that never declares a width could be running in any terminal, and guessing one
would invent findings.

Run:  python tests/test_promptwidth_regression.py
Exit: 0 = pass, 1 = a detection regression or a new false positive.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "promptwidth_regression.cmd"


def analyze(path):
    out = subprocess.run([sys.executable, str(ANALYZER), str(path), "--json"],
                         capture_output=True, text=True)
    findings = json.loads(out.stdout)[str(path)]["findings"]
    return {f["line"] for f in findings if f["code"] == "prompt-width"}


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

    problems = []
    missed = sorted(expect - got)
    extra = sorted(got - expect)
    if missed:
        problems.append(f"NOT flagged (blind spot reopened): {missed}")
    if extra:
        problems.append(f"falsely flagged (new false positive): {extra}")

    # no declared width -> nothing to measure against -> the check must stay silent
    with tempfile.TemporaryDirectory() as td:
        nowidth = Path(td) / "nowidth.cmd"
        stripped = "\r\n".join(l for l in text.split("\r\n") if "mode con" not in l)
        nowidth.write_bytes(stripped.encode("ascii"))
        quiet = analyze(nowidth)
        if quiet:
            problems.append(
                f"flagged {sorted(quiet)} in a script with no `mode con` - there is no "
                f"declared width to measure against, so the check must stay silent")

    if not problems:
        safe_n = text.count("SAFE:")
        print(f"PASS  prompt-width={sorted(got)}  ({safe_n} safe cases held clean, "
              f"and silent with no declared width)")
        return 0
    print("FAIL")
    for p in problems:
        print("  -", p)
    return 1


if __name__ == "__main__":
    sys.exit(main())

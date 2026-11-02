#!/usr/bin/env python3
"""
Deterministic regression guard for check_blocks in analyze_batch.py.

Runs the analyzer against paren_regression.cmd and asserts the EXACT set
of flagged lines - in both directions, which is the point:

  * every line whose text contains MUSTFLAG must be reported block-paren-literal
    (guards that the detector still fires - catches a refactor that reopens a
    blind spot), and
  * every line whose text contains MUSTERR must be reported block-early-close, and
  * NO other line may be flagged (guards against false positives - catches a
    refactor that makes the detector fire on safe code).

The fixture pairs each buggy case with its safe twin, including the exact
false-positive traps that surfaced while widening the check (a legit
`( echo a & echo b )`, a quoted-if with a clean body, a quoted `set "x=(y)"`,
top-level parens, escaped `^(...^)`, and for-in structural parens).

Run:  python tests/test_paren_regression.py
Exit: 0 = pass, 1 = a detection regression or a new false positive.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "paren_regression.cmd"


def lines_with(token, skip_comments=True):
    """1-based line numbers of fixture lines containing `token`. Comment lines
    (rem / ::) are skipped by default, since the analyzer never flags them and
    this file's header comment mentions the marker tokens while explaining them."""
    text = FIXTURE.read_bytes().decode("ascii")
    out = set()
    for i, ln in enumerate(text.splitlines(), 1):
        s = ln.lstrip()
        low = s.lower()
        if skip_comments and (s[:2] == "::" or low == "rem"
                              or low.startswith(("rem ", "rem\t"))):
            continue
        if token in ln:
            out.add(i)
    return out


def flagged_lines(findings, code):
    return {f["line"] for f in findings if f["code"] == code}


def main():
    if not ANALYZER.exists():
        print(f"FAIL: analyzer not found at {ANALYZER}")
        return 1
    if not FIXTURE.exists():
        print(f"FAIL: fixture not found at {FIXTURE}")
        return 1

    out = subprocess.run(
        [sys.executable, str(ANALYZER), str(FIXTURE), "--json"],
        capture_output=True, text=True)
    report = json.loads(out.stdout)
    findings = report[str(FIXTURE)]["findings"]

    expect_flag = lines_with("MUSTFLAG")
    expect_err = lines_with("MUSTERR")
    got_flag = flagged_lines(findings, "block-paren-literal")
    got_err = flagged_lines(findings, "block-early-close")
    unbalanced = [f for f in findings if f["code"] == "paren-unbalanced"]

    ok = True
    problems = []

    missed = expect_flag - got_flag
    if missed:
        ok = False
        problems.append(f"NOT flagged but should be (block-paren-literal): "
                        f"{sorted(missed)}  <- a blind spot reopened")
    false_pos = got_flag - expect_flag
    if false_pos:
        ok = False
        problems.append(f"flagged but should be CLEAN (block-paren-literal): "
                        f"{sorted(false_pos)}  <- new false positive")

    if got_err != expect_err:
        ok = False
        problems.append(f"block-early-close mismatch: expected "
                        f"{sorted(expect_err)}, got {sorted(got_err)}")

    if unbalanced:
        ok = False
        problems.append(f"fixture went paren-unbalanced (a block no longer "
                        f"self-contained): {unbalanced}")

    if ok:
        print(f"PASS  block-paren-literal={sorted(got_flag)}  "
              f"block-early-close={sorted(got_err)}  "
              f"({len(expect_flag)} flag cases, "
              f"{len(lines_with('SAFE:', skip_comments=False))} safe cases held clean)")
        return 0

    print("FAIL")
    for p in problems:
        print("  -", p)
    return 1


if __name__ == "__main__":
    sys.exit(main())

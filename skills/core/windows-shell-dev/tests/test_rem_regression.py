#!/usr/bin/env python3
"""
Deterministic regression guard for the rem rules in check_blocks (analyze_batch.py).

Two measured facts, both easy to get backwards:

  * nothing ends a rem. An inline `rem` comments out the rest of the LINE - `&`, `|`
    and `)` included - so on `if 1==1 (echo a & rem note & echo b)` the block never
    closes: measured, nothing after the '(' ran, exit 255, no message.
  * cmd runs a piped block - either side of the pipe - in a child after folding its
    lines into ONE line joined with `&`, so a rem anywhere in it comments out the rest
    of that line, the block's own ')' included. Measured: the child runs nothing from
    the block, not even the lines before the rem; no message, and the script carries on.

Runs the analyzer against rem_regression.cmd and asserts the EXACT sets, both ways:
every MUSTEAT line is reported rem-eats-paren, every MUSTPIPE line rem-in-piped-block,
no other line is reported by either, and the fixture stays balanced. The SAFE twins are
the shapes a careless version would flag: a rem in a redirected (not piped) block, a
comment hoisted above a piped block, `||` on either side of a block, a line-leading
`@rem` whose ')' was never meant to close anything, an inline rem at top level, an
inline rem whose parens are its own, and a quoted "& rem".

Run:  python tests/test_rem_regression.py
Exit: 0 = pass, 1 = a detection regression or a new false positive.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYZER = HERE.parent / "scripts" / "analyze_batch.py"
FIXTURE = HERE / "rem_regression.cmd"


def lines_with(text, token):
    """1-based numbers of the lines holding `token` - rem lines included, since a rem is
    what is under test - skipping only the `rem ---` section headers."""
    return {i for i, ln in enumerate(text.splitlines(), 1)
            if token in ln and not ln.lstrip().lower().startswith(("rem ---", "rem ==="))}


def main():
    for p in (ANALYZER, FIXTURE):
        if not p.exists():
            print(f"FAIL: missing {p}")
            return 1
    text = FIXTURE.read_bytes().decode("ascii")
    out = subprocess.run([sys.executable, str(ANALYZER), str(FIXTURE), "--json"],
                         capture_output=True, text=True)
    findings = json.loads(out.stdout)[str(FIXTURE)]["findings"]
    got_eat = {f["line"] for f in findings if f["code"] == "rem-eats-paren"}
    got_pipe = {f["line"] for f in findings if f["code"] == "rem-in-piped-block"}
    unbalanced = [f for f in findings if f["code"] == "paren-unbalanced"]
    exp_eat = lines_with(text, "MUSTEAT")
    exp_pipe = lines_with(text, "MUSTPIPE")
    safe = lines_with(text, "SAFE:")

    problems = []
    if len(exp_eat) < 2 or len(exp_pipe) < 4 or len(safe) < 8:
        problems.append(f"fixture lost cases: {len(exp_eat)} EAT, {len(exp_pipe)} PIPE, {len(safe)} SAFE")
    for name, got, exp in (("rem-eats-paren", got_eat, exp_eat),
                           ("rem-in-piped-block", got_pipe, exp_pipe)):
        if exp - got:
            problems.append(f"{name}: NOT flagged (blind spot reopened): {sorted(exp - got)}")
        if got - exp:
            problems.append(f"{name}: falsely flagged (new false positive): {sorted(got - exp)}")
    if unbalanced:
        problems.append("the fixture reads as paren-unbalanced - a rem-eaten ')' is being "
                        "counted differently from how cmd counts it")
    if not problems:
        print(f"PASS  rem-eats-paren={sorted(got_eat)}  rem-in-piped-block={sorted(got_pipe)}  "
              f"({len(safe)} safe cases held clean, file balanced)")
        return 0
    print("FAIL")
    for p in problems:
        print("  -", p)
    return 1


if __name__ == "__main__":
    sys.exit(main())

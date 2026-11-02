#!/usr/bin/env python3
"""
extract_ps.py - pull embedded PowerShell one-liners out of a .cmd/.bat file and
run a fast static lint on each.

Large batch tools tend to shell out to PowerShell for anything cmd can't do
cleanly (registry work, timestamps, web requests, .NET calls). Those one-liners
live inside cmd quoting, so they're easy to break and hard to see. This script
finds every `powershell ... -Command "..."` / `pwsh ... -Command "..."` and
checks bracket and quote balance as a first pass.

It is intentionally lint-only and dependency-free so it runs anywhere. For a
real parse check, feed the same file to Validate-Embedded.ps1 under an actual
PowerShell interpreter (see setup_pwsh.sh if pwsh isn't installed).

Usage:
    python extract_ps.py FILE [--json] [--show]
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Matches:  powershell [flags] -Command "....."   (also pwsh, -c, /c)
# Captures the double-quoted command body, treating \" as an escaped quote so a
# command containing \"literal quotes\" isn't truncated mid-string. Batch
# one-liners keep the whole command on one logical line, which is what these
# scripts do.
INVOKE_RE = re.compile(
    r'(?i)\b(?:powershell|pwsh)\b[^"\r\n]*?\s(?:-Command|-c|/c)\s+"((?:[^"\\]|\\.)*)"')


def balance(s):
    """Return dict of bracket balance, ignoring single-quoted spans (PowerShell
    single quotes don't interpret their contents)."""
    stripped = re.sub(r"'[^']*'", "", s)
    return {
        "()": (stripped.count("("), stripped.count(")")),
        "{}": (stripped.count("{"), stripped.count("}")),
        "[]": (stripped.count("["), stripped.count("]")),
        "single_quotes_even": s.count("'") % 2 == 0,
    }


def lint_snippet(code):
    b = balance(code)
    problems = []
    for pair, (o, c) in (("()", b["()"]), ("{}", b["{}"]), ("[]", b["[]"])):
        if o != c:
            problems.append(f"unbalanced {pair}: {o} open vs {c} close")
    if not b["single_quotes_even"]:
        problems.append("odd number of single quotes")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--show", action="store_true",
                    help="print each snippet body")
    args = ap.parse_args()

    text = Path(args.file).read_text(encoding="utf-8", errors="replace")
    # Track line numbers by searching line-by-line offsets.
    results = []
    for m in INVOKE_RE.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        code = m.group(1)
        results.append({
            "line": line,
            "length": len(code),
            "problems": lint_snippet(code),
            "snippet": code if args.show else None,
        })

    bad = sum(1 for r in results if r["problems"])
    if args.json:
        print(json.dumps({"count": len(results), "with_problems": bad,
                          "snippets": results}, indent=2))
    else:
        print(f"Found {len(results)} embedded PowerShell command(s), "
              f"{bad} with static-lint problems.\n")
        for r in results:
            status = "OK " if not r["problems"] else "BAD"
            print(f"  [{status}] L{r['line']}  ({r['length']} chars)")
            for p in r["problems"]:
                print(f"          - {p}")
            if args.show and r["snippet"] is not None:
                print(f"          | {r['snippet'][:160]}"
                      + ("..." if len(r['snippet']) > 160 else ""))
        if not results:
            print("  (no embedded PowerShell found)")

    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

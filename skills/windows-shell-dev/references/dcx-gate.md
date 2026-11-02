# DCX neo port-sync gate (`scripts/extract_baseline.py`)

Project-specific: read this when the work touches DCX neo's `DCX.bat` or its `dcx-py` port.
[SKILL.md](../SKILL.md) carries the rule and the two commands; this file is the rest.

Applies only to DCX neo (`DCX.bat` + the `dcx-py` Python port). Any change to `DCX.bat`
MUST be followed by re-running the extractor, or the port's golden/parity suite silently
drifts from the batch:

```
cp <new DCX.bat> <dcx-py>/reference/DCX.bat
python "<skill folder>/scripts/extract_baseline.py" --repo <dcx-py>
```

`<skill folder>` is the folder of this skill: the same path the commands in SKILL.md already
show (this file is read as plain text, so no path is filled in here). Run the command from the
project, not from the skill folder.

Exit 0 prints a `gate green` summary; exit 1 lists UNMAPPED adb lines and structural
failures (SurfaceFlinger review-table drift, missing backup-capture keys, missing feature
streams). Never hand-edit `dcx/data/` - regenerate and commit. The generated `.py` files
carry the source sha256 and are byte-deterministic; `baseline.json` differs only in its
`generated` timestamp. This copy lives in the skill because the sandbox filesystem resets
between sessions; the canonical home is `tools/extract_baseline.py` in the `dcx-py` checkout -
keep the two in sync when the tool changes (bump `EXTRACTOR_VERSION`).

Per-feature gate rows live in `gate_expectations.json`, not in the script, resolved from the
checkout's `tools/`, then the copy **next to the script** (the one in `scripts/` here), then a
built-in Tier-1 fallback that says so loudly. Keep the rows in this skill: only the skill
survives a sandbox reset, and rows that live solely in a delivered zip are missing next
session while the gate still prints `gate green` and checks less than it claims. When `DCX.bat` grows a feature, add its
row in the same pass and re-ship the skill; the author uploads it and never hand-edits rows.

**A red gate is not automatically a broken script, and a green one is not a complete
check.** Both happened in one pass: two rows had gone stale because the *code improved past
them* (a value moved behind device-side single-quoting so adb stopped stripping it; a `put`
migrated to a new label in a refactor), so the gate was red while the script was fine -
while the backup counter knew three capture helpers and the project had grown two more, so
it reported 60 targets where the README correctly said 62, and deleting either capture would
have failed to fail. Before editing a row, work out which case you have: run the extractor,
read the `coverage_report.txt` line for that label, and take the token stream from the
report rather than retyping it. One sharp edge: a stream ends at the *next label*, internal
jump targets included, so a command after an internal `:_` label belongs to that label - the
same routine-boundary distinction sincript's `Get-RoutineBody` needed.

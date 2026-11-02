---
name: windows-shell-dev
description: "Author, debug, and extend large Windows batch/cmd scripts (.bat, .cmd) with embedded PowerShell: menu tools, tweakers, ADB/registry front-ends, installers. Use for a sizable .cmd/.bat, a batch project zip, delayed expansion, goto/label bugs, CRLF-safe edits, embedded PowerShell one-liners, or a PowerShell test harness - even «fix my script», «debug my .bat», «add a feature to my tool». Bundled scripts for static analysis, byte-safe editing, and real-parser validation."
---

# Windows shell development (batch/cmd + embedded PowerShell)

This skill is for **large, interactive Windows batch scripts**: hundreds or thousands of
lines, a menu, PowerShell for the hard parts, maintained over many versions. At that size
the failure mode is not a compile error; it is a bug that hides on one menu path and fires
*after* a side effect already happened. Everything below exists to surface those first.

Two things make the domain unforgiving:

- **cmd's parser is quirky.** Delayed expansion, redirects, parentheses and quoting all
  fail silently. The [pitfall catalog](references/pitfalls.md) is the collected list.
- **The file's bytes matter.** CRLF, no BOM and (usually) pure ASCII are load-bearing; an
  editor that "cleans up" the file can break a `goto` with no visible change.

## When this applies

Any sizable `.cmd`/`.bat`: optimizers, tweakers, ADB/registry front-ends, installers, menu
tools; the PowerShell embedded in them; any `tests\Run-Tests.ps1`-style harness. If the user
hands over a batch project (often a zip with a README), start here.

**Calling the bundled scripts.** They live in this skill's folder, not in the user's project,
so a bare command typed in the project folder misses them. DSH prints that folder when the
skill loads (`Base directory for this skill: <path>`), and the commands below use paths
relative to it (`python scripts/analyze_batch.py`). Resolve them against the base directory
and run from the project folder while you edit it. Every command is one line: PowerShell 5.1
has no `&&` and no `||` (both are parse errors), and a trailing `\` does not continue a line
(`Missing expression after unary operator '--'`; PowerShell's continuation character is the
backtick). Use `python`, never `python3` (on Windows `python3` is often a Microsoft Store stub
that prints nothing useful).

**The DSH shell is Windows PowerShell 5.1, not Git Bash.** Verified 2026-11-02 on this
machine: `python` in PATH is 3.14.7 and `python3` is the Store stub; captured `python` output
is cp1251, so add `-X utf8` when its text matters. `>` writes UTF-16LE with a BOM and
`Set-Content -Encoding utf8` writes UTF-8 with a BOM, so neither may touch a shipped text
file - `scripts/crlf_edit.py` preserves the bytes. `2>&1` on a native command raises
NativeCommandError. PowerShell embedded in a batch is 5.1 too: no `Join-String`, no ternary
`? :` and no `??`.

---

## The non-negotiables

Each habit prevents a specific, painful failure.

**Preserve the bytes.** Line endings (CRLF), BOM state (none) and the file's *existing*
encoding must come out identical. Projects differ - one script is ASCII-pure, another
uses UTF-8 box-drawing and emoji on purpose - so the rule is "change nothing you weren't
asked to", never "normalise". LF endings can make `goto` miss a label; a leading BOM
corrupts the first line. Edit through `scripts/crlf_edit.py` or Python opened with
`newline=""`, never through anything that rewrites line endings. See
[Editing safely](#editing-safely).

**Validate after every edit.** Run `scripts/analyze_batch.py` after each change: a rename
that fixes one `goto` can dangle another, and catching it one edit later is cheap. It exits
nonzero on real breakage, so it doubles as a pre-ship gate.

**Match the script's conventions exactly.** Learn its idioms first - ANSI colour variables,
`choice /c YN` confirmations, label naming, menu structure - and make new code
indistinguishable from what is there. Consistency keeps a 4000-line script maintainable;
clever deviations are noise the author has to decode.

**Prefer flat, label-based flow over deep nesting.** Batch punishes deep `( )` nesting
(the errorlevel and paren pitfalls). Intermediate labels (`:menu_ask`, `:menu_confirm`) are
clearer and avoid re-running slow probes. When a block gets awkward, split it.

**A backup that a second run overwrites is not a backup.** Re-running after an update is a
feature of these tools, so an action must never copy the current file over the pristine one
it saved last time. Keep the beside-the-file copy **write-once**, put the per-run snapshot
somewhere randomized, and make restore prefer the pristine copy. The registry side usually
has this via an idempotent skip; the file side is where it gets forgotten. Pitfall 24.

**Keep features opt-in, reversible and idempotent.** Write a backup before a registry flip
(a UTF-16 `.reg` of the prior state), set absolute values on "on", delete the keys on "off",
and make a second run change nothing.

**Be honest about what does something.** In comments and docs: say when a tweak is placebo
or OEM-dependent, add nothing you can't justify, and don't let existing comments overstate.
In output: never print an unconditional `[OK]`. Count failures in `_FAILS` (propagated across
`endlocal`), print `[FAIL]` inline at the failing write, end every gated action through one
shared `:Summary` that branches `[OK]`/`[WARN]`, and gate on elevation (`_ELEV`) so a
non-admin run says so. Pitfall 18 has the pattern.

**A long operation must say it is long, and show it is alive.** Batch cannot poll for a key
mid-command, so a screen that sits blank for ten seconds reads as a hang, and users kill it.
Say roughly how long and that input is not accepted, then emit step markers. Inside a
`( … ) > file` block plain `echo` goes into the file; `1>CON` reaches the console without
polluting the redirect:

```bat
(
    echo    [2/6] memory and storage... 1>CON
    echo [Memory]
    ...
) > "%REPORT%" < nul
```

If there is no abort, say so rather than implying one. Where a user could feel trapped, put
the way out in the *window title*: it survives every page of a pager, an echoed hint scrolls
away. The pager is not yours - `more.com` takes only its own keys (SPACE, ENTER, Q), so a
`0`/`Q` convention from your menu means nothing one level down, and "your quit key doesn't
work" is a fair report.

**A question must fit on one line.** cmd places the `set /p` caret at *(prompt length mod
console width)*, so a prompt longer than the line puts the caret **inside the question** and
the first keystroke overwrites the text being read. If the script sets `mode con: cols=N`,
that N is the limit; `analyze_batch.py` reads it from the script and enforces it
(`prompt-width`). Put the explanation on an `echo` line above and keep the question short;
the parenthetical that pushed it over is usually the part most worth a full line. Pitfall 52.

---

## Trust these over your memory

Each of these has been gotten wrong with this skill loaded, because the wrong version is
what a model already believes. When instinct disagrees with a line here, the line is right.

- **Duplicate labels: cmd does not jump to the first one.** `goto :x` and `call :x` search
  forward from the jump and wrap at the end of the file, so which copy runs depends on
  where the jump sits (pitfall 10). "Jumps to the first matching label" is the myth.
- **`powercfg` scheme aliases are named for power *savings*.** `SCHEME_MIN` is High
  performance, `8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c`; `SCHEME_MAX` is Power saver,
  `a1841308-3541-4fab-bc81-f71556f20b4a`; `SCHEME_BALANCED` is Balanced,
  `381b4222-f694-41f0-9685-ff5bb260df2e` (pitfall 26). Code pairing `SCHEME_MIN` with
  `8c5e7fda-...` is correct - leave it. Check any other pairing with `powercfg /aliases`.
- **A README pasted into the prompt is one more copy of the script's lists.** When a fix
  touches an accepted-value list (modes, options, keys), write the validator's list and
  every copy's list side by side in the reply - help line, error message, README table,
  example config, pasted or on disk - and name what each is missing (pitfall 28). No copy
  is "fine" before that comparison is written down.
- **`if COND a & b` runs both commands or neither.** The `&` belongs to the `if`, as does
  a `|` (pitfall 31). Folklore says the second command always runs; "fixing" a correct
  one-liner on that belief is how the bug gets introduced.
- **A caret escapes nothing inside double quotes.** `echo "skip ^(not installed^)"` prints
  its carets, and `^|` inside a quoted PowerShell `-Command` string reaches PowerShell as a
  stray argument - this catalog's pitfall 14 example did exactly that until it was measured
  (pitfall 32). Carets are for operators cmd can see.
- **Nothing ends a `rem` but the end of the line.** Not `&`, not `|`, not `)`:
  `echo a & rem note & echo b` never prints `b`, an inline `rem` in a block eats the
  block's `)`, and a `rem` anywhere in a piped block leaves the whole block unrun
  (pitfall 54). It is `echo` whose text stops at a separator; pitfall 27 had the two swapped
  until it was measured.

---

## The workflow

A debug-and-extend pass runs in this order. It is a loop, and the order matters because
each step de-risks the next.

**1. Read before touching.** Read the README, skim the script top to bottom for structure
and idioms, and list the labels for a map:

```powershell
Select-String -Path script.cmd -Pattern '^:[^:]'   # labels, not :: comments
```

From a zip: extract, then check the main file's size and line endings before anything else.

**2. Baseline the analyzer** on the untouched file, so you know what was there versus what
you introduce:

```powershell
python scripts/analyze_batch.py script.cmd
python scripts/menuscan.py script.cmd
```

ERRORs first (provably broken), then WARNs (known bug patterns), then INFO; look up anything
unfamiliar in the [catalog](references/pitfalls.md). The analyzer's block-paren machinery is
a character-level simulation of cmd's parser (quotes protect, `^` escapes, `(` opens only at
a command position, cross-line depth), and the whole tool is calibrated on two production
scripts (~12,700 lines combined at the time, ~17,600 today) to zero false positives - so
treat ERRORs as real until proven otherwise, and take WARNs seriously even in code that "has always worked": the calibration
pass found a live block-parse bug in one of the calibration scripts themselves.

**3. Fix bugs, smallest safe edits first.** Each fix is an exact-match replacement through
`crlf_edit.py` (it cannot silently no-op or hit the wrong place), then the analyzer again.
Understand the root cause from the catalog first: a fix you don't understand papers over the
symptom and moves the bug.

**4. Add the feature (if asked), in the house style.** Same colour variables, confirmation
pattern and label style, wired into the menu like the other options. Opt-in, reversible,
backup written first.

**5. Re-validate.** `analyze_batch.py` (zero ERRORs; understand any WARN) and `menuscan.py`
again; embedded PowerShell per [Embedded PowerShell](#embedded-powershell); the test harness
if there is one.

**6. Package and document.** Preserve bytes in the zip, update the README, write a short
CHANGES note. See [Deliverables](#deliverables).

---

## Editing safely

`scripts/crlf_edit.py` reads with line endings intact, refuses a replacement that does not
match exactly once, and writes back byte-faithfully.

From a one-off Python edit script (best for multi-line blocks). The module sits in the
skill folder, so the script puts that folder on `sys.path` first (write the edit script to a
file and run it with `python`; do not paste it into `python -c`):

```python
import sys
SKILL = r"<base directory for this skill>"   # from "Base directory for this skill: <path>"
sys.path.insert(0, SKILL + r"\scripts")
from crlf_edit import read, write, replace_exact, to_newline
text, meta = read("script.cmd")
# to_newline gives a block typed with LF the file's own line ending (CRLF)
text = replace_exact(text, to_newline(OLD_BLOCK, meta.newline),
                     to_newline(NEW_BLOCK, meta.newline))   # raises unless exactly 1 match
write("script.cmd", text, meta)                    # CRLF/BOM/encoding preserved
```

Or from the shell:

```powershell
python scripts/crlf_edit.py report script.cmd     # EOL/encoding/BOM
python scripts/crlf_edit.py replace script.cmd --old-file old.txt --new-file new.txt
```

`replace` reads `--old-file`/`--new-file` as bytes and gives both the file's line ending, so
an LF-written `old.txt` still matches a multi-line block of a CRLF file and `new.txt` never
puts bare LF into it. It exits 1 and leaves the file alone when nothing would change or the
edit would add lone LF endings. If the anchor is not unique the tool says so; widen or narrow
it rather than forcing the edit.

**This applies to every file the project ships.** Preset files, `.config` inputs, bundled
`hosts` lists and sample data are read on the same Windows box and carry the same
CRLF/BOM/ASCII expectations. Guarding the script religiously and then hand-editing the small
text file next to it with a literal `\n` is exactly how a preset file picks up two lone-LF
endings nothing notices. Run `crlf_edit.py report` on every file you touched, and have the
harness check their bytes too.

---

## Embedded PowerShell

Batch tools shell out to PowerShell for registry work, timestamps, web requests and .NET
calls. Those one-liners live inside cmd quoting, so they break easily and hide in plain
sight. Validate in two passes:

```powershell
python scripts/extract_ps.py script.cmd --show    # fast static lint: bracket/quote balance
```

**On Windows** (the normal case) nothing needs installing: Windows PowerShell 5.1,
`powershell.exe`, is built in and runs the validator. `-ExecutionPolicy Bypass` applies to
this one process only; without it a default Windows refuses to run a `.ps1`.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Validate-Embedded.ps1 -CmdFile script.cmd -Harness tests\Run-Tests.ps1 -RunHarness
```

Exit codes: 0 valid, 1 a snippet or the harness is bad, 2 a named file does not exist. A line
`WARNING: no embedded PowerShell found` means nothing was parsed (the file has none, or its
`-Command` body is not written in double quotes) - it is not a pass. Inside a snippet `\"` is
read as a quote, the way `powershell.exe` reads its command line. When its output goes to a
pipe (the DSH `pwsh` tool) the script writes UTF-8, so the parser's localized
messages stay readable; the console encoding is restored on exit.

**On Linux** (a sandbox with no `pwsh`; not the DSH path on Windows, and not verified there)
install the Linux build first. The script refuses on Windows and macOS (it installs a Linux
binary into `/opt/pwsh`):

```bash
bash scripts/setup_pwsh.sh    # Linux only; idempotent; installs to /opt/pwsh
/opt/pwsh/pwsh -NoProfile -File scripts/Validate-Embedded.ps1 -CmdFile script.cmd -Harness tests\Run-Tests.ps1 -RunHarness
```

Only PowerShell's own parser proves a one-liner valid; the second pass is the real check.

Three conventions that prevent whole bug classes:

- **Never round-trip non-ASCII data through cmd.** Pass values to the worker in environment
  variables and do the string work in .NET: the console code page mangles non-ASCII at the
  cmd boundary, and literal-safe .NET calls avoid wildcard and `!` misfires on odd names.
- **Gate downloads on the exit code, not file existence.** A partial file still exists;
  check the exit code and delete leftovers first (pitfall 9).
- **Read the registry; never parse a tool's human-readable output.** `powercfg /query`,
  `sc query`, `net`, `tasklist` headers are localized. A parser built on their English
  wording captures *nothing* on a translated Windows and fails silently, returning an empty
  result that reads as "nothing to do". Registry value names, GUIDs and numbers are the same
  in every locale. Pitfall 26.

**Watch what `Add-Type` costs.** `Add-Type -TypeDefinition ... -Language CSharp` spawns the
C# compiler: one to two-and-a-half seconds cold, dwarfing the P/Invoke it was for. Fine
behind a menu item, not on a startup path - a header that draws on launch pays it every run.
The fix is rarely a faster detector (the fast ones are usually the unreliable ones you
avoided on purpose); run the trusted probe **once per machine** and cache the answer, keyed
on something that changes when the hardware does, so the cache invalidates itself. Never
cache a failed probe: one bad run would become permanent.

---

## Testing and the harness

Projects at this scale benefit from a static harness (often `tests\Run-Tests.ps1`,
dependency-free, stock PowerShell 5.1) that asserts invariants: every label resolves, key
settings round-trip, presets are valid, status reporting stays honest. `analyze_batch.py`
is the batch-side half of that harness: it ports the structural checks and adds the
cmd-specific lints. A mature one (the reference guards well over a hundred invariants)
converges on these patterns:

- **Helpers, not frameworks.** `Invoke-Test 'name' { ... }` with
  `Assert-True $cond 'message'`, plus `Read-Lines` and `Get-RoutineBody -Label 'X'` to
  pull one `:label` routine's body. When an action spans sub-labels, scan from the top-level `:Label` to the
  next top-level label (skipping those starting with `_`).
- **Parse facts out of the script; don't hard-code them.** "The validator recognises keys
  A,B,C" drifts; a test that *extracts* the recognised set from the validator and checks the
  example preset against it tracks the script forever.
- **Guard behaviours, not line numbers.** "`:CreateRegBackup` has an `[ERROR]` branch before
  its `[OK]`", not "line 812 says X".
- **Assert against code, never prose.** A static test greps text, and a well-commented
  script talks *about* the thing under test. `-notmatch 'setx'` fails because a banner
  explains that setx is avoided - annoying but visible. The dangerous direction:
  `-match 'Get-ScheduledTask'` **passes with the implementation deleted**, because the
  routine's comment names the cmdlet. The same bites `IndexOf(a) -lt IndexOf(b)` ordering
  checks, more confusingly: a comment mentioning the command hands you the comment's index,
  and the test fails on correct code - a routine explaining *why it avoids* something is the
  classic case. Strip comments and echoes first, for matching and for positions alike:

  ```powershell
  $code = @($body | Where-Object { $_.Trim() -notmatch '^(?i)(echo|rem)\b' }) -join "`n"
  ```

  A prose-satisfied positive assertion is green forever and guards nothing.
- **A declaration is not a call.** `-match 'DeviceIoControl'` passes while the extern
  signature exists, even if nothing invokes it - the P/Invoke block names every API it
  imports (same for `SendMessageTimeout`, `RmGetList`). Assert the invocation form
  (`[Type]::Method\(`), never the bare name. This bit three tests across two sessions, twice
  *after* the rule above was written down; mutation testing caught it every time, reading
  never did.
- **Pin the polarity of anything that maps a fact to advice.** Proving a probe *runs* says
  nothing about whether it maps the answer the right way round; inverted, it gives
  confidently backwards guidance - worse than "unknown". Assert the mapping.
- **Pin the branch you rely on, not the existence of *a* branch.** `-match '"%VAR%"=='`
  stays true while any comparison on `VAR` survives, so deleting the specific early return
  slips through. Assert the exact branch.
- **Helpers that `return ,$array` do not survive a pipeline - assign first, always.** The
  comma operator defeats unrolling, so any pipeline fed by the call itself receives the
  array as **one object**; `-join` then stringifies it to the literal `System.String[]`,
  every `-match` reads garbage and every `-notmatch` passes vacuously:

  ```powershell
  $b = Get-RoutineBody -Label 'X'; $b | Where-Object {...}   # fine - assignment unwraps
  Get-RoutineBody -Label 'X' | Where-Object {...}            # BROKEN - one String[] in
  @('A','B') | ForEach-Object { Get-RoutineBody -Label $_ }  # BROKEN - String[] each
  ```

  Assign to a variable first, or concatenate:
  `(Get-RoutineBody ...) + (Get-RoutineBody ...)`. Four tests across four sessions; the rule is *assign first*, not "remember which
  shapes are safe".
- **Pair every `-notmatch` with proof the haystack is real.** A negative assertion passes on
  an empty string, a stringified array or a typo'd routine name - the three commonest ways a
  test dies quietly. One `Assert-True ($body.Length -gt 0)` in front makes the vacuous pass a
  failure that names itself.
- **A sub-label that doesn't start with `_` ends the routine body.** `Get-RoutineBody`
  stops at the next real entry point, so a routine whose work lives past `:Foo_ask` or
  `:OA_HaveSrc` gives a stub, and the test fails bewilderingly or passes on almost nothing.
  Concatenate the pieces
  (`@(Get-RoutineBody -Label 'Foo') + @(Get-RoutineBody -Label 'Foo_ask')`) and say why in
  a comment, or the next person "simplifies" it back.
- **You cannot drive an interactive script by piping stdin to it.** `pause` drains the
  redirected stream, so the run sails past the first prompt and every later `set /p`
  returns instantly at EOF - which looks exactly like the menu bug you were reproducing.
  Extract the routine into a driver instead: pull `:the_menu` through to the next real label,
  stub its jump targets and `cls` with echo markers, feed *that* a keystroke list, and count
  redraws. That proved both halves of one fix: the pre-fix shape spun forever and was killed
  at 60 s; the fixed one drew once and exited on the first key.
- **One `[PASS]`/`[FAIL]` line per test, exit code 0/1**, so the harness drops into any CI
  or pre-ship check.

Invariants worth guarding in any project of this shape - each regresses silently and none
shows in a diff:

- **The bytes of every shipped text file** (ASCII/CRLF/no BOM). `analyze_batch.py` checks
  them, but it is a dev-machine tool; the PowerShell harness runs on the target box. Loop
  over the files and assert how many you checked, so a broken path cannot shrink the scope.
- **Menu item ↔ dispatch parity.** Every key a menu prints has a branch, every branch has a
  printed key, and the numbers stay contiguous with the conditional rows on, off and each one
  alone: a row printed behind `if` is exactly how a menu comes to read 1 2 3 4 6. Renumbering
  is when this breaks, and an option that silently does nothing looks fine in source.
  `scripts/menuscan.py` checks `set /p` menus for all of it (it found that 4→6 skip on a real
  screen; `choice /c` menus and rows drawn by a `call`ed helper are outside its reach), so
  keep the harness's own parity test too, avoiding two assumptions: the dispatch does not
  always live in `:X_ask`, and the variable is not always the one you expect. Two conventions
  no scan can judge: which key is Back (`0` everywhere in one script, the last number in
  another - match the script), and that a feature belongs in one menu, never two.
- **No state change outside its wrapper.** If the project funnels registry writes (or
  service edits, file replacements) through one backed-up helper, assert that nothing calls
  the raw command elsewhere - including smuggled through a `:Run` helper. That line is where
  the backup, the honesty and the failure tally live, and bypassing it looks ordinary.

**Add a test for every fix or feature, and mutation-test the test:** re-break the code in a
throwaway copy and confirm the detector fires. A test green on both versions tests nothing.
Every trap above was found this way and by nothing else - each looked correct and passed on
good code. Mutate the *file under test*, not a neighbouring routine, or you prove nothing;
and after any edit re-check that the copy you mutate is byte-identical to the copy you
validated. Four ways a mutation lies:

- **It did not apply.** A wrong anchor - a backslash eaten by a shell, a quoting slip, a
  string that no longer matches - changes nothing, the harness passes, and it reads exactly
  like "the guard did not fire"; you then rewrite a test that was fine. One
  `assert text != before` in the mutation script makes it loud. Four mutations in one session
  no-opped this way before that assert went in.
- **It changed bytes, not the property.** Swapping two characters for two others leaves a
  width check passing, and it is right to.
- **It removed some instances, not all.** Deleting one of two lines that mention the thing
  leaves the assertion satisfied by the survivor. In both of these the test is correct and
  the mutation is the bug, so check the mutation before touching the test.
- **The flip side: the assertion is too weak.** A bare `-match` is satisfied by one
  occurrence, so deleting three of four octet checks, or routing one of five commands past
  its wrapper, stays green - real regressions. When a property appears N times, assert the
  count. A too-narrow mutation is your bug; a too-weak assertion is the test's. Decide which
  before touching anything.

**Measure cmd behaviour in cmd, and check the probe before believing it.** Several catalog
entries exist because a confident belief was wrong, so settle a doubt with a two-line probe
- and know how a probe lies:

- **A tool rewrote it.** A shell heredoc that collapses `\\` to `\` once turned `!v:\=\\!`
  into a no-op and the result looked like a new pitfall. Print the probe's bytes before
  trusting a surprising answer - the same rule as asserting a mutation applied.
- **The echo parsed what it printed.** `echo %~1` runs the value through one more parse, so
  the carets and `!` under measurement change on the way to the screen. Capture into a
  variable with delayed expansion off and print it with `set NAME` (pitfall 53 was nearly
  written up wrong this way).
- **The wrong `find`.** A cmd inherits the PATH of the process that started it: from Git Bash
  (no longer the DSH shell) that puts Git's `usr\bin` near the front, so `find` and `sort` are
  the GNU tools (`where find` lists `C:\Program Files\Git\usr\bin\find.exe` first), while from
  DSH's PowerShell 5.1 they resolve to `C:\Windows\System32\find.exe` and `sort.exe`. A test
  of `find /v ""` that measures the wrong program proves nothing, so run `where.exe find` in
  the same shell the cmd starts from and probe from a plain cmd window.
- **chcp ate the test's input.** `chcp` reads a redirected stdin to its end, so in a driver
  fed answers from a file every later `set /p` got nothing - which looks like a code-page
  bug. Give it its own `chcp 65001 >nul <nul`; `set /p` then reads the file fine at 65001. At
  a real console `chcp` leaves typed-ahead keys alone.
- **A stub swallowed control.** A `.cmd` standing in for a tool is not transparent: a script
  that runs `adb ...` without `call` jumps into the stub and never returns (pitfall 29).
  Inside `for /f ('...')` a stub is fine (a child runs it); everywhere else use a small
  compiled `.exe`, which returns like the real tool -
  `Add-Type -TypeDefinition $cs -OutputAssembly adb.exe -OutputType ConsoleApplication`
  builds one in a second. One that keeps state between calls (a setting written, then read
  back) and can refuse, silently ignore, or act as a dropped connection covers every branch
  of an honest-status check.

---

## The pitfall catalog

A pitfall lives in **three** places that move together: the row below, the entry in
[references/pitfalls.md](references/pitfalls.md), and that file's own `## Contents` index.
Appending an entry and forgetting the index is the easy mistake: the reference then
advertises fewer pitfalls than it holds, and the newest ones are invisible to anyone who
reads the index instead of scrolling - the same shape as changing a harness without changing
the harness's README.

The mechanical bugs are flagged by `analyze_batch.py`; the semantic ones are review rules.
Full symptom/cause/fix with before-and-after for each is in the reference - read it when a
finding needs context or when writing new code.

| # | Pitfall | Analyzer code | Severity |
|---|---------|---------------|----------|
| 1 | Delayed expansion eats `!` | `delayed-bang` | WARN |
| 2 | Redirect glued to a value (` 1>>`) | `redirect-var-glue` | WARN |
| 3 | Explicit `<nul` overrides a pipe | `pipe-nul-override` | WARN |
| 4 | Stale `set /p` re-runs the last choice | `setp-stale` / `setp-stale-confirms` | INFO |
| 5 | A lone quote in input kills the script | `quote-odd` | INFO |
| 6 | Bare parens inside ( ) blocks: crash and truncation | `block-early-close` / `block-paren-literal` / `paren-unbalanced` | ERROR / WARN |
| 7 | errorlevel captured inside a block | (review) | — |
| 8 | Non-idempotent powercfg / duplicate schemes | (review) | — |
| 9 | Download "succeeded" on a partial file | (review) | — |
| 10 | Broken goto/call targets and duplicate labels | `goto-undefined` / `call-undefined` / `label-duplicate` | ERROR |
| 11 | Line-ending and encoding damage | `eol-mixed` / `eol-lf` / `bom` / `eol-final` | ERROR / WARN / INFO |
| 12 | Quote-hostile and non-ASCII text through cmd | `non-ascii` (summary) | INFO |
| 13 | Unguarded expansion ops (`:~`, `:=`) on an empty variable — a plain undefined `%v%` just expands to nothing | (review) | — |
| 14 | ASCII sort picks the wrong "latest" version | (review) | — |
| 15 | reg.exe from PowerShell mangles quotes | (review) | — |
| 16 | `%RANDOM%` backup-name collisions | (review) | — |
| 17 | Generated .reg files: escape backslashes and quotes, never strip | (review) | — |
| 18 | Unconditional `[OK]` — dishonest status reporting | (review) | — |
| 19 | `setx` truncates PATH and flattens `REG_EXPAND_SZ` | (review) | — |
| 20 | A wrong identifier fails quietly — absent is not success | (review) | — |
| 21 | A CIM namespace is only as good as its worst provider | (review) | — |
| 22 | A backup that can't tell "unreadable" from "unset" is a deletion script | (review) | — |
| 23 | A caret followed by trailing whitespace is not a line continuation | `caret-trailing-ws` | WARN |
| 24 | A fixed-name backup is destroyed by the second run | (review) | — |
| 25 | A generated undo script must restore the important thing first | (review) | — |
| 26 | Localized command output is not a data source | (review) | — |
| 27 | Batch that writes batch — and `echo`'s other forms: emitted `goto`/`call` are data | (jump scan strips echo/rem text) | — |
| 28 | An accepted-value set stated in more than one place drifts — compare every copy item by item, a README pasted into the prompt included | (review) | — |
| 29 | Falling through into a `call`ed routine ends the script | `call-fallthrough` | ERROR |
| 30 | One level of quoting is stripped before a re-parsing child sees it | (review) | — |
| 31 | `&` and `\|` bind to a single-line `IF` | (review) | — |
| 32 | Caret-escaped operators outside a `for /f` clause become literal arguments | (review) | — |
| 33 | `::` comments inside a ( ) block | `comment-in-block` | WARN |
| 34 | `findstr /x` and `$` fail on LF-only input | (review) | — |
| 35 | A variable named like a dynamic one shadows it | (review) | — |
| 36 | A piped validator never sees the value it is validating | `pipe-validate` | ERROR |
| 37 | `goto` out of a `call`ed routine leaves the call stack one frame deep | (review) | — |
| 38 | Variable names are case-insensitive: two names differing only by case are one variable | `var-case-collision` | ERROR |
| 39 | `set /p` cannot tell EOF from Enter, so an unbounded input loop spins forever | (review) | — |
| 40 | `shift` renumbers `%0`, so `%~dp0` stops naming the script | `shift-selfpath` | ERROR |
| 41 | errorlevel is clobbered by the next command — and `del` always clears it | (review) | — |
| 42 | `set /a` is 32-bit signed: it saturates a variable but errors on a literal | (review) | — |
| 43 | A missing `for /f` token expands to empty, not to nothing | (review) | — |
| 44 | `2>nul` cannot suppress a failed redirection | (review) | — |
| 45 | A hidden PowerShell child that prompts hangs the parent forever | (review) | — |
| 46 | PowerShell 5.1 reads a UTF-8 `.ps1` without a BOM as ANSI | (review) | — |
| 47 | `cd` into a tool folder does not put it on PATH | (review) | — |
| 48 | A `for /f "delims=<allowed>"` validator passes anything after a `;` — give it an `eol=` that is one of the allowed characters | (review) | — |
| 49 | `choice` returns 0 on Ctrl+C, so an `if errorlevel 2` confirmation means Yes | (review) | — |
| 50 | `if errorlevel 1` is "1 or higher", so a negative exit code reads as success | (review) | — |
| 51 | `""` inside a helper's command string is not an escaped quote | (review) | — |
| 52 | A `set /p` prompt longer than the console line puts the caret inside the question | `prompt-width` | WARN |
| 53 | `call` parses its arguments a second time — `%` is consumed and quoted `^` doubled; hand values over by name, and let a child `cmd` expand them itself | `call-reparse` | WARN |
| 54 | An inline `rem` comments out the rest of the line — `&`, `\|` and a block's `)` included; a `rem` anywhere in a piped block leaves the whole block unrun | `rem-eats-paren` / `rem-in-piped-block` | ERROR |

---

## Bundled scripts

| Script | Purpose | Typical call |
|--------|---------|--------------|
| `scripts/analyze_batch.py` | Static analysis: labels, parens, delayed expansion, redirects, pipes, line endings. Run after every edit. | `python scripts/analyze_batch.py script.cmd [--strict] [--json]` |
| `scripts/menuscan.py` | Menu parity for `set /p` menus: keys printed vs keys dispatched, numbers contiguous with conditional rows on, off and each alone, keys shown twice, keys shown but never handled or handled but never shown. Exit 1 on findings; `-v` lists every menu checked; the docstring states the heuristics and their limits. | `python scripts/menuscan.py script.cmd [-v]` |
| `scripts/crlf_edit.py` | Byte-safe editing (CRLF/BOM/encoding preserved) with exact-match replacement. | `python scripts/crlf_edit.py report script.cmd` |
| `scripts/extract_ps.py` | Extract + statically lint embedded PowerShell one-liners. | `python scripts/extract_ps.py script.cmd --show` |
| `scripts/Validate-Embedded.ps1` | Real-parser validation of embedded PS + optional harness run. Runs in `powershell.exe` 5.1 on Windows. | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/Validate-Embedded.ps1 -CmdFile script.cmd` |
| `scripts/setup_pwsh.sh` | **Linux only** (refuses elsewhere): install PowerShell from the official tarball when absent. Not needed on Windows. | `bash scripts/setup_pwsh.sh` |
| `scripts/extract_baseline.py` | **DCX neo only** — port-sync gate: parses a `reference/DCX.bat`, regenerates `dcx/data/*.py` + `tests\golden\baseline.json` + `tools/coverage_report.txt`; exit 1 on any UNMAPPED adb line or review-table drift. | `python scripts/extract_baseline.py --repo <dcx-py checkout>` |

The Python scripts have no dependencies. `analyze_batch.py`, `menuscan.py` and
`Validate-Embedded.ps1` exit nonzero on real problems, so they compose into CI or a harness.
The `test_*.py` files in `tests` are the scripts' own regression guards - run them after
changing a script, each with `python` from any folder (they find the scripts next to
themselves), e.g. `python tests/test_setp_regression.py`. In the DSH sandbox
`test_promptwidth_regression.py` can stop with PermissionError when it writes its temporary
copy: writes inside `tempfile` directories are denied there (2026-11-02), so check its two
rules by hand on the fixture - the `mode con` lines are flagged, the copy without `mode con`
is silent - rather than treating the crash as a regression.

### Project gate: DCX neo port sync (`extract_baseline.py`)

Applies only to DCX neo (`DCX.bat` + the `dcx-py` Python port). Any change to `DCX.bat`
MUST be followed by re-running the extractor, or the port's golden/parity suite silently
drifts from the batch:

```
Copy-Item -LiteralPath '<new DCX.bat>' -Destination '<dcx-py>\reference\DCX.bat'
python scripts/extract_baseline.py --repo <dcx-py>
```

Before acting on the result, read [references/dcx-gate.md](references/dcx-gate.md): what a
red or a green gate does and does not prove, where the per-feature rows live
(`gate_expectations.json`, kept in this skill so they survive a sandbox reset), and the rule
that a new `DCX.bat` feature gets its row in the same pass. Never hand-edit `dcx/data/`.

---

## Deliverables

When wrapping up a batch project:

- **Preserve bytes in the archive.** Zip so the `.cmd` keeps its CRLF/ASCII/no-BOM form;
  verify with `crlf_edit.py report` after building if in doubt.
- **Update the README to match reality.** New menu rows, new behaviour, honest notes on what
  works versus placebo or OEM-dependent. Put a caveat where someone will *look* for it - a
  warning that exists only in the changelog is a warning nobody reads.
- **Recount every number and list the README states.** Test counts, capture counts, menu
  items: each is a copy of something in the code, and a change that moves the code leaves
  the copy behind (pitfall 28). Search the README for each count your change can move and
  recount it from the code - never carry the old number forward or add one to it. One pass
  found a stale "121 checks" in two places, a sub-menu listed twice with each copy missing a
  *different* one of its eight items, and "63 captures" that was one too many because the
  63rd grep hit was a helper's own label. If the README keeps a *Recent changes* section,
  the change goes in it.
- **Touch the harness, update the harness's README in the same pass.** If the project
  documents its tests (`tests\tests_README.md` or similar), a new or widened check needs its
  numbered entry and the total updated right then; the table is what makes the suite
  auditable and it goes stale within a session otherwise. Say what the check *caught*, not
  just what it asserts, so the next reader knows why it exists before weakening it.
- **Write a short CHANGES note.** One entry per bug (what was wrong, why, the fix) and one
  for the feature. This is what lets the author trust the diff.
- **Re-state validation.** Confirm the label count resolves and the analyzer is clean, so
  the user knows the structural invariants still hold.

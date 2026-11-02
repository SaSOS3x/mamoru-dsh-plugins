# Batch / cmd pitfall catalog

The bugs in this file share a personality: they stay invisible until a user
walks the one code path that triggers them, and they often fire *after* a side
effect has already happened (a file written, a registry key set), so the script
looks like it "half worked." Each entry gives the symptom, the root cause, how
`analyze_batch.py` flags it, and the fix — with a concrete before/after.

Read this when writing or reviewing a batch script; the analyzer catches the
mechanical ones, but understanding *why* each is wrong is what stops you
reintroducing them in new code.

## Contents

1. [Delayed expansion eats `!`](#1-delayed-expansion-eats-)
2. [Redirect glued to a value (` 1>>`)](#2-redirect-glued-to-a-value--1)
3. [Explicit `<nul` overrides a pipe](#3-explicit-nul-overrides-a-pipe)
4. [Stale `set /p` re-runs the last choice](#4-stale-set-p-re-runs-the-last-choice)
5. [A lone quote in input kills the script](#5-a-lone-quote-in-input-kills-the-script)
6. [Bare parens inside ( ) blocks: crash and truncation](#6-bare-parens-inside---blocks-crash-and-truncation)
7. [errorlevel captured inside a block](#7-errorlevel-captured-inside-a-block)
8. [Non-idempotent powercfg / duplicate schemes](#8-non-idempotent-powercfg--duplicate-schemes)
9. [Download "succeeded" on a partial file](#9-download-succeeded-on-a-partial-file)
10. [Broken goto/call targets and duplicate labels](#10-broken-gotocall-targets-and-duplicate-labels)
11. [Line-ending and encoding damage](#11-line-ending-and-encoding-damage)
12. [Quote-hostile and non-ASCII text through cmd](#12-quote-hostile-and-non-ascii-text-through-cmd)
13. [Unguarded expansion ops on an empty variable](#13-unguarded-expansion-ops-on-an-empty-variable)
14. [ASCII sort picks the wrong "latest" version](#14-ascii-sort-picks-the-wrong-latest-version)
15. [reg.exe from PowerShell mangles quotes](#15-regexe-from-powershell-mangles-quotes)
16. [`%RANDOM%` backup-name collisions](#16-random-backup-name-collisions)
17. [Generated .reg files: escape backslashes and quotes, never strip](#17-generated-reg-files-escape-backslashes-and-quotes-never-strip)
18. [Unconditional `[OK]` — dishonest status reporting](#18-unconditional-ok--dishonest-status-reporting)
19. [`setx` truncates PATH and flattens `REG_EXPAND_SZ`](#19-setx-truncates-path-and-flattens-reg_expand_sz)
20. [A wrong identifier fails quietly — absent is not success](#20-a-wrong-identifier-fails-quietly--absent-is-not-success)
21. [A CIM namespace is only as good as its worst provider](#21-a-cim-namespace-is-only-as-good-as-its-worst-provider)
22. [A backup that can't tell "unreadable" from "unset" is a deletion script](#22-a-backup-that-cant-tell-unreadable-from-unset-is-a-deletion-script)
23. [A caret followed by trailing whitespace is not a line continuation](#23-a-caret-followed-by-trailing-whitespace-is-not-a-line-continuation)
24. [A fixed-name backup is destroyed by the second run](#24-a-fixed-name-backup-is-destroyed-by-the-second-run)
25. [A generated undo script must restore the important thing first](#25-a-generated-undo-script-must-restore-the-important-thing-first)
26. [Localized command output is not a data source](#26-localized-command-output-is-not-a-data-source)
27. [Batch that writes batch — and `echo`'s other forms](#27-batch-that-writes-batch--and-echos-other-forms)
28. [An accepted-value set stated in more than one place drifts](#28-an-accepted-value-set-stated-in-more-than-one-place-drifts)
29. [Falling through into a `call`ed routine ends the script](#29-falling-through-into-a-called-routine-ends-the-script)
30. [One level of quoting is stripped before a re-parsing child sees it](#30-one-level-of-quoting-is-stripped-before-a-re-parsing-child-sees-it)
31. [`&` and `|` bind to a single-line `IF`](#31--and--bind-to-a-single-line-if)
32. [Caret-escaped operators outside a `for /f` clause become literal arguments](#32-caret-escaped-operators-outside-a-for-f-clause-become-literal-arguments)
33. [`::` comments inside a ( ) block](#33--comments-inside-a---block)
34. [`findstr /x` and `$` fail on LF-only input](#34-findstr-x-and--fail-on-lf-only-input)
35. [A variable named like a dynamic one shadows it](#35-a-variable-named-like-a-dynamic-one-shadows-it)
36. [A piped validator never sees the value it is validating](#36-a-piped-validator-never-sees-the-value-it-is-validating)
37. [`goto` out of a `call`ed routine leaves the call stack one frame deep](#37-goto-out-of-a-called-routine-leaves-the-call-stack-one-frame-deep)
38. [Variable names are case-insensitive: two names differing only by case are one variable](#38-variable-names-are-case-insensitive-two-names-differing-only-by-case-are-one-variable)
39. [`set /p` cannot tell EOF from Enter, so an unbounded input loop spins forever](#39-set-p-cannot-tell-eof-from-enter-so-an-unbounded-input-loop-spins-forever)
40. [`shift` renumbers `%0`, so `%~dp0` stops naming the script](#40-shift-renumbers-0-so-dp0-stops-naming-the-script)
41. [errorlevel is clobbered by the next command — and `del` always clears it](#41-errorlevel-is-clobbered-by-the-next-command--and-del-always-clears-it)
42. [`set /a` is 32-bit signed: it saturates a variable but errors on a literal](#42-set-a-is-32-bit-signed-it-saturates-a-variable-but-errors-on-a-literal)
43. [A missing `for /f` token expands to empty, not to nothing](#43-a-missing-for-f-token-expands-to-empty-not-to-nothing)
44. [`2>nul` cannot suppress a failed redirection](#44-2nul-cannot-suppress-a-failed-redirection)
45. [A hidden PowerShell child that prompts hangs the parent forever](#45-a-hidden-powershell-child-that-prompts-hangs-the-parent-forever)
46. [PowerShell 5.1 reads a UTF-8 `.ps1` without a BOM as ANSI](#46-powershell-51-reads-a-utf-8-ps1-without-a-bom-as-ansi)
47. [`cd` into a tool folder does not put it on PATH](#47-cd-into-a-tool-folder-does-not-put-it-on-path)
48. [A `for /f "delims=<allowed>"` validator passes anything after a `;`](#48-a-for-f-delimsallowed-validator-passes-anything-after-a-)
49. [`choice` returns 0 on Ctrl+C, so an `if errorlevel 2` confirmation means Yes](#49-choice-returns-0-on-ctrlc-so-an-if-errorlevel-2-confirmation-means-yes)
50. [`if errorlevel 1` is "1 or higher", so a negative exit code reads as success](#50-if-errorlevel-1-is-1-or-higher-so-a-negative-exit-code-reads-as-success)
51. [`""` inside a helper's command string is not an escaped quote](#51--inside-a-helpers-command-string-is-not-an-escaped-quote)
52. [A `set /p` prompt longer than the console line puts the caret inside the question](#52-a-set-p-prompt-longer-than-the-console-line-puts-the-caret-inside-the-question)
53. [`call` parses its arguments a second time](#53-call-parses-its-arguments-a-second-time)
54. [An inline `rem` comments out the rest of the line — `&`, `|` and a block's `)` included](#54-an-inline-rem-comments-out-the-rest-of-the-line----and-a-blocks--included)

---


## 1. Delayed expansion eats `!`

**Symptom.** Text with an exclamation mark prints wrong: `[!] ADB not found!` shows
as a bare `[`, and a diagnostic like `mState != IDLE` prints as `mState = IDLE`
— which silently *inverts* the meaning of the check you're showing the user.

**Cause.** Under `setlocal enabledelayedexpansion`, `!` is the delayed-expansion
sigil. cmd tries to expand `!whatever!` and consumes the `!` characters (and
whatever it thinks is between them). This happens in `echo`, in `set`, anywhere
the line is parsed with delayed expansion active.

**Detection.** `delayed-bang` (WARN) flags a literal `!` in echoed text when the
file enables delayed expansion anywhere. Real references are ignored, including
pseudo-arrays and substring/substitution forms (`!_nm[%%I]!`, `!_sst[%sel%]!`,
`!_p4:~0,58!`, `!_hx:~-8!`), as are already-escaped `^!`/`^^!`. Note quotes do
NOT protect `!` — delayed expansion fires inside quoted text too.

**Fix.** Escape a literal `!` as `^^!` inside a delayed-expansion block (the
double caret survives both the normal and the delayed parse pass); outside such
blocks a single `!` is fine. Inside double quotes the normal pass leaves carets
alone, so there it is a single `^!` — `echo "done^^!"` prints `"done^"`.

```bat
:: before  (prints "mState = IDLE" - meaning flipped!)
echo    mState != IDLE  means the device is awake

:: after
echo    mState ^^!= IDLE  means the device is awake
```

**The same rule bites when you *capture* a value, and there it corrupts data rather than
display.** A `for /f` that reads a value into a variable eats any `!` the value contains —
and if that value is on its way into a generated backup, the shortened text is what gets
written, and what a later restore puts back over the real setting. Escaping is no help
here: the text comes from outside the script, so there is nothing to pre-escape.

```bat
:: device holds  Hi!There!

:: before - _val ends up as "Hi", and the backup records that
setlocal enabledelayedexpansion
for /f "delims=" %%v in ('adb shell settings get global key') do set "_val=%%v"

:: after - read with delayed expansion OFF, switch it on for the manipulation
setlocal DisableDelayedExpansion
for /f "delims=" %%v in ('adb shell settings get global key') do set "_val=%%v"
setlocal EnableDelayedExpansion
:: ...use !_val! here; endlocal twice, or let exit /b pop both scopes
```

Worth knowing how rare it is before you spend effort on it: a scan of all three Android
settings namespaces on a real device (1297 keys) found **zero** values containing `!`. The
bug is real and the fix is cheap, but it is a correctness backstop, not a live fire.

**A second hop re-opens it.** Capturing the value safely once is not the end of it. *Any*
`set "X=%%v"` that runs with delayed expansion on re-expands a `!` the FOR variable carries,
because the FOR variable is substituted before the delayed pass. The usual culprits are small
tidy-up copies of a value you already hold: dropping a trailing CR with
`for /f "delims=" %%v in ("!X!") do set "X=%%v"`, or keeping only its first token. Measured in
DCX: a package name `com.odd!USERNAME!x`, captured correctly, came out of such a CR-strip as the
PC user's name. Do the copy with delayed expansion off as well. Inside a loop body that works
per iteration, while the `for` line itself, parsed with it still on, can use `!LIST!`:

```bat
for /f "usebackq tokens=1,* delims=:" %%a in ("!LIST!") do (
    setlocal DisableDelayedExpansion
    set "_v="
    for /f "delims=" %%v in ("%%b") do set "_v=%%v"
    call :check_v
    endlocal
)
```

The inner `for /f` drops the CR and keeps the `!`; `:check_v` turns delayed expansion back on
and reads `!_v!`, which is never parsed again.

---

## 2. Redirect glued to a value (` 1>>`)

**Symptom.** A settings backup or log silently drops exactly the single-digit
values — every `0`/`1` toggle gets written with no value, so a restore reads
nothing back.

**Cause.** `echo %val%>>file` — when `%val%` expands to a single digit, cmd sees
` 1>>file` and parses the `1` as *stream handle 1* (stdout), not as text. The
digit is consumed by the redirect and never reaches the file.

**Detection.** `redirect-var-glue` (WARN) flags a `%var%` glued directly onto
`>>` / `>` in an echo. (A hardcoded ` 1>>` is left unflagged on purpose, because
it is indistinguishable from a legitimate handle redirect like `2>nul` — the fix
below, redirect-first, is the habit that makes both safe.)

**Fix.** Put the redirect *first*, so nothing can be glued onto it:

```bat
:: before  (drops single-digit values)
echo %_dirtyratio%>>"%backup%"

:: after  (redirect-first: value is always written)
>>"%backup%" echo %_dirtyratio%
```

---

## 3. Explicit `<nul` overrides a pipe

**Symptom.** A whole class of device/state probes returns nothing, so
downstream logic misfires: "could not detect refresh rate" aborts a setup that
was fine, a status field shows blank, or — worst — a safety guard that was
supposed to detect the foreground app reads empty and the guard becomes a no-op.

**Cause.** `adb shell ... | findstr "pattern" <nul`. The `<nul` was meant to feed
the *producer* (some tools block waiting on stdin), but it landed after
`findstr`. An explicit `<` redirect overrides the pipe, so `findstr` reads from
`nul`, sees end-of-file immediately, and matches nothing.

**Detection.** `pipe-nul-override` (WARN) flags `<nul` appearing after a pipe
into `findstr`/`find`/`more`/`sort`.

**Fix.** Attach `<nul` to the command that actually needs it, before the pipe —
or drop it if nothing on the line reads stdin:

```bat
:: before  (findstr reads nul, never matches)
adb shell dumpsys display | findstr "refresh" <nul

:: after
adb shell dumpsys display <nul | findstr "refresh"
```

---

## 4. Stale `set /p` re-runs the last choice

**Symptom.** The user presses Enter on a menu without typing anything and the
script re-runs whatever they picked last time — sometimes something
destructive like a reboot or a reset.

**Cause.** `set /p CHOICE=` leaves `CHOICE` untouched on an empty Enter. If
`CHOICE` still holds the previous value, the dispatch below re-fires it.

**Detection.** Two tiers. `setp-stale` (INFO, per line) flags an uncleared
prompt whose value *drives dispatch* — a computed `goto`/`call` or comparisons
against 2+ distinct values — where a stale value re-runs the last action.
Plain Y/N confirms are rolled into one `setp-stale-confirms` summary per file
(a stale `Y` + bare Enter auto-confirms; lower risk, but real). A clear on the
prompt line itself counts: `set "kb=" & set /p kb="..."` is recognised.

**Fix.** Clear the variable immediately before every prompt, so a bare Enter
means "no choice":

```bat
:: before
:menu
set /p CHOICE=Select: 
goto :do_%CHOICE%

:: after
:menu
set "CHOICE="
set /p CHOICE=Select: 
if not defined CHOICE goto :menu
goto :do_%CHOICE%
```

The compound one-liner form does the same and also absorbs a phantom empty
line handed to `set /p` right after a slow probe (the "press-twice" bug —
re-prompt *without* redrawing on empty input so the redraw doesn't re-run the
probes):

```bat
:menu_ask
set "kb=" & set /p kb="  Choose An Option >> "
if not defined kb goto menu_ask
```

---

## 5. A lone quote in input kills the script

**Symptom.** Typing a single `"` at any prompt closes the entire console window
— not a handled error, the whole script dies.

**Cause.** `if %CHOICE%==9 (...)` with `CHOICE` set to `"` expands to
`if "==9 (...)`, which is a syntax error that aborts the batch. Any unquoted
comparison against user input has this hole.

**Detection.** `quote-odd` (INFO) flags lines with an odd number of quotes.
The two standard quote-handling substitutions are recognised as well-formed
and not flagged: the *strip* idiom `set "_gd=%_gd:"=%"` (input sanitising —
the defense this pitfall calls for) and the *escape* idiom
`set "_sd=!_sd:"=\"!"` (see pitfall 17). There is no perfect static check for
"can user input reach this comparison," so the fix is a convention, not a
lint.

**Fix.** Always quote *both sides* and use delayed expansion so the value is
inserted as data, not spliced into syntax:

```bat
:: before  (a lone " crashes the parse)
if %CHOICE%==9 goto :quit

:: after
if "!CHOICE!"=="9" goto :quit
```

---

## 6. Bare parens inside ( ) blocks: crash and truncation

**Symptom.** Two flavours of the same parse rule:

- *Crash:* the script aborts mid-routine with `X was unexpected at this time.`
  — often *after* a side effect already happened (e.g. the hosts file was
  modified, then the batch died before printing "done").
- *Silent truncation:* echoed output loses text from the first `)` onward, and
  the rest of the block runs *outside* it — in an `if` block, whatever the
  condition was. Measured with both a true and a false condition: the remaining
  lines *and* the `else` body ran, because a line that starts with `)` outside
  a block is ignored, so cmd skips the block's real `)` / `) else (` line.
  Nastier still, an output-grouping block `( ... ) > file` closes early
  *without its redirect*, so everything sprays to the console and the file is
  never written — it stays missing, or keeps the previous run's contents. A
  5000-line ADB tool shipped exactly this: its diagnostic-report block opened
  at one line, was meant to close 85 lines later into `) > "%REPORT%" < nul`,
  and a `(deci-degrees C)` in an echo 36 lines in detached the whole thing.

**Cause.** Inside *any* paren block — one-line `if () else ()`, a multi-line
`if (`, a `for ... do (` body, or a bare `(` output group — cmd treats a bare
`)` as the block terminator **even in the middle of echo text**. The opening
`(` is harmless (it only opens a block at a command position: line start,
after `&`/`|`/`(`, after `do`/`else`/`in`, or after an if-condition), which is
what makes a paired `(like this)` *look* legal. After the accidental close,
only `do`/`else`/`&`/`|`/`)`/redirects may follow; anything else is the crash.

The `(` and its accidental closing `)` need not be on the same line. A bare
`(` in one echo and a bare `)` in a *later* echo pair up just as destructively —
the report block above has this too:

```bat
    echo  (Each entry = something keeping a wakelock right now.
    echo   PARTIAL_WAKE_LOCK is the usual battery drain.)
```

The `)` at the end of the second line closes the block, truncating everything
after it — even though the two lines look like an ordinary parenthetical
spread across two echoes.

**Detection.** A character-level simulation of cmd's block parsing (quotes
protect, `^` escapes, command-position opens, cross-line depth):
`block-early-close` (ERROR) — an illegal token follows an in-block close, the
crash class; `block-paren-literal` (WARN) — a command inside a block emitted a
bare `(` (an `echo`, an unquoted `set x=(y)`, a `call :f (a)`, …) whose
matching `)` later closes the block, the truncation class (the `(` and `)` may
be on the same line or different lines — the pending `(` is carried across
lines until the block closes; a `)` sitting at a structural close position like
`) > file` on its own line is the intended close and is *not* flagged; blocks
opened by a quoted comparison like `if "a"=="b" (` are tracked too);
`paren-unbalanced` (ERROR) — net depth at end of file isn't zero.

**Fix.** Escape literal parens inside blocks as `^(` and `^)` — both of them,
consistently; escaping only the `)` works but reads as an accident waiting for
the next edit. Remember the *next* bare `)` becomes the new early-closer, so
fix the whole block in one pass, not one paren per crash.

```bat
:: before  (block closes early at the ) in "(reset)")
if exist "%hosts%.bak" ( echo restored ) else ( echo no backup (reset) )

:: after
if exist "%hosts%.bak" ( echo restored ) else ( echo no backup ^(reset^) )
```

```bat
:: before  (the ) after "C" closes the group - report file comes out empty)
(
    echo [Battery]
    for /f "delims=" %%i in ('adb shell dumpsys battery ^<nul') do echo  %%i (deci-degrees C)
    echo [more sections...]
) > "%REPORT%" < nul

:: after
    ... do echo  %%i ^(deci-degrees C^)
```

```bat
:: before  (cross-line pair: the ) on the second echo closes the block)
    echo  (Each entry = something keeping a wakelock right now.
    echo   PARTIAL_WAKE_LOCK is the usual battery drain.)

:: after
    echo  ^(Each entry = something keeping a wakelock right now.
    echo   PARTIAL_WAKE_LOCK is the usual battery drain.^)
```

It isn't only `echo`. The classic *set-in-block* gotcha is the same rule: an
unquoted value with parens leaves the block one `)` short. Quoting the whole
assignment is the idiomatic fix (it also protects `&`, `|`, `<`, `>`, and
spaces in the value), and is why a quoted `set "x=(y)"` inside a block is
perfectly safe while the unquoted form is not:

```bat
:: before  (the ) in "(x86)" closes the if-block, aborting on the next token)
if defined pf (
    set ProgFiles=C:\Program Files (x86)
)

:: after  (quote the assignment - parens are now inert)
if defined pf (
    set "ProgFiles=C:\Program Files (x86)"
)
```

---

## 7. errorlevel captured inside a block

**Symptom.** A check that reads `%errorlevel%` inside a parenthesised block
always sees the *old* value, so error handling never triggers (or always does).

**Cause.** `%errorlevel%` is expanded when the whole block is *parsed*, before
any command in the block runs. So it reflects the state before the block, not
the command just above it.

**Detection.** Not reliably static (depends on intent). Watch for `%errorlevel%`
used inside `( ... )` blocks during review.

**Fix.** Use delayed expansion (`!errorlevel!`) so it's read at run time, or
test with `if errorlevel N`, or restructure to flat labels:

```bat
:: before  (sees errorlevel from before the block)
( adb connect %ip%
  if %errorlevel%==0 echo connected )

:: after
setlocal enabledelayedexpansion
( adb connect %ip%
  if !errorlevel!==0 echo connected )
```

---

## 8. Non-idempotent powercfg / duplicate schemes

**Symptom.** Every run leaves another orphaned "Ultimate Performance" power plan
behind, and the plan you meant to activate never actually becomes active.

**Cause.** `powercfg -duplicatescheme <src>` with no destination GUID mints a
*new random* GUID each time, while `/setactive` targets a fixed canonical GUID
the clones never have. Result: clones pile up, activation is a silent no-op.

**Detection.** Not static (semantic). Flagged here so you recognise the shape:
any "create then reference by a different id" pair is a smell.

**Fix.** Give the operation a fixed destination GUID so it is idempotent —
running twice is the same as running once:

```bat
:: before
powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61
powercfg /setactive e9a42b02-d5df-448d-aa00-03f14749eb61

:: after (canonical dest GUID; re-runs are harmless)
powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61 e9a42b02-d5df-448d-aa00-03f14749eb61
powercfg /setactive e9a42b02-d5df-448d-aa00-03f14749eb61
```

---

## 9. Download "succeeded" on a partial file

**Symptom.** A mid-transfer failure leaves a truncated file that passes the
"did it download?" check and gets installed, corrupting whatever consumed it.

**Cause.** The code checks only file *existence* after `Invoke-WebRequest`. A
partial write still exists, so existence is the wrong signal.

**Detection.** Not static. A review rule: any download gated on `if exist`
alone is suspect.

**Fix.** Gate on the child process exit code, and delete any leftover before the
existence check so a stale file can't masquerade as success:

```bat
del /q "%out%" 2>nul
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; try { Invoke-WebRequest -Uri $env:URL -OutFile $env:OUT } catch { exit 1 }"
if errorlevel 1 ( echo download failed & goto :cleanup )
if not exist "%out%" ( echo download failed & goto :cleanup )
```

---

## 10. Broken goto/call targets and duplicate labels

**Symptom.** A menu option "does nothing," or the script ends with 'cannot find
the batch label'. With duplicates, edits to the "wrong" copy of a label appear to
have no effect.

**Cause.** `goto :typo` with no matching label makes cmd print an error and end
the script. With two `:setup` labels, goto/call find whichever comes first
searching forward from the jump and wrapping at end of file, so the result
depends on where the jump is. Measured, including the details that decide what
the user actually sees:

- The error is `The system cannot find the batch label specified - typo`.
  Whatever is left of the current line or ( ) block still runs before the
  script ends.
- Inside a `call`ed routine, a failed `goto` ends only that routine: control
  returns to the caller with errorlevel 1, as if by `exit /b 1`.
- `call :typo` prints the same error, sets errorlevel 1 and carries on with the
  next line — the menu option "does nothing" apart from that one error line.

**Detection.** `goto-undefined` / `call-undefined` (ERROR) and `label-duplicate`
(ERROR). These are provably wrong from static reading and should always be zero
before shipping. A computed target (`goto :do_%CHOICE%`) is judged by its fixed
prefix: it is reported only when no label starts with `do_`, because only then
does it fail whatever the variable holds. Guarded by
`tests/computed_jump_regression.cmd`.

**Fix.** Rename to resolve the typo or the collision. Re-run the analyzer after
*every* edit so a rename never leaves a dangling jump. `goto :eof` is a built-in
and always valid.

---

## 11. Line-ending and encoding damage

**Symptom.** After editing in the wrong tool, the script behaves erratically or
a label stops being found — with no visible change in the text.

**Cause.** A tool rewrote CRLF to LF, added a UTF-8 BOM, or normalised trailing
whitespace. cmd is sensitive to all three; LF line endings can make `goto` miss a
label (measured: most LF-only layouts lost one, while a few stray lone LFs in a
CRLF file did not reproduce it), and a leading BOM corrupts the first line.

**Detection.** `eol-mixed` (ERROR), `eol-lf` (WARN), `bom` (WARN). Also run
`crlf_edit.py report FILE` for the full byte picture.

**Fix.** Edit through `crlf_edit.py` (or any Python opened with `newline=""`) so
line endings and encoding are preserved exactly. Never let a GUI editor
"clean up" the file. Keep it CRLF, no BOM — and match the file's *existing*
character repertoire: an ASCII-pure script stays ASCII-pure, while a script
that intentionally uses UTF-8 box-drawing menus (`┏━┓`) or emoji stays UTF-8.
"Normalising" either direction is damage. The analyzer's `non-ascii` INFO is
one summary per file for exactly this triage: confirm the non-ASCII lines are
the intentional ones, not a smart-quote that crept in.

---

## 12. Quote-hostile and non-ASCII text through cmd

**Symptom.** Real-world data breaks the plumbing: a Steam path under
`C:\Users\O'Brien` kills the PowerShell one-liner that creates a shortcut; a
program name with non-ASCII characters gets mangled crossing the cmd boundary
and comparisons against it fail; an entry name containing `[ ] * ?` misfires a
wildcard-matching API onto a different value.

**Cause.** Splicing data into *code*. An apostrophe ends a PowerShell
single-quoted string; a quote ends a cmd quoted argument; the console code
page mangles non-ASCII as it round-trips; `!` gets eaten under delayed
expansion. Any character that means something to any layer the value crosses
is a landmine.

**Detection.** `non-ascii` (INFO, one summary per file) helps confirm
intentional non-ASCII vs strays. The quoting failures are a runtime effect —
this is a convention, not a lint.

**Fix.** Stage risky values through **environment variables** instead of
splicing them into the command text, and read them on the other side as data:

```bat
:: before  (an apostrophe in %_STEAMDIR% ends the '...' string and crashes)
powershell -NoProfile -Command "$s = New-Object -ComObject WScript.Shell; $lnk = $s.CreateShortcut('%_STEAMDIR%\steam.lnk'); ..."

:: after   (the value never touches the code text)
set "PT_SLDIR=%_STEAMDIR%"
powershell -NoProfile -Command "$s = New-Object -ComObject WScript.Shell; $lnk = $s.CreateShortcut((Join-Path $env:PT_SLDIR 'steam.lnk')); ..."
```

Do the string work in .NET, never echo the value back through cmd, and use
literal-safe APIs (e.g. `[Microsoft.Win32.Registry]::SetValue`) so names that
*look like* wildcards cannot misfire.

**Showing a non-ASCII name is its own problem.** When a screen must print an adapter, program or
folder name, the letters can be lost on the way in, and not at display:
- `reg query` and other console tools convert their output to the **console code page** when it
  goes into a pipe, which is how `for /f ('...')` reads it. A letter that code page lacks arrives
  as `?`. Measured with a Russian interface and code page 437 for non-Unicode programs:
  `Беспроводная сеть` arrived as `???????????? ????`.
- A worker that writes its answer with `Out-File -Encoding ASCII`, or cleans it with
  `-replace '[^\x20-\x7e]','?'`, loses the letters itself. A UTF-8 file read by `for /f` under
  437 comes back as mojibake instead.

Switch the console to UTF-8 only around the read, and put the saved code page back afterwards.
Workers write UTF-8 without a BOM: a BOM glues itself to the first field. Displaying is the easy
part: cmd writes the console in UTF-16, so `echo !name!` shows the letters under any code page.
Measured in the classic console and in Windows Terminal. `type` of a UTF-8 file is the exception
and needs 65001 while it runs.

```bat
:Utf8On
if defined _cpSaved goto :eof
set "_cpRaw="
for /f "tokens=2 delims=:" %%p in ('chcp') do set "_cpRaw=%%p"
if defined _cpRaw set "_cpRaw=!_cpRaw: =!"
if defined _cpRaw set "_cpRaw=!_cpRaw:.=!"
if not defined _cpRaw goto :eof
set "_cpBad="
for /f "eol=0 delims=0123456789" %%c in ("!_cpRaw!") do set "_cpBad=1"
if defined _cpBad goto :eof
if "!_cpRaw!"=="65001" goto :eof
set "_cpSaved=!_cpRaw!"
chcp 65001 >nul
goto :eof
:Utf8Off
if not defined _cpSaved goto :eof
chcp !_cpSaved! >nul
set "_cpSaved="
goto :eof
```

Two more places where UTF-8 text breaks, both measured:
- **A generated .bat written at 65001 is UTF-8, and a double-click runs it at the default code
  page.** cmd decodes each line with the code page in force when it reads it, so a restore file
  wrote `Телефон` to the phone as `╨ó╨╡...` and still printed `[OK]`. Put `chcp 65001 >nul`
  near the top, before any line that can hold such text, and restore the saved page on the way out.
- **`fc` damages UTF-8 text.** Under 65001 it breaks every letter with a byte in 0x80-0x9F,
  which is half of Cyrillic and most of CJK; under 437 it breaks them all. Diff UTF-8 files
  with something that reads them as UTF-8.

`set /p` reading typed Cyrillic under 65001 and `more` showing a UTF-8 file were both fine on
Windows 11, in the classic console and in Windows Terminal.

chcp's text is localized, but its number is not. Some languages end the line with a period
(`Aktive Codepage: 850.`). If no plain number comes out, skip the switch rather than guess. A
test of this needs a console for chcp to act on. A hidden console, or a child started with
`CreateNoWindow`, has one.

---

## 13. Unguarded expansion ops on an empty variable

**Symptom.** The whole script aborts the moment a config/preset file contains a
line like `key=` (empty value) — or the value quietly comes out as garbage like
`~0,-1`. Every other line works; this one kills the run.

**Cause.** Start with what an undefined variable does in a **batch file**: a
plain `%_v%` expands to nothing. It is never printed literally — `%_v%` survives
as text only when typed at an interactive prompt or in a `cmd /c` command line,
which is where that myth comes from. The empty expansion crashes nothing by
itself; the line fails only if what is left no longer parses:

```bat
echo %BS%   text        :: prints "   text" - fine
if "%x%"=="1" goto a    :: becomes  if ""=="1" goto a  - fine; this is why the quotes matter
if %x%==1 goto a        :: becomes  if ==1 goto a  -> "goto was unexpected at this time.", script aborts
```

Substring and substitution expansions (`%_v:~0,-1%`, `%_v:x=y%`) do worse. On
an undefined variable cmd deletes only the `%_v:` part and keeps the rest as
literal text, and the leftover closing `%` pairs with the next `%` on the line,
deleting everything in between. Measured, with `_v` undefined:

```bat
echo [%_v:~0,-1%]                        :: [~0,-1]
set "_q=%_v:"=%"                         :: _q is  "=  - the quote-strip idiom just injected a quote
echo [%_v:~0,1%] then %OS% tail          :: [~0,1OS tail
if "%_v:~-1%"==" " set "_v=%_v:~0,-1%"   :: The syntax of the command is incorrect. - aborts
```

Delayed expansion changes *when* this bites, not *whether*. `!_v:...!` on an undefined
variable leaves the same literal text behind. It cannot abort anything — the line was
parsed before the expansion ran — so the leftover lands in the variable instead, and the
variable is now **defined**, which also defeats every later `if defined` check on it.
Measured, `_v` undefined, delayed expansion on:

```bat
set "_s=!_v: =!"                         :: _s is [ =]  - "strip the spaces" defined it
set "_s=!_v:~0,-1!"                      :: _s is [~0,-1]
set "_s=!_v:"=!"                         :: _s is ["=]  - the same injected quote
echo [!_v:~0,1!] then !OS! tail          :: [~0,1OS tail
```

**Detection.** Semantic — review rule. Grep for `:~` and `:=`-style expansions
and check each is guarded when the value can be empty — and check *where* the
guard sits (see Fix). For a plain `%var%`, look for unquoted comparisons.

**Fix.** Guard every substring/substitution expansion whose input can be
empty — on its **own line**, or with delayed expansion. `%...%` is expanded and
the whole line parsed before an `if defined` on that line runs, so a same-line
guard only helps when the garbage still parses: `if defined _v set "_v=%_v:~0,-1%"`
is fine (it becomes a harmless `set "_v=~0,-1"` that never runs), but the same
guard in front of the trim below still aborts.

```bat
:: before  (on "key=" this is a syntax error and the whole script aborts)
if "%_v:~-1%"==" " set "_v=%_v:~0,-1%"

:: after - the guard on its own line
if not defined _v goto :trim_done
if "%_v:~-1%"==" " set "_v=%_v:~0,-1%"
:trim_done

:: or, with delayed expansion on - still guarded, but the guard may share the line
if defined _v if "!_v:~-1!"==" " set "_v=!_v:~0,-1!"
```

For a plain `%var%` in a comparison, quote both sides (pitfall 5).

---

## 14. ASCII sort picks the wrong "latest" version

**Symptom.** A tool that finds "the newest app-* folder" silently starts
patching an **old** version — but only after the app updates across a digit
rollover. It worked for months first.

**Cause.** `dir /o-n` (and plain string sort) compares character by character:
`app-1.0.9` sorts *after* `app-1.0.10` because `9 > 1`. Any versioned folder
or file pick based on name order has this time bomb.

**Detection.** Review rule: any `dir /o-n`/`/on` (or first-match `for`) used to
choose among versioned names.

**Fix.** Version-sort in PowerShell with a real `[version]` cast and take the
top entry:

```bat
:: before
for /f "delims=" %%D in ('dir /b /o-n "%_droot%\app-*"') do ( set "_appdir=%%D" & goto :got )

:: after (true semantic version ordering)
set "PT_DROOT=%_droot%"
for /f "delims=" %%D in ('powershell -NoProfile -Command "Get-ChildItem -Directory (Join-Path $env:PT_DROOT '') -Filter 'app-*' | Sort-Object {[version]($_.Name -replace '^app-','')} -Descending | Select-Object -First 1 -ExpandProperty Name"') do set "_appdir=%%D"
```

No carets on those pipes: they sit inside the double-quoted `-Command` string, where cmd
already treats them as text, and a caret inside quotes is passed on literally (pitfall 32).
This example used to write `^|` there. Measured, that form fails — PowerShell reports
`A positional parameter cannot be found that accepts argument` and nothing is returned —
while the form above picks `app-1.0.10`, where `dir /o-n` picks `app-1.0.9`.

---

## 15. reg.exe from PowerShell mangles quotes

**Symptom.** Restoring a REG_SZ whose data contains `"` writes corrupted data
(doubled, stripped, or split at the quote) — the undo path destroys the value
it was meant to restore.

**Cause.** Calling native `reg add` *from PowerShell 5.1* re-quotes arguments
on the way to the child process; embedded quotes in the data don't survive the
translation.

**Detection.** Review rule: any PowerShell code that shells out to `reg.exe`
with value *data* (not just key paths) in its arguments.

**Fix.** Stay inside PowerShell/.NET for the write: `Set-ItemProperty` with the
hive short-name converted to a PSDrive path:

```powershell
# before  (quote in $d arrives mangled)
reg add $k /v $n /t REG_SZ /d $d /f

# after
$pk = $k -replace '^HKLM\\','HKLM:\' -replace '^HKCU\\','HKCU:\'
Set-ItemProperty -LiteralPath $pk -Name $n -Value $d
```

---

## 16. `%RANDOM%` backup-name collisions

**Symptom.** One action's undo file silently overwrites another's: two registry
values under the same key are backed up in the same pass, and only one `.reg`
survives. The restore then only half-works.

**Cause.** `%RANDOM%` is 0–32767, and there are three ways two names collide. Only the
last is the birthday problem people expect:

- **Inside a `for` body it is expanded once**, when the loop is parsed, so every pass gets
  the *same* number — a certain collision, not a likely one. (A `goto` loop re-parses each
  pass and does not have this problem.)
- **Each new cmd process seeds from the clock** (`srand(time(NULL))`, one-second
  resolution — Raymond Chen, *Why cmd.exe's %RANDOM% isn't so random*). Processes started
  within the same second draw the identical sequence: a helper run through `cmd /c` or
  `start`, or two copies of the script.
- **Separate lines in one process** do draw different numbers. There the birthday problem
  is the whole risk: small for any two names, real over a long run.

Measured: four passes of a `for /l` body printed `19306` every time while `!RANDOM!` gave
four different values, and four `cmd /c` children started back to back all printed the
same doubled value, `1930625382`.

**Detection.** Review rule: a generated file name built from `%RANDOM%` inside a `for` body
(an `if` block within one included), or in a script that runs helpers in child processes or
can run twice at once. A single `%RANDOM%` on a top-level line is the mild case.

**Fix.** Put something in the name that differs between the things being backed up — a
counter, the value name — rather than trusting the number:

```bat
:: before  (inside a for loop: one number for every pass)
set "_bkp=%BACKUP_DIR%\undo_%RANDOM%.reg"

:: after  (delayed expansion on)
set /a "_bkn+=1"
set "_bkp=%BACKUP_DIR%\undo_!_bkn!_!RANDOM!.reg"
```

Doubling to `%RANDOM%%RANDOM%` (~30 bits) is still worth doing on a top-level line, but it
fixes neither of the first two causes: inside a loop both halves are frozen together, and
a child started in the same second draws the same pair.

---

## 17. Generated .reg files: escape backslashes and quotes, never strip

**Symptom.** A `.reg` undo file fails to import, or imports with a value whose
quotes vanished — the "backup" restores *different data* than what was there.

**Cause.** REG_SZ data written into a generated `.reg` without escaping. Inside a
`.reg` file the backslash is the escape character, so in string data every `\` must be
written `\\` and every `"` written `\"` — and every path is string data full of
backslashes. Stripping quotes to dodge the problem is silent data loss on restore. An
empty value hits pitfall 13 on top.

**Detection.** Review rule on any routine that writes `"name"="data"` lines.
The escape idiom's odd-looking quoting is recognised by `quote-odd` as
well-formed.

**Fix.** Escape with the substitution idiom, guarded for empty — backslashes **first**,
then quotes:

```bat
:: before  (a quote in !_sd! corrupts the .reg; stripping it corrupts the data)
>>"!_bkp!" echo "!_val!"="!_sd!"

:: after
if defined _sd set "_sd=!_sd:\=\\!"
if defined _sd set "_sd=!_sd:"=\"!"
>>"!_bkp!" echo "!_val!"="!_sd!"
```

The order matters. Measured on `C:\Tools\say "hi".exe`: backslashes then quotes gives
`C:\\Tools\\say \"hi\".exe`, which is right; quotes then backslashes gives
`C:\\Tools\\say \\"hi\\".exe` — the second pass doubles the backslash the first pass put in
front of each quote, so the quote is unescaped again. Value *names* are quoted strings too
and need the same treatment when they can contain either character. (An earlier version of
this example showed only the quote step; the script it was taken from does both.)

This is the *escape* twin of pitfall 5's *strip* idiom: strip on the way **in**
(sanitising user input), escape on the way **out** (generating files).

---

## 18. Unconditional `[OK]` — dishonest status reporting

**Symptom.** An action prints `[OK]` even though registry writes failed, the
download broke, or the script was never elevated. The user trusts a green line
that means nothing; the failure surfaces much later as "the tweak didn't
stick."

**Cause.** A final `echo [OK]` with no branch. Failures inside `call`ed
subroutines are invisible to the caller; `endlocal` wipes any counter that
tried to track them; non-elevated runs "succeed" because nothing checked.

**Detection.** Review-level: grep for `echo` lines containing `[OK]` and check
each is gated. Mechanical linting can't see intent — this is the pattern to
*build*, mirrored from a mature ~2700-line optimizer:

**Fix — the honest-reporting pattern.**

- Every risky write reports **inline** `[FAIL]` at the site and increments a
  `_FAILS` counter; the counter is propagated across scope ends:
  `endlocal & set "_FAILS=%_FAILS%"`.
- Every gated action **resets** `_FAILS` at its start and ends by calling one
  shared `:Summary` routine — never a raw `echo [OK]`.
- `:Summary` branches: `[OK]` only when `%_FAILS%`==0, `[WARN] n of m writes
  failed` otherwise — and tailors the message to `%_ELEV%`.
- **Elevation honesty:** the admin probe sets `_ELEV=1`; declining UAC sets
  `_ELEV=0` explicitly (no silent "continuing anyway"), and service/boot
  actions gate their final status on it with a `[WARN]` branch.
- A `_RUNTRACK` flag scopes *which* child exit codes count as failures, and
  `:Summary` clears it — so benign nonzero exits during cleanup don't cry
  wolf.

A test harness should lock this in (counter resets, `:Summary` call sites,
inline `[FAIL]` presence) — see the skill's testing section.
---

## 19. `setx` truncates PATH and flattens `REG_EXPAND_SZ`

**Symptom.** A script edits `PATH` with `setx` and it works on the author's test
box. On a real machine, entries vanish — or everything still resolves until
Windows moves a folder, and then nothing does. Both failures land *after* the
write, and `setx` reported success.

**Cause.** Two documented behaviours of `setx`, either of which is fatal for
`PATH`:

- **A 1024-character limit.** Microsoft's `setx` reference is explicit that
  content over 1024 characters is *cropped*, and that the cropped text is what
  gets applied — so a real machine `PATH` (routinely longer) is silently
  destroyed, keeping only the front of it.
- **It expands variable references.** Running `setx` against an existing
  variable "removes any variable references and uses expanded values." A `PATH`
  is normally `REG_EXPAND_SZ` holding `%SystemRoot%`, `%ProgramFiles%` and
  friends; `setx` freezes those to literal absolute paths and downgrades the
  value to `REG_SZ`. Later OS changes stop being reflected.

Reading `%PATH%` from the live environment is the same trap from the other end:
that string is already expanded, and already merged from the machine *and* user
values — write it back to either scope and you have corrupted both.

**Detection.** Review-level. Grep for `setx` in any script that touches `PATH`.
In a harness, assert that no *executable* line invokes it (skip `echo`/`rem`, or
a banner explaining the avoidance will trip the check — see pitfall 12's cousin
in the skill's testing section).

**Fix.** Go through the registry, and tell the system afterwards.

```bat
rem  Scope is two distinct keys - never mix them:
rem    machine : HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment
rem    user    : HKCU\Environment

rem  READ raw, so %VAR% survives (reg query returns the unexpanded data):
reg query "HKCU\Environment" /v Path

rem  WRITE keeping the type:
reg add "HKCU\Environment" /v Path /t REG_EXPAND_SZ /d "%_new%" /f
```

Then broadcast `WM_SETTINGCHANGE` so new processes see it without a sign-out —
one embedded PowerShell line, per the env-var hand-off convention:

```
SendMessageTimeout([IntPtr]0xffff, 0x1A, [IntPtr]::Zero, 'Environment', 2, 5000, [ref]$r)
```

`0xffff` = `HWND_BROADCAST`, `0x1A` = `WM_SETTINGCHANGE`. Already-open programs
keep the old value until restarted — say so rather than implying otherwise.

Two more constraints worth building in: back the whole value up before the first
edit (a mangled `PATH` is not something a user can reconstruct), and remember a
cmd variable caps at ~8191 characters, which a legal machine `PATH` can exceed —
so do the string work in the PowerShell worker via an environment variable, not
in a batch variable.

---

## 20. A wrong identifier fails quietly — absent is not success

**Symptom.** The script says it disabled the scheduled task / blocked the rule /
stopped the service. Nothing changed. Re-running says the same thing.

**Cause.** Many Windows tools take a *name or path you have to get exactly
right*, and returning "no such thing" is not the same as failing loudly:

- `schtasks /Change /TN "..."` needs a task's **full folder path**
  (`\Microsoft\Windows\Application Experience\MareBackup`), not its name. A wrong
  path is an error — but if the call is wrapped in a runner that only counts
  failures when *not* elevated (a deliberate rule, see pitfall 18), an elevated
  run swallows it.
- The same shape appears with service short names, firewall rule groups, and any
  `reg delete` of a key that was never there.

The deeper problem is that an action against a named thing has **three**
outcomes, not two: *not present here*, *present but not changed*, and *changed*.
Collapsing the first into "done" is pitfall 18 at the identifier level — and it
is worse, because it also hides your own typo.

**Detection.** Review-level, and it is worth being suspicious specifically of
identifiers you could not verify on a live system. If you are transcribing a path
out of another tool, check what that tool actually does — a reference
implementation that matches *by name* is telling you the paths are not stable
enough to hardcode.

**Fix.** Prefer a lookup that resolves the identifier for you, and report all
three outcomes.

```powershell
# BAD: hardcoded path, silent on a typo or a different Windows edition
schtasks /Change /TN "\Microsoft\Windows\...\MareBackup" /Disable

# GOOD: find it wherever it lives, and count what really happened
$found = 0; $ok = 0
foreach ($n in $names) {
  foreach ($t in @(Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue)) {
    $found++
    try { Disable-ScheduledTask -InputObject $t -ErrorAction Stop | Out-Null; $ok++ } catch {}
  }
}
```

Hand `found`/`ok`/`checked` back to the batch and branch on them: `[SKIP]` when
nothing was present (honest — this edition simply doesn't have it), `[FAIL]` when
things were found but none changed (usually elevation), `[OK] n of m` otherwise.
The same applies to firewall work: flipping the rule group Windows already ships
beats inventing a `netsh` rule, because there is no name to get wrong and nothing
to clean up afterwards.

**An empty answer is the hardest case.** After a clear or a delete, the read-back you want is
*nothing*. A transport that has gone away also answers with nothing: a phone that dropped off
adb, a remote query that timed out. Counting that as "cleared" makes every dropped connection
a success. Make the tool prove it is still answering first, and only then count an empty
read-back as cleared. For adb, `adb shell echo MARK` must print `MARK`. A non-empty expected
value does not need this, because a dead link cannot produce it.
---

## 21. A CIM namespace is only as good as its worst provider

**Symptom.** A PowerShell probe that works on your machine returns nothing on a
user's. Not an error they see — the `catch{}` swallows it and the script reports
whatever the "couldn't tell" default is, forever, on that hardware.

**Cause.** The convenience cmdlets are a façade over a CIM namespace, and some
namespaces **enumerate across every registered provider**. Microsoft's own
`Get-PhysicalDisk` reference says it returns objects "visible across any
available Storage Management Providers" — so a single broken vendor provider
makes *every* cmdlet in `root\Microsoft\Windows\Storage` throw, including raw
`Get-CimInstance MSFT_PhysicalDisk`. OEM laptops ship storage agents and RAID
stacks as standard, so this is a common configuration, not an exotic one.

Observed in the field: on an HP Omen with a healthy NVMe SSD, `Get-Partition`,
`Get-PhysicalDisk` **and** raw `Get-CimInstance MSFT_PhysicalDisk` all failed
with `CimException: "Invalid property"`, while the machine itself was fine.
Every WMI-based fallback failed together, because they share the one broken
dependency — the classic mistake of "adding a fallback" that fails for exactly
the same reason as the primary.

**Detection.** Not lintable, and this is the part worth internalising: **a
cmdlet chain that parses is not a cmdlet chain that binds, and neither is one
that runs.** A static harness proves the text is present; it cannot prove the
call resolves, that a parameter set matches, or that a provider answers. Any
probe that leans on CIM needs a real-machine run — or a path that doesn't need
CIM at all.

**Fix.** Where the OS exposes a direct API for the same fact, prefer it: fewer
dependencies, no provider surface, and usually faster. For SSD-vs-spinning, the
question has a literal API — `IOCTL_STORAGE_QUERY_PROPERTY` with
`StorageDeviceSeekPenaltyProperty`, which is what Windows itself uses:

```powershell
# open the VOLUME with 0 access - query only, no read rights, no elevation needed
$h = [PTDisk.N]::CreateFile('\\.\C:', 0, 3, [IntPtr]::Zero, 3, 0, [IntPtr]::Zero)
$q = New-Object PTDisk.SPQ
$q.PropertyId = 7        # StorageDeviceSeekPenaltyProperty
$q.QueryType  = 0        # PropertyStandardQuery
$q.AdditionalParameters = New-Object byte[] 1
$d = New-Object PTDisk.DSPD
if ([PTDisk.N]::DeviceIoControl($h, 0x2D1400, [ref]$q, ..., [ref]$d, ..., [ref]$ret, [IntPtr]::Zero)) {
    if ($d.IncursSeekPenalty) { 'hdd' } else { 'ssd' }   # a seek penalty IS the spinning platter
}
```

`STORAGE_PROPERTY_QUERY` and `DEVICE_SEEK_PENALTY_DESCRIPTOR` each marshal to 12
bytes. Keep the CIM route only as a **fallback gated on the primary having
failed**, so it can turn an "unknown" into an answer but never the reverse — and
be honest that a fallback sharing the primary's dependency is not a fallback.
---

## 22. A backup that can't tell "unreadable" from "unset" is a deletion script

**Symptom.** The worst one there is: the backup reports success, and restoring it
**destroys** the thing it was supposed to protect.

**Cause.** Backup code reads a current value and records it. The read fails — the
device is unplugged, the service is down, the key is on a hive you can't touch —
and returns *empty*. Now look at what "empty" means to the writer:

```bat
set "_val="
for /f "delims=" %%v in ('adb shell settings get %_ns% %_key% 2^>nul') do set "_val=%%v"
if "!_val!"=="" set "_val=null"
if /i "!_val!"=="null" (
    >>"%_out%" echo settings delete %_ns% %_key%     &rem  <-- DELETE on restore
)
```

That mapping is correct *when the read worked*: a key with no value should be
deleted on restore, not set to empty. It is catastrophic when the read **failed**,
because the two are indistinguishable at this point — and they were distinguishable
one line earlier: `settings get` prints the literal word `null` for a key that is not
set, and `if "!_val!"==""` throws that away before anyone can use it. The failure is
the quiet one. Unplug the cable, run Backup, get "Backup complete.", and you now hold
a file whose sole content is instructions to erase every managed setting.

The general shape, well beyond adb: **a read that fails silently, mapped to a
value that means "remove it".** Registry backups (`reg query` on a missing hive),
config dumps, anything with a "not set" sentinel.

**Detection.** Not lintable — the code is *correct* on its face; the bug is a
missing precondition. Ask of every backup routine: *what does this write if every
read returns nothing, and would I hand that file to a user?*

**Fix.** Three guards, and the first is the one that matters:

1. **Prove the source is reachable before reading anything**, and refuse otherwise.
   Check once, up front:

   ```bat
   set "_dvst="
   for /f "delims=" %%d in ('adb get-state 2^>nul') do set "_dvst=%%d"
   if /i not "%_dvst%"=="device" ( echo Backup refused - no device. & goto menu )
   ```

   Necessary, and not sufficient: a long backup can lose the device *during* the run,
   and a phone that is still rebooting answers `adb get-state` with `device` while its
   settings service is not up yet. Both land in the same trap, one key at a time.

2. **Use the tool's own "unset" marker when it has one.** Android's `settings get`
   prints the literal word `null` for a key with no value (AOSP's settings command
   does `println(result)` on a `null` string), and sends read failures to stderr — so
   an *empty* capture means the read failed, and `null` means unset:

   ```bat
   set "_val="
   for /f "delims=" %%v in ('adb shell settings get %_ns% %_key% 2^>nul') do set "_val=%%v"
   if not defined _val (
       >>"%_out%" echo rem %_ns% %_key% - unreadable at backup time, left as it is
   ) else if /i "!_val!"=="null" (
       >>"%_out%" echo settings delete %_ns% %_key%
   ) else (
       >>"%_out%" echo settings put %_ns% %_key% '!_val!'
   )
   ```

   Not every tool gives you one: `getprop` answers an unset property with an empty
   line, which is exactly what a failed read looks like, so there guard 1 is all you
   have. Check which case you are in before you write the restore line.

   If the restore file is itself a batch file, the value you echo into it becomes code
   there: a `%` in it is consumed when the file runs, and a `"` can turn the rest of the
   line into syntax (pitfall 27) — worse again if the line hands it to a `call`
   (pitfall 53).

3. **Prove the file is real before claiming it exists.** Not `if exist` alone —
   the header may have been written while every value append was blocked (antivirus
   and Controlled Folder Access guard exactly the folders backups live in). Check for
   a line that only a successful capture produces:

   ```bat
   set "_bkok=0"
   if exist "%BAKFILE%" findstr /b /c:"call :dcx_do" "%BAKFILE%" >nul 2>&1 && set "_bkok=1"
   ```

A backup a user *believes* they have is worse than one they know failed: they act
on the belief, and they find out at the moment they can least afford to.

---

## 23. A caret followed by trailing whitespace is not a line continuation

**Symptom.** A long command split across lines with `^` silently stops splitting.
The first half runs alone; the second half runs as its own command — often
harmlessly, occasionally not.

**Cause.** `^` escapes the *next character*. At end-of-line that character is the
newline, which is what makes it a continuation. Add a single trailing space and
the caret escapes the **space** instead; the newline ends the command as usual.
The difference is invisible in every editor that does not render whitespace, and
it survives copy-paste, review, and diff.

**Detection.** Trivially lintable, and now checked: `analyze_batch.py` reports
`caret-trailing-ws`. Guarded by `tests/caret_ws_regression.cmd`.

**Fix.** Strip trailing whitespace. It is worth doing across the whole file as a
matter of hygiene, precisely because this is the one place where invisible
characters change behaviour — and while you are there, note that trailing spaces
*inside* quotes (`set "pad=x   "`) are load-bearing and end with `"`, so a plain
right-strip never touches them.

---

## 24. A fixed-name backup is destroyed by the second run

**Symptom.** The undo works once. Run the same action a second time, then restore —
and you get back the *modified* file, not the original. To the user this looks like
the restore silently did nothing, because in effect it copied the change over itself.

**Cause.** Two things that are individually reasonable. The backup lives beside the
file under a fixed name (`hosts.bak`, `app.asar.bak`, `boot.config.bak`), and the
action copies to it unconditionally on every run. The first run saves the pristine
original; the second run saves *what the first run wrote*. If the action is one users
are told to repeat — "re-run this after a Discord update reverts it" — the destructive
path is the documented workflow, not an edge case.

This is the same bug class an idempotence guard already prevents on the registry side
(re-applying a value that is already at the target must skip *before* writing a
backup, or the redundant apply buries the true-original undo). Scripts that learned
that lesson for `reg add` routinely still have it for files.

**Detection.** Grep every backup target for a fixed name and ask one question of each:
*is this action meant to be run twice?* If yes, it is already broken. Check the
restore side too — it commonly prefers the beside-the-file copy, which is precisely the
poisoned one, and a "newest first" fallback picks the most recently poisoned of the
rest.

**Fix.** Split the two jobs the backup was doing.

```bat
rem  BEFORE - one copy, fixed name, unconditional
copy /y "%_HOSTS%" "%_HOSTS%.bak" >nul 2>&1 && set "_hbak=1"

rem  AFTER - write-once pristine original, plus a randomized per-run snapshot
if not exist "%_HOSTS%.bak" copy /y "%_HOSTS%" "%_HOSTS%.bak" >nul 2>&1
copy /y "%_HOSTS%" "!_hbakdoc!" >nul 2>&1 && set "_hbak=1"
if exist "%_HOSTS%.bak" set "_hbak=1"
```

The gate is satisfied by *either*, deliberately: a pristine original already on disk is
a **better** undo than a fresh copy of the current file, not a worse one. Then make the
restore prefer the write-once copy, and if it falls back to the snapshots, take the
**oldest** — the newest is the most recently modified state, which is usually something
this script itself applied.

---

## 25. A generated undo script must restore the important thing first

**Symptom.** The restore ran, the machine crashed or the window was closed part-way,
and afterwards the single thing you most needed back is still not back — even though
most of the script executed.

**Cause.** The generated `.bat` was written in logical order: set all the values, then
activate. That puts the one irreplaceable action last, so any interruption skips
exactly it. And a partial run is not exotic here — these scripts restore machine state,
which is precisely the situation where a machine is already misbehaving. In one real
case the restore of a power scheme crashed during the value writes and never reached
its trailing `powercfg -setactive`, so the user was left on the plan they were trying
to escape.

**Cause, restated as a rule.** Generated undo artifacts have a different failure model
from ordinary scripts. Assume they will be interrupted.

**Detection.** Review rule — no lint can know which line matters most. For each
generator, name the one action whose absence would leave the user worst off (the
activate, the service start, the file put back) and check it is emitted first.

**Fix.** Order by importance, not by data flow, and make it idempotent so the
belt-and-braces repetition is free:

```bat
rem  the plan itself goes back FIRST - a partial run still leaves you on it
powercfg -setactive {scheme}

powercfg -setacvalueindex {scheme} {sub} {setting} {value}
...

rem  again at the end, because changed values only take effect on activation
powercfg -setactive {scheme}
```

While you are writing the generator: emit a comment instead of a guess for anything you
could not capture (a setting the scheme never had explicitly should stay at its
default, not be invented), and make the trailing `pause` conditional
(`if "%~1"=="" pause`) so the file is pleasant to double-click *and* callable from the
tool without blocking a menu.

---

## 26. Localized command output is not a data source

**Symptom.** A parser works perfectly on the developer's machine and silently returns
nothing on a user's. Not an error — an empty result, which downstream logic reads as
"there was nothing to capture". The undo file is written, looks plausible, and restores
less than it claims.

**Cause.** The code parses a CLI tool's human-readable output, and that output is
translated. `powercfg /query` prints `Current AC Power Setting Index` in English and
something else entirely under a Russian, German or Japanese install. Same for `sc
query`, `net`, `tasklist` headers, and most of `wmic`. Matching on that wording ties
the feature to one locale, and the failure is quiet because "no lines matched" and
"nothing to report" are indistinguishable.

**Detection.** Search embedded PowerShell and `for /f` loops for English prose in a
match: `findstr /C:"Current"`, `Select-String 'Power Setting'`, `-match 'Running'`.
Anything matching a *word* rather than a symbol, number or GUID is suspect.

**Fix.** Prefer a locale-invariant source, in this order:

1. **The registry.** Power schemes, services, and most Windows settings have registry
   homes whose value names are identical in every language —
   `HKLM\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes\{guid}\{sub}\{setting}`
   carries `ACSettingIndex` / `DCSettingIndex` regardless of display language.
2. **Structured output.** A cmdlet returning objects, or a tool's `/xml` / `/fo csv`
   mode, beats scraping its default view.
3. **Locale-invariant tokens.** If you must parse text, match GUIDs, numbers, or
   punctuation the translation cannot move — a regex for a GUID shape is safe, a regex
   for "Power Scheme GUID:" is not.

Getting the `{guid}` in that registry path right is its own trap. `powercfg`'s scheme
aliases are named for power *savings*, not performance, so they read backwards:

| Alias | GUID | Plan |
|---|---|---|
| `SCHEME_MIN` | `8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c` | High performance (minimum power savings) |
| `SCHEME_MAX` | `a1841308-3541-4fab-bc81-f71556f20b4a` | Power saver (maximum power savings) |
| `SCHEME_BALANCED` | `381b4222-f694-41f0-9685-ff5bb260df2e` | Balanced |

Verified with `powercfg /aliases` and the built-in plans' `FriendlyName` values under
`HKLM\SYSTEM\CurrentControlSet\Control\Power\User\Default\PowerSchemes\{guid}`. Those
names are resource strings, translated like everything else in this entry; the aliases and
GUIDs are not. Mixing the two up points a backup or a restore at the wrong plan, so check a
mapping with `powercfg /aliases` rather than from memory before "correcting" one.

The related trap is anchoring: `findstr`'s `$` only fires before a CR, so output piped
from a tool that emits bare LF never matches an end-of-line anchor. Same category —
the pattern depends on something environmental you did not check.

---

## 27. Batch that writes batch — and `echo`'s other forms

**Symptom.** The analyzer (or a reviewer) reports `goto-undefined` /
`call-undefined` on lines that are obviously working as intended:

```bat
>>"%_out%" echo call :dcx_do "settings put %_ns% %_key% '!_sv!'"
echo(Use goto :menu to go back
echo ok & rem see :Cleanup for the rest
@rem goto :legacy_path - kept for reference
```

The referenced labels exist in the **generated** file, or nowhere at all
because the text is a comment. A backup feature that writes a standalone
restore `.bat` puts `goto`/`call :label` text on `echo` lines; comments name
routines constantly. On a real ~8400-line ADB front-end the naive scan
produced 5 confident false ERRORs — worse than it sounds, because a
known-false ERROR makes the exit code permanently red and quietly costs you
the per-edit gate.

**Cause.** Matching `goto`/`call` against whole lines, and recognising only
one spelling of `echo`. Three forms turn text that looks like a jump into data
or comment:

| Form | Why it is missed |
|---|---|
| `echo(text` | The paren-delimiter twin of `echo.`; a regex expecting `echo` + space/dot skips it. The corpus uses it ~29 times (`echo(!var!\| findstr ...`) |
| `cmd & rem note` | An inline `rem` comments out the rest of the **line**, but `is_comment()` only sees line-leading comments |
| `@rem text` | A comment to cmd, invisible to `is_comment()` because of the `@` |

**Detection / fix (mechanical).** `strip_echoed()` blanks echo- and rem-emitted
text before the jump scan, and the two end in different places. An `echo` ends
at the first unquoted, unescaped `&`, `|` or `)`, so `echo hi & goto :next` and
`echo(text| findstr x || goto :next` still fire; `^&` stays literal and `2>&1`
shields nothing. A `rem` ends only at the end of the line — `&`, `|` and `)`
are part of the comment — so `echo x & rem note & goto :next` never jumps.
Measured: `echo first & rem note & echo X` prints `first` and nothing else.
Both keywords count only where a command starts, so `call :lorem ipsum` holds
no rem. Guarded both ways by `tests/test_labels_echo_regression.py` — every
suppression case in the fixture sits beside a live control, and the pair was
verified to fail against the pre-fix analyzer (3 false positives, 0 missed).
What the end-of-line rule does inside blocks is pitfall 54.

**Three review rules stay yours, not the analyzer's:**

- **The generated file is real cmd — lint the OUTPUT too.** Everything in
  this catalog applies to it: its own labels, `:eof` discipline, honest
  counters, an `[OK]`/`[WARN]` summary, and pitfall 25's restore ordering.
  Generate a sample and run the analyzer on it as part of validation; if the
  generator feeds a port or data pipeline, gate the artifacts too
  (`extract_baseline.py` exists for that).
- **Emitted parens still hit the OUTER parse.** An `echo` that runs inside a
  `( )` block is parsed by cmd before it prints, so a bare `)` in the emitted
  text ends the enclosing block (pitfall 6). The block simulator keeps
  flagging those on purpose — that is not a false positive.
- **A value you write into the file is code there.** The generated file gets its own
  percent pass when it runs, so a `%` in captured data must be written `%%`. Measured
  with a stub standing in for adb: `Over%20the%20Horizon`, written as-is, was restored as
  `Over0the0Horizon`, because `%2` was read as the restore file's own (empty) second
  argument. `!` is live too if the generated file enables delayed expansion. A `"` is
  the one to refuse rather than escape: it ends the quoting on the emitted line, and an
  `&`, `|`, `<` or `>` after it becomes syntax that runs when the user restores — emit a
  comment naming the skipped value instead. And hand the value over in a variable, not
  as a `call` argument: the first line of the example above is that shape, and `call`
  parses its arguments a second time (pitfall 53). The analyzer reports that emitted shape
  as `call-reparse`.

---

## 28. An accepted-value set stated in more than one place drifts

**Symptom.** A user is told an option does not exist when it does, or is offered one that
gets rejected. Nothing crashes; the tool simply describes itself wrongly - and people
believe the description over the behaviour, because the description is what they can see.

**Cause.** The set of values a feature accepts is almost never written once. A typical
menu-driven script states it in five places: the on-screen help line, the validator, the
**error message** the validator prints, the README table, and the bundled example config.
Adding a value touches the validator and usually the help line, because those sit next to
each other. The error message is a string a few lines further down; the README and the
example file are different files entirely.

Three real instances found in a single review pass, across two projects:

- A compile-mode screen whose help line and validator both listed **six** modes while its
  error message printed **five** - silently dropping the one the README called recommended.
- A preset example documenting three of four accepted values for a registry knob, and
  describing one of the three using *another value's* meaning.
- A preset example still listing three provider names after the validator had gained an
  entirely new form of input.

**Detection.** Whenever you touch any copy of a value set (help line, validator, error
message, README, example config), list the set from the validator and compare every other
copy against it item by item, including files the user didn't mention. A copy that arrives
as text in the conversation counts exactly like a file: a README pasted into the prompt "for
context" is one of the copies, and the easiest one to skip, because nothing sends you to open
it. Never report a copy as correct without that comparison, and when you do call one correct,
show it - the validator's list next to that copy's list - so an unchecked copy cannot pass
for a checked one. To find the copies, grep for the value *set*, not for the key: search a
distinctive member of it - one provider name, one mode - and expect several hits across the
script, the README and any bundled config. Finding fewer places than you changed means you
have not finished. Worth automating where a harness exists: pull the accepted set out of the
validator, pull it out of each place that describes it, and assert the sets are equal.
A menu the README enumerates is a value set too: count its items against the menu, one by
one, in the table and in any prose that lists them.

**Fix.** Name the validator as the single source of truth, where the copies live:

```bat
:: The accepted set lives in THREE places - the "Valid modes" line above, the for-loop
:: whitelist, and this error - and they have to say the same thing. This one used to list
:: five of the six. The loop is the source of truth; keep both texts equal to it.
    echo [!] Invalid mode. Use one of: speed, speed-profile, verify, quicken,
    echo     everything, everything-profile.
```

Then reconcile every copy in the same pass, README table and example config included -
exactly as a pitfall row, its reference entry and that file's index all move together. A
tool that lies about its own options is a documentation bug with a user-facing symptom,
which is the kind that gets reported as "it doesn't work".

---

## 29. Falling through into a `call`ed routine ends the script

**Symptom.** The script exits silently moments after startup, right after a step that
visibly worked. Everything past a certain point is unreachable - a main menu that "never
opens", but only on the common path. An unusual route still reaches it, which makes the
whole thing look like an environment problem rather than a code one.

**Cause.** A routine is `call`ed from the line directly above its own label:

```bat
call :pick_device

:pick_device
...
exit /b 0
```

The `call` runs the routine and returns. Execution then continues onto the next line -
which is the label - and runs the body a **second** time. That pass was not entered by
`call`, so its `exit /b` leaves whatever context the `call` line runs in - at top level,
where this shape usually sits, that ends the batch file (inside another `call`ed routine it
returns from *that* routine instead). Side effects inside the routine happen twice too; a
device picker prompted twice before quitting.

**Detection.** Lintable, and now checked: `analyze_batch.py` reports `call-fallthrough`
(ERROR) when the first non-blank, non-comment line after a `call :X` *is* `:X`. Guarded by
`tests/callfall_regression.cmd`. Only that unambiguous shape is flagged - with anything
executable in between the author plainly meant control to arrive there, and guessing would
only add noise. Re-run against the pre-fix source of the script this came from and it fires
on the exact line.

By hand, sanity-check reachability too: if a label is only ever reached from one unusual
path, ask what was supposed to reach it from the normal one. Here the main menu was
reachable *only* via a no-device -> wireless-setup -> back detour, which is why it read as
"works over Wi-Fi, closes over USB" rather than as a bug.

**Fix.** Jump over the routine.

```bat
call :pick_device
goto detect_device      :: without this, :pick_device runs twice and its exit /b kills the script

:pick_device
```

Related, same symptom from the other direction: invoking another `.bat` **without**
`call` transfers control permanently and never returns.

---

## 30. One level of quoting is stripped before a re-parsing child sees it

**Symptom.** A "clear this value" action reports success and clears nothing. In one ADB
front-end this silently broke four separate features at once, each printing its normal
done message.

**Cause.** cmd removes one level of quoting when it builds a child's argv. Programs that
*rejoin* their arguments and hand them to another parser - `adb shell`, `ssh`, `wsl`,
`docker exec`, `su -c` - then pass the value on **bare**. Empty quotes are the worst case:
they do not survive as an empty argument, they vanish, so the far side gets one argument
fewer.

```
adb shell setprop KEY ""
  -> cmd argv:     shell setprop KEY
  -> phone runs:   setprop KEY                 (one argument)
  -> phone prints: usage: setprop NAME VALUE   (stderr, swallowed by >nul)
```

A quoted value with no spaces survives by luck - `"*:S"` is one token either way - which is
exactly why this hides: some of the quoted lines do work.

**Detection.** For every `adb shell` / `ssh` / `wsl` line, ask what the **far** shell
receives, not what cmd sees. Quotes only matter when they are load-bearing: an empty
string, or a value containing spaces. Then test against a real target - set a scratch
value, run the clear, read it back. Nothing else settles it.

**Fix.** Quote for the *receiving* shell, or hand the whole remote command over as a single
double-quoted argument:

```bat
:: before - never clears anything
adb shell setprop debug.hwui.renderer "" <nul

:: after - '' survives the round trip and arrives as a real empty argument
adb shell setprop debug.hwui.renderer '' <nul

:: also correct - whole remote command is one argument, quoted inside for the far shell
adb shell "settings put secure sysui_qs_tiles '%VALUE%'" <nul
```

Measured on hardware: `""` left the property untouched, `''` cleared it.

---

## 31. `&` and `|` bind to a single-line `IF`

**Symptom.** None - and that is the point. This entry exists because the folklore says the
opposite, so people "fix" correct code and introduce a bug doing it.

**Cause.** In `if COND cmd1 & cmd2` the `& cmd2` belongs to the `if`'s command, not to the
line. The same holds for a pipe. Both measured:

```bat
if 1==2 echo A & echo B                          :: prints nothing
if "%lp%"=="2" type x | find /v "" > out.txt     :: false branch does NOT truncate out.txt
```

That second form is the one that matters in practice: swapping a plain redirect for a
pipeline inside a one-line `if` is safe, because the false branch runs neither half.

**Detection.** Do not reason about this from memory in either direction - it is two lines
to measure, and the answer decides whether a file gets clobbered.

**Fix.** Nothing to fix. If you want the grouping obvious to the next reader, make it
explicit rather than restructuring the logic:

```bat
if "%lp%"=="1" ( adb shell pm list packages | find /v "" > "%LIST%" )
```

---

## 32. Caret-escaped operators outside a `for /f` clause become literal arguments

**Symptom.** A filtered command prints errors from the *far* machine instead of results:
`/system/bin/sh: findstr: inaccessible or not found`, `can't open nul`.

**Cause.** Inside `for /f ('...')` the pipe and redirects must be escaped - `^|`, `^<`,
`^>` - because the clause is parsed twice. Such lines get copy-pasted elsewhere, and out in
the open the caret does what it always does: makes the next character literal. The operator
stops being an operator and is handed to the child as ordinary text.

```bat
:: inside a for /f IN clause - carets REQUIRED
for /f "delims=" %%i in ('adb shell dumpsys power ^<nul 2^>nul ^| findstr /C:"WAKE"') do ...

:: the same line pasted at top level - now wrong
adb shell dumpsys power ^<nul 2^>nul ^| findstr /C:"WAKE"
   -> adb receives:  dumpsys power <nul 2>nul | findstr /C:WAKE
   -> the ANDROID shell runs that, and has neither findstr nor a nul device
```

The rule has one exception, and it breaks code in the opposite direction: **inside double
quotes a caret escapes nothing.** cmd already treats a quoted `|` as text, and the caret is
handed on literally. A `for /f` that runs `powershell -Command "a | b"` needs no caret, and
`"a ^| b"` gives PowerShell a stray `^` argument - measured: `A positional parameter cannot
be found that accepts argument`, and no output. Escape the operators cmd can see; leave the
ones inside quotes alone.

**Detection.** Grep for a caret-escaped operator on a line that is not a `for /f` IN
clause - `^\s*[a-z].*\^[|<>]`, excluding `for /f` lines. Every hit is either this bug or a
deliberate literal. Inside a `for /f` clause, check the other way round: a `^` between
double quotes is a bug.

**Fix.** Drop the carets so the operators are real again - or better, where the far side can
do the work, filter there:

```bat
adb shell "dumpsys power 2>/dev/null | grep -E 'PARTIAL_WAKE_LOCK'" <nul
```

---

## 33. `::` comments inside a ( ) block

**Symptom.** `The system cannot find the drive specified.` printed once or twice from a
block that otherwise behaves - or the whole script aborting with `) was unexpected at this
time.`

**Cause.** `::` is not a comment keyword - it is a label that can never be jumped to.
Inside a parenthesised block, the line after a label is always parsed as a command.
Measured:

| Inside the block | Result |
|---|---|
| one `::` line, then a command | harmless |
| two `::` lines in a row | the second runs as a command - `::` looks like a drive, so: `The system cannot find the drive specified.` |
| `::` directly before the closing `)` | the `)` is parsed as the command: `) was unexpected at this time.` and the script aborts |

**Detection.** Lintable, and now checked: `analyze_batch.py` reports `comment-in-block`
(WARN) for a `::` line while the block simulation says depth is non-zero. Guarded by
`tests/callfall_regression.cmd`. It flags every `::` in a block, the harmless single line
included: that one breaks as soon as someone adds a second comment line or deletes the
command below it, and `rem` has no such rule.

Reading block depth from the *parser simulation* rather than from indentation is the whole
trick, and it is not optional: plenty of correct `::` lines are indented under the
`if not X goto skip` idiom, which is not a block at all. A first attempt at this check used
indentation as the signal and returned a page of noise. On a real 8700-line script the
depth-based rule found ten genuine instances and zero false positives.

**Fix.** Use `rem` inside blocks - on a line of its own, and not in a block that is piped
(pitfall 54: a `rem` runs to the end of the line, `)` included, and a piped block is folded
onto one line) - or hoist the comment above the block, which usually reads better anyway
and is safe everywhere:

```bat
:: the explanation lives out here...
if not "%_fail%"=="0" (
    rem ...and rem is what goes in here
    echo   Failures listed below:
)
```

---

## 34. `findstr /x` and `$` fail on LF-only input

**Symptom.** An exact-match filter matches nothing at all, so every lookup reports
"absent". Substring matching over the same data works fine.

**Cause.** Not what it looks like: findstr *does* split LF-only input into lines. `^`
anchors match, `/n` numbers every line, and a substring search finds what you expect. What
it will not do is **end** a line: `$` matches only a position immediately before a CR, and
`/x` is the same as `^` plus `$`. On LF-only input there is no CR, so both fail on every
line. Piped output from a cross-platform tool - adb, ssh, git, WSL - arrives exactly that
way.

Measured on `abc<LF>def<LF>ghi<LF>` against the same text with CRLF:

| search | LF-only | CRLF |
|---|---|---|
| `/n "."` (line count) | 3 lines | 3 lines |
| `/c:"def"` (substring) | match | match |
| `/r /c:"^def"` | match | match |
| `/r /c:"def$"` | **no match** | match |
| `/x /c:"def"` | **no match** | match |

One wrinkle worth knowing before you test this by hand: redirected and piped input can pick
up a trailing CRLF that the source does not have, so the **last** line may match `/x` when
none of the others do. That is what makes the failure look intermittent rather than total.

The trap is that the naive fix makes it worse. Given a substring match with a
prefix-collision bug (`com.foo` matching the line for `com.foobar`), tightening it to `/x`
looks like a one-character fix - and on an LF-only stream it converts a *false positive*
into *every lookup failing*, which is the more damaging direction.

**Detection.** Check the bytes before trusting an anchored match - count CR against LF in
the captured output rather than assuming.

**Fix.** Normalise to CRLF first, then anchor. `find /v ""` re-terminates every line:

```bat
:: exact, and correct under both LF-only and CRLF
adb shell pm list packages < nul 2>nul | find /v "" | findstr /x /c:"package:%PKG%" >nul
```

Measured both ways: `/x` alone matched nothing on LF-only input; with `find /v ""` in
front it matched correctly under both.

---

## 35. A variable named like a dynamic one shadows it

**Symptom.** `%CD%` stops being the current directory - for the rest of the run, and inside
every child process the script starts.

**Cause.** `CD`, `DATE`, `TIME`, `RANDOM`, `ERRORLEVEL` and friends are *dynamic*
pseudo-variables: cmd synthesises them only when no real environment variable of that name
exists. `set "CD=320"` creates a real one, and it wins from then on - and being a genuine
environment variable, it is inherited:

```bat
set "CD=320"
echo %CD%                :: 320
cmd /c echo %%CD%%       :: 320  - the child sees it too
```

A menu that reads a DPI into `CD`, or a diff screen that reads a choice into `cd`, does
exactly this. It is usually latent - nothing in the script reads `%CD%` as a path - which
is what makes it a trap for whoever edits it next, or for a generated script that runs in a
child process and does.

**Detection.** Grep the script's scratch-variable names against the dynamic list.

**Fix.** Rename. `CDPI`, `ckd` - anything not on that list.

---

## 36. A piped validator never sees the value it is validating

**Symptom.** A charset check that "allows nothing but digits and dots" accepts
`1.1.1.1&some-command` — *and runs the command*. The validator returns "valid" and the
injected text has already executed. Reachable from a typed prompt and from any file the
script parses.

**Cause.** cmd runs each side of a pipe in a **child process**, and it builds that child's
command line from the *already-expanded* text — which the child then parses again,
operators and all. Delayed expansion does not protect it: `!v!` is substituted before the
child line is built, so the `&` arrives as an operator.

```bat
set "v=1.1.1.1&some-command"
echo(!v!| findstr /r /x /c:"[0-9.]*" >nul   :: child runs: echo(1.1.1.1 & some-command
                                            :: findstr is handed a clean "1.1.1.1" -> valid
```

The value never reaches `findstr` at all. A comment claiming "no metacharacter can survive
this" is exactly the shape to distrust — the metacharacter is consumed one layer earlier.

**Detection.** Grep for a variable echoed into a pipe: `echo(!v!|`, `echo %v%|`. Any
*validation* built that way is suspect; piping a **literal** is fine.

**Fix.** Validate in-shell, with no child. `for /f "delims=<allowed>"` yields a token only
when the string contains a character that is *not* a delimiter, and the value stays quoted
inside the `( )` set, so it is data throughout. Give it an `eol=` that is one of the allowed
characters, or everything after a `;` walks straight through it — **pitfall 48**, which is
the hole this exact snippet used to have:

```bat
set "_bad="
for /f "eol=0 delims=0123456789." %%X in ("!v!") do set "_bad=1"
if defined _bad exit /b 1
if not defined v exit /b 1      :: an empty value produces no token either
```

When a real regex is unavoidable, write the value to a file first and point `findstr` at
the file — the redirect happens in this shell, where the value is inert.

**Retrofitting a script that already has dozens of these.** Converting every probe is the
clean end state, but the patterns differ — plain charsets convert in a line, numeric ranges
and decimals need their range logic rewritten too, and that is real regression risk spread
across screens nobody is going to re-test by hand. The cheaper move is to put a *pipe-free*
gate in front of the existing probe:

```bat
call :_safechk VAL || goto bad      :: rejects & | < > and " using only quoted string compares
echo(!VAL!| findstr /r /x /c:"..." >nul || goto bad
```

Once the gate has run, the value provably cannot contain a metacharacter, so the pipe below
it is safe and the regex keeps working unchanged. On a 8700-line menu script this closed ten
prompts in ten one-line insertions, with the guard helper already written and proven at
seven other call sites.

The analyzer recognises this shape. `check_pipe_validate` resolves such helpers out of the
file (not by name): a routine that rejects each of `&`, `|`, `<`, `>` by quoted comparison —
`if not "!%~1:&=_!"=="!%~1!" exit /b 1` and so on — **and** strips and compares the double
quote. A probe on a variable such a helper has just cleared, within the same routine, is not
reported. A helper missing any one of the five does not count, and its probes stay flagged.

The quote is on that list because of the `%VAL%` form. Measured with `1.1.1.1"`:
`echo(%VAL%| findstr ...` turns everything after the quote into echo text, so findstr never
runs, `echo` succeeds, the `||` branch is skipped and the value is accepted. The `!VAL!` form
rejects the same value, because the pipe was split before the value was substituted.

Where you can, still prefer dropping the pipe: pure batch (`for /f "eol=<allowed char>
delims=<allowed>"` over a quoted value, with the `eol=`, see pitfall 48) re-parses nothing,
so there is no list of characters to get right. Gate the many, convert the few that matter
most — the ones whose value ends up on a command line.

---

## 37. `goto` out of a `call`ed routine leaves the call stack one frame deep

**Symptom.** "Exit" stops exiting. The user picks Exit from a menu, the goodbye banner
prints — and the script resumes *inside* an action they abandoned several screens ago,
at its confirmation prompt. It takes two Exits to leave. Only happens after a particular
earlier step, which makes it look random.

**Cause.** cmd pops a call frame on `goto :eof`, on `exit /b`, on running off the end of
the file, and on a `goto` whose label does not exist — and on **nothing else**. A bare
`goto` to a label that does exist, inside a `call`ed routine, jumps away and leaves the
frame pending forever:

```bat
:RequireFile
if exist "%1" goto :eof
echo [ERROR] missing
goto MenuApps          :: <- jumps out; the frame from "call :RequireFile" is still open
```

The next `exit /b` anywhere in the script — including `:ExitScript`'s — is consumed
returning into that abandoned frame instead of ending the batch file. One stuck frame per
occurrence, and they accumulate.

**Detection.** For every label reached by `call`, check its body for a bare `goto` to a
label outside itself. Restrict the target set to the script's menu/exit labels to keep the
signal clean.

**Fix.** A subroutine returns a *status*; the caller owns the jump.

```bat
:RequireFile
if exist "%~1" exit /b 0
echo [ERROR] missing
exit /b 1

:: caller
call :RequireFile "boot.config"
if errorlevel 1 goto MenuApps
```

Returning a status is also what lets a multi-step caller (a preset, a batch run) depend on
the routine without being stranded part-way through with no summary.

---

## 38. Variable names are case-insensitive: two names differing only by case are one variable

**Symptom.** A screen renders nothing until a key is pressed. A path variable is empty at
the point of use even though the line that sets it clearly ran. A feature is silently
inert with no error anywhere.

**Cause.** cmd environment variables are case-**insensitive**. A pair that reads like two
slots — the file and the value it holds, the input and the output — is one slot, and
assigning either clobbers the other:

```bat
set "_susig=%TEMP%\sig_%RANDOM%.txt"   :: the path
set "_SUSIG="                          :: "clear the value" - actually blanks the path
```

Everything downstream then receives an empty path. In the case this came from, the empty
path was handed to a PowerShell child, whose `Out-File -FilePath $null` prompted for the
missing parameter in a **minimized** window (see pitfall 45), so the whole screen waited
on input that could not arrive.

**Detection.** Static and cheap: collect every `set "NAME=` in the script, group by
lower-cased name, and flag any group holding more than one spelling. Worth running once
over an existing script — the first run on a mature one found a second latent pair.

**Fix.** Give them distinct names, not distinct casing: `_susigf` (file) and `_susigv`
(value). The same rule covers a routine's locals versus its caller's — a `setlocal` may
shadow the collision harmlessly today and stop doing so after an edit.

---

## 39. `set /p` cannot tell EOF from Enter, so an unbounded input loop spins forever

**Symptom.** Run interactively: perfect. Run from a scheduler, a pipe that ran out, a CI
step, or plain `script.cmd < nul`: one core pinned at 100% until something kills it. No
output, no error.

**Cause.** The standard menu shape re-asks when nothing was entered:

```bat
:MenuX_ask
set /p "sel=Choose: "
if not defined sel goto MenuX_ask
```

At EOF `set /p` returns **instantly**, leaves the variable unchanged (here: still unset),
and sets errorlevel 1. On a bare Enter it does *exactly the same*. There is no signal to
distinguish them, so the loop has no exit condition at all once stdin is exhausted.

**Detection.** Find every backward `goto` whose cycle contains a `set /p` and no other way
out. A redraw does not make a cycle safe. Take the common shape where an empty or unknown
answer falls through to `goto Menu`: at EOF the redraw *is* the loop, and it runs forever with
a `cls` in it. The same goes for a "blank = back" prompt whose parent menu redraws.

**Fix.** Bounded patience rather than a guess about the terminal. Count *consecutive*
empty reads and give up once they can only be coming from an exhausted stream. At EOF the
limit is reached in milliseconds; a person would have to press Enter a hundred times without
typing anything.

Reset the count on a **real answer**, not on a screen draw. Resetting on a draw works only
while every empty answer re-asks without redrawing. In the `goto Menu` shape above, the reset
runs on every lap and the count never reaches the limit. With the reset on a real answer, one
call after every prompt covers both shapes:

```bat
set "sel=" & set /p "sel=Choose: "
call :NoInput sel || goto ExitScript
if not defined sel goto MenuX_ask

:NoInput
:: %1 = the variable set /p just filled
if defined %~1 (set "_NOIN=0" & exit /b 0)
set /a _NOIN+=1
if %_NOIN% LSS 100 exit /b 0
exit /b 1
```

`:NoInput` returns a status rather than jumping — see pitfall 37. That leaves one hole: a
prompt inside a `call`ed routine. There `goto ExitScript` runs the exit code inside the call,
and its `exit /b` returns to the caller, which carries on. `exit` without `/b` stops
everything, but it also closes the console the user started the script from. To stop every
batch level at once and leave that console open, end with a deliberate syntax error:

```bat
:ExitScript
echo [ERROR] No input - stdin looks closed.
call :_halt 2>nul
exit /b 1
:_halt
()
```

Measured both ways from a nested `call`. After the syntax error nothing more of the script ran
and the interactive cmd took its next command. After `exit` the interactive cmd was gone.
The `exit /b 1` is never reached. It stops the routine visibly falling into `:_halt`, which
`analyze_batch.py`'s `call-fallthrough` check reports.

---

## 40. `shift` renumbers `%0`, so `%~dp0` stops naming the script

**Symptom.** Bundled files are looked for in `C:\` instead of beside the script. Every
"file not found" is a lie about where it looked. Appears the moment the script is given
*any* argument — including an internal relaunch marker it passes to itself.

**Cause.** `shift` renumbers **all** parameters, `%0` included. After one shift, `%0` is
whatever argument moved into slot 0, and `%~dp0` of `/preset:light` is just the current
drive root.

```bat
:parse
if "%~1"=="" goto done
shift
goto parse
:done
set "SCRIPT_DIR=%~dp0"     :: no longer this script
```

**Detection.** Any `%~dp0` / `%~f0` / `%0` textually *after* a `shift` in the same script.

**Fix.** Capture the script's own location at the very top, before anything parses
arguments, and use the captured value everywhere afterwards:

```bat
set "SCRIPT_DIR=%~dp0"
set "_SELFPATH=%~f0"
```

---

## 41. errorlevel is clobbered by the next command — and `del` always clears it

**Symptom.** A guard that "trusts the child's exit code" never fires. The line reads
correctly and is dead: the failure branch it protects is unreachable.

**Cause.** `errorlevel` holds whatever the last command that *sets* it left there. External
programs always set it; many internal commands reset it to 0 on success, but not all —
`echo` leaves it alone. `del` in particular returns 0 whether or not it deleted anything —
verified for both a missing and an existing file. So an intervening cleanup silently
resets the code being tested:

```bat
powershell -Command "...; exit 1"
if errorlevel 1 del "%out%" >nul 2>&1   :: del succeeds -> errorlevel now 0
if errorlevel 1 goto :failed            :: dead line, can never fire
```

Only the `if not exist` that follows was doing any work — which is fine until the `del`
itself is blocked (antivirus holding a freshly written file), at which point a partial
download installs.

**And the file extension changes the answer.** In a `.cmd` file — but not a `.bat` — the
internal commands `set`, `path`, `prompt`, `assoc`, `ftype` and `dpath` reset errorlevel to
**0** on success. Measured, after `cmd /c exit 7`: in `x.bat` all six leave errorlevel at 7;
in `x.cmd` all six make it 0, while `echo` and `rem` leave it alone in both. (SS64 documents
the same list, sourced to Mark Zbikowski.) So a script that reports failures correctly as
`.bat` reports every one of them as success the day it is renamed `.cmd`:

```bat
some.exe
set "_stage=post-run cleanup"      :: in a .cmd this alone clears the code
if errorlevel 1 goto :failed       :: dead line in a .cmd, live in a .bat
```

The capture below is immune to it — `%errorlevel%` is expanded before the `set` runs — which
is one more reason to branch on the copy rather than on the live value.

**Detection.** Two consecutive `if errorlevel` tests with any command between them; and in a
`.cmd`, any `set` between the command and its check.

**Fix.** Capture the code the instant it matters, then branch on the copy:

```bat
powershell -Command "..."
set "_rc=%errorlevel%"
if not "%_rc%"=="0" del "%out%" >nul 2>&1
if not "%_rc%"=="0" goto :failed
```

---

## 42. `set /a` is 32-bit signed: it saturates a variable but errors on a literal

**Symptom.** An idempotence check decides two clearly different values are equal and skips
a write. Or a running total silently stops accumulating one item.

**Cause.** `set /a` is 32-bit **signed**, and it fails in two different ways depending on
where the out-of-range number comes from:

```bat
set /a x=4294967295          :: "Invalid number." - x is not assigned (keeps any old value)
set "v=4294967295"
set /a x=v                   :: saturates: x = 2147483647
```

Dereferencing saturates at `INT_MAX`; a literal errors and assigns nothing. So any two
values at or above 2^31 compare *equal* after `set /a`, and a large literal drops the
whole term.

**Detection.** Any `set /a` whose operand can exceed 2^31 — DWORD registry data
(`0xffffffff` is 4294967295), byte counts, sizes in bytes.

**Fix.** Keep the units small enough to fit (sum kilobytes, not bytes), stage the value
through a **variable** so an oversized input caps rather than vanishes, and when equality
above 2^31 actually matters, fall back to comparing the raw text:

```bat
if "!_cur!"=="2147483647" if "!_tgt!"=="2147483647" (
    if /i not "!_curtok!"=="!_data!" goto :write     :: both saturated - compare as text
)
```

---

## 43. A missing `for /f` token expands to empty, not to nothing

**Symptom.** A "rebuild it and compare" validator accepts a malformed value — `1.2.3.`
passes an IPv4 check that splits on dots and reassembles four parts.

**Cause.** With `tokens=1-4`, a token that does not exist is substituted with an **empty
string**, not left as literal text and not skipped. So the rebuild of a three-part value
is `1.2.3.` + empty = `1.2.3.` — identical to the input, and the check passes:

```bat
for /f "tokens=1-4 delims=." %%a in ("1.2.3.") do (
    if "%%a.%%b.%%c.%%d"=="1.2.3." echo looks like four parts   :: it is three
)
```

**Detection.** Any rebuild-and-compare that does not separately require the last token to
be non-empty.

**Fix.** Require the final token explicitly, first, and chain the rest onto it so the
later tests never see an empty operand:

```bat
for /f "tokens=1-4 delims=." %%a in ("!v!") do ^
  if not "%%d"=="" if "%%a.%%b.%%c.%%d"=="!v!" if %%a LEQ 255 set "_ok=1"
```

---

## 44. `2>nul` cannot suppress a failed redirection

**Symptom.** A logging helper prints `The system cannot find the path specified.` on every
call — dozens of lines per run — and no amount of `2>nul` on the line silences it. The
real output is buried.

**Cause.** When the redirection itself cannot be set up, the message comes from the
**command processor** while it is preparing the redirect — *before* the command's own
stderr exists. So the command's stderr redirection has nothing to do with it. Verified:
neither trailing `2>nul` nor putting the redirections first suppresses it.

```bat
>>"%LOGFILE%" echo hello              :: folder missing -> error to the console
>>"%LOGFILE%" echo hello 2>nul        :: same
>>"%LOGFILE%" 2>nul echo hello        :: same
```

**Detection.** Review rule: every redirect target whose folder the script does not create
itself, or creates somewhere that can fail — a folder under Documents is exactly what
Controlled Folder Access guards. At runtime the tell is one identical error line per write.

**Fix.** Redirect the **call**, not the command. Move the write one level deeper and put
`2>nul` on the `call` — that scope does cover it, and unlike `( ... ) 2>nul` it introduces
no parenthesised block for a `)` in the path or the message to close early (pitfall 6):

```bat
:Log
set "_LOGLN=%~1"
call :_LogWrite 2>nul
goto :eof

:_LogWrite
>>"%LOGFILE%" echo [%date% %time%] !_LOGLN!
goto :eof
```

Better still, verify the directory once at startup and say so, rather than failing per
call — a missing log folder usually means the backup folder is missing too.

---

## 45. A hidden PowerShell child that prompts hangs the parent forever

**Symptom.** A screen draws its header and then nothing. Output appears only after the
user types something. `start /min /wait` never returns.

**Cause.** A cmdlet given `$null` for a **mandatory** parameter does not fail — PowerShell
*prompts* for it. `$ErrorActionPreference='SilentlyContinue'` does not suppress a
parameter prompt. Under `start "" /min /wait` the prompt is drawn in a minimized window
nobody is looking at, and the parent blocks on `/wait` indefinitely:

```powershell
$sg | Out-File -FilePath $env:PT_SIG   # env var unset -> $null -> "Supply values for..."
```

An empty *string* errors instead (and is swallowed), so this only bites when the variable
is genuinely unset — which is why a case-collision (pitfall 38) or a typo'd hand-off name
produces a hang rather than an error.

**Detection.** Every environment variable a child depends on should be set immediately
before the `start` line, and any cmdlet taking a path from `$env:` should be guarded.

**Fix.** Guard the call on the value being present, so a missing hand-off degrades to
"skipped" instead of "hung":

```powershell
if($env:PT_SIG){ $sg | Out-File -FilePath $env:PT_SIG -Encoding ASCII }
```

When testing such a child, run the harness once with stdin attached (not `< nul`) — the
redirect makes a prompt fail instantly and hides exactly this bug.

---

## 46. PowerShell 5.1 reads a UTF-8 `.ps1` without a BOM as ANSI

**Symptom.** Em dashes and arrows in a generated file come out as `â€"` / `Ã¢â‚¬`. The
script that wrote them looks correct in every editor.

**Cause.** Windows PowerShell 5.1 assumes the **ANSI** code page for a `.ps1` with no BOM.
Every non-ASCII literal in the script is therefore already mojibake by the time it is a
string in memory; writing it back as UTF-8 encodes the mojibake faithfully. The same
asymmetry bites `Get-Content` on a UTF-8-no-BOM *data* file.

The companion hazard is `Set-Content -Encoding ascii`, which maps every non-ASCII
character to `?` — a one-line command can flatten every dash and arrow in a document.

**Detection.** Any non-ASCII character in a `.ps1`; any `-Encoding ascii` writing a file
that is not required to be ASCII.

**Fix.** Keep `.ps1` files pure ASCII and hold the non-ASCII text in a UTF-8 data file
read with `[System.IO.File]::ReadAllLines`, which honours UTF-8 regardless of BOM. Write
with an explicit encoding object rather than a name:

```powershell
[System.IO.File]::WriteAllLines($path, $lines, (New-Object System.Text.UTF8Encoding($false)))
```

Before any bulk rewrite of a text file, check what it actually contains — and take a copy.
A round-trip through the wrong encoding is not detectable afterwards from the result alone.

---

## 47. `cd` into a tool folder does not put it on PATH

**Symptom.** A script that ships its own helper binary in a subfolder reports the binary as
missing on *some* machines, while working everywhere the author tested. The error message
sends the user off to install a tool they already have, sitting right there in the folder.

**Cause.** The usual shape is `if exist tools\ cd tools` followed by bare `tool.exe ...`
calls. That resolves only because cmd searches the **current directory** before PATH - and
that behaviour is switchable. When `NoDefaultCurrentDirectoryInExePath` is set (hardened
builds and managed enterprise images do set it) the current directory is dropped from the
search, and every bare call fails at once.

It fails *totally*, which is the confusing part: not one feature degrading, but the very
first probe reporting the tool absent, so the script never starts.

**Detection.** Grep for a `cd` into a bundled folder followed by bare invocations of a
binary that lives there. Reproduce it directly - the variable is honoured per-process, so
setting it in the parent shell is enough:

```bat
set "NoDefaultCurrentDirectoryInExePath=1"
call your_script.cmd          :: bundled tool now "not found"
```

**Fix.** Say where the tool is instead of relying on the search order. One line covers
every later call, however many there are:

```bat
if exist tools\ cd tools
:: %CD% is correct here because this is a TOP-LEVEL statement - cmd expands it when the
:: line runs, i.e. after the cd. Inside a ( ) block it would expand at parse time and
:: still name the old directory, which is the classic way to "fix" this and change nothing.
if exist tool.exe set "PATH=%CD%;%PATH%"
```

Capturing the full path once (`set "TOOL=%CD%\tool.exe"`) and calling `"%TOOL%"` is the
stricter form and worth it for a handful of call sites; the PATH line is what you want when
the script already has hundreds of bare calls, because it fixes them all without touching
any of them.

---

## 48. A `for /f "delims=<allowed>"` validator passes anything after a `;`

**Symptom.** A charset check that "allows nothing but digits and dots" accepts
`1.1.1.1;&whatever` and hands it on. The same validator rejects `1.1.1.1&whatever`, so it
looks like it works — the hole is exactly one character wide and nobody types it by accident.

**Cause.** `for /f` reads its input as *lines*, and it ignores a line whose first character,
**after the leading delimiters are skipped**, is the `eol` character. `eol` defaults to `;`.
In a validator the whitelist *is* the delimiter set, so for a value like `1.1.1.1;&x` the
loop skips every allowed character, finds the `;`, treats the rest as a comment, and never
runs its body — and the body is what sets the "bad" flag:

```bat
set "_bad="
for /f "delims=0123456789." %%X in ("!v!") do set "_bad=1"
if defined _bad exit /b 1        :: never fires for 1.1.1.1;&x
```

Measured with `delims=0123456789.`: `1.1.1.1&x` rejected, `1.1.1.1;&x` **accepted**, `;x`
**accepted**, `1.1.x;y` rejected (the `x` comes before the `;`), and an empty value accepted,
because an empty line has no token either.

**Which way it fails depends on which flag the body sets.** A loop that sets a *bad* flag
fails **open** — the shape above, and the dangerous one. A loop that sets an *ok* flag fails
**closed**: the `;` value never reaches the body, so ok is never set and the value is
rejected. Both shapes turn up in the same script, which is why testing one of them proves
nothing about the other.

**Detection.** Grep for `for /f "` … `delims=` with no `eol=` in the same options string.
Then test with a `;` **after a legal prefix** — a bare metacharacter is rejected and tells
you nothing.

**Fix.** Give the loop an `eol` that is one of the allowed characters, so it can never be the
first character after the leading delimiters:

```bat
set "_bad="
for /f "eol=0 delims=0123456789." %%X in ("!v!") do set "_bad=1"
if defined _bad exit /b 1
if not defined v exit /b 1
```

Measured with `eol=0`: `1.1.1.1;&x`, `;x` and `1.1.x;y` all rejected; `1.1.1.1` and `0.0.0.0`
still accepted. Two traps to avoid: `"eol="` does **not** reliably turn the feature off (it
takes whatever character follows, often the quote or space), and an `eol` character that is
*not* in the whitelist just moves the hole onto that character. Empty stays accepted either
way, so keep the `if not defined` line.

---

## 49. `choice` returns 0 on Ctrl+C, so an `if errorlevel 2` confirmation means Yes

**Symptom.** A destructive action runs although the user tried to abort it: they pressed
Ctrl+C at the confirmation, answered **N** to cmd's "Terminate batch job (Y/N)?", and the
action went ahead anyway.

**Cause.** Documented contract: `choice` sets errorlevel to the **index** of the key pressed
(1-based), `255` on an error, and **0 on Ctrl+C or Ctrl+Break**. A two-way confirmation
usually tests only the second index and lets Yes fall through:

```bat
choice /c:YN /n
if errorlevel 2 goto :no      :: N
:: falls through = Yes
```

`if errorlevel n` is "n or higher" (pitfall 50), so that Yes branch is really "0 or 1" — and
Ctrl+C lands in it. Declining to terminate the batch resumes at the line after `choice`,
which is the Yes path. Note the other two exits are safe here: an error (255) and a `/t`
timeout (the `/d` default's index) both satisfy `errorlevel 2`. Measured: `choice` with stdin
at EOF returns 255, i.e. the no branch.

**Detection.** For every `choice`, read the branches under it. Each index needs its own test,
and the fall-through has to be the *safe* one.

**Fix.** Test the index you want and let everything else fall to the safe side:

```bat
choice /c:YN /n
if errorlevel 2 goto :no      :: N
if errorlevel 1 goto :yes     :: Y
goto :no                      :: 0 = Ctrl+C, and anything else
```

---

## 50. `if errorlevel 1` is "1 or higher", so a negative exit code reads as success

**Symptom.** A tool that failed is reported as fine. DISM is the usual one: it returns
HRESULTs, which arrive as negative numbers.

**Cause.** `if errorlevel <n>` is documented as true when the exit code is *equal to or
greater than* n. A negative code is less than 1, so the failure branch never fires and the
`else` runs:

```bat
dism /online /cleanup-image /restorehealth
if errorlevel 1 ( echo failed ) else ( echo OK )    :: -2146498529 prints OK
```

Measured after an exit code of `-2146498529`: `if errorlevel 1` silent; `if not errorlevel 0`
fires; `if %errorlevel% neq 0` fires; `if not "%_rc%"=="0"` fires; `||` fires.

**Detection.** Any `if errorlevel 1` guarding a program that can return an HRESULT — DISM,
SFC wrappers, MSI custom actions, .NET tools that return `Marshal.GetHRForException`. Test it
with `cmd /c exit -1` rather than a real failure.

**Fix.** Compare against zero instead of ordering against 1:

```bat
some.exe
set "_rc=%errorlevel%"
if not "%_rc%"=="0" goto :failed
```

`||` is equally correct and shorter for one-liners. `if not errorlevel 0` is true only for
*negative* codes, so it catches these and misses every positive one — use it to add a second
branch, never as the only test.

---

## 51. `""` inside a helper's command string is not an escaped quote

**Symptom.** Every action whose path contains a space quietly does nothing, while the
on-screen line and the log both look correct. In the worst case one of them deletes files
somewhere else entirely.

**Cause.** A helper that takes a whole command line as `%1`, called with the inner quotes
doubled:

```bat
call :Run "del /f /s /q ""%ProgramData%\NVIDIA Corporation\Downloader\*.*"""
...
:Run
set "_cmd=%~1"
cmd /s /c "%_cmd%"
```

`%~1` removes the outer pair only, so the doubled quotes reach the child. To cmd, `""` is not
an escaped quote — it is an empty quoted string followed by a *new* quoted region, so quoting
toggles off exactly where the author wanted it on. The path is then unquoted and splits at
its first space into two names: `C:\ProgramData\NVIDIA` and `Corporation\Downloader\*.*`
(relative to the current directory).

What happens next is worth knowing precisely, because the destructive case is conditional.
Measured with `del /f /s /q`:

| the relative remainder | result |
|---|---|
| does not resolve | "The system cannot find the path specified", exit 1, **nothing deleted** |
| resolves | deletes it **and** the first name — recursively, `/s` — and exits **0** |

So the usual outcome is a command that silently does nothing while its wrapper logs OK or
FAIL; the destructive outcome needs a directory matching the text after the first space to
exist under the current directory, and then it takes the *sibling* of the intended folder
with it. External tools show the split more plainly: `wevtutil cl ""Windows PowerShell""`
reaches wevtutil as two arguments and fails outright.

**Detection.** Grep the call sites for `""` inside a quoted argument, and the helper for
`set "_cmd=%~1"` with no un-doubling. Do not judge it by the echoed line: the helper usually
prints `%_cmd%`, where the doubled quotes are still invisible to the eye.

**Fix.** Collapse the doubled quotes once, in the helper, so every existing call site is
fixed at the same time:

```bat
:Run
set "_cmd=%~1"
set "_cmd=!_cmd:""="!"      :: "" -> "
cmd /s /c "%_cmd%"
```

Measured with that line in place: the intended files were deleted and the sibling folder was
untouched. Passing the command as separate arguments and quoting them inside the helper is
the cleaner design, but it means touching every call site.

The helper has a second hazard of its own: the command reaches it as a `call` argument, so
cmd parses it a second time (pitfall 53). A `%` the command should see has to be written
`%%%%` at the call site — measured, `"echo 100%%"` arrives as `echo 100` — and a quoted `^`
arrives doubled.

---

## 52. A `set /p` prompt longer than the console line puts the caret inside the question

**Symptom.** The user starts typing and their answer appears in the *middle of the question*,
overwriting it. `Also open Windows Disk Cleanup...` becomes `Alyerergergergerg Disk Cleanup...`
after a few keystrokes. Other prompts on the same screen behave perfectly, which is what makes
it look like a problem with that one menu item.

**Cause.** cmd positions the `set /p` input caret at *(prompt length mod console width)*. When
the prompt is longer than the line it expects the text to have wrapped, so it places the caret
that far into the next row. If nothing visibly wrapped, "that far into the next row" is that
far into the row the question is still sitting on. The offsets below are measured; *why* the
text did not wrap is inferred: the window and the width cmd calculates with disagree. In the
case this came from, that began when a `mode con` call moved from before any output to after
it — a terminal that ignores the resize is the other likely way to get there.

The arithmetic is exact, which makes it confirmable from a screenshot. With
`mode con: cols=100`:

| prompt length | caret lands at |
|---|---|
| 102 | column 2 |
| 103 | column 3 |
| 106 | column 6 |
| 79 | end of the prompt — correct |

**Detection.** `analyze_batch.py` reports `prompt-width` (WARN). It reads the limit out of the
script's own `mode con: cols=N` line rather than assuming one, so it follows a change to that
line instead of going stale, and it stays silent in a script that never resizes — that script
could be running in any terminal, and guessing a width would invent findings. Colour variables
are counted as zero columns, since a prompt's variables are almost always ANSI escapes; that
can only under-estimate a prompt, so it never invents a finding that way either. Both shapes
are read, `set /p "VAR=text"` and `set /p VAR="text"`; the `set /p VAR=<file` read-from-file
idiom has no prompt and is not matched.

By hand: measure the visible text between `=` and the closing quote, and compare it against the
width the script asks for. On the script this was found in, fourteen of 111 prompts were over.

**Fix.** Keep the question short and put the explanation on its own `echo` line above it. This
is better writing anyway: the parenthetical that pushed the prompt over the limit is usually the
part the user most needs to read, and it gets a full line instead of being crammed onto the end
of a question.

```bat
rem  before - 102 columns, so the caret lands at column 2
set /p "_cm=Also open Windows Disk Cleanup (cleanmgr) for the system drive? Sincript does not wait for it. (Y/N): "

rem  after - the explanation gets its own line, the question is 70 columns
echo   Cleanup opens in its own window; Sincript does not wait for it.
set /p "_cm=Also open Windows Disk Cleanup (cleanmgr) for the system drive? (Y/N): "
```

A script that never calls `mode con` has no declared limit, so keep prompts under about 78
columns — that survives an 80-column window too.

Worth knowing when you move a `mode con` call. Resizing at the very top, before anything
prints, is what most scripts were written against; deferring it (so an unattended run does not
clear the caller's console, say) is a reasonable change on its own, but it changes when the
window and the buffer agree on a width — and in the case this came from, that was the change
that turned a cosmetic wrap into a question being typed over.

---

## 53. `call` parses its arguments a second time

**Symptom.** A restore puts back a different value from the one it backed up — and only for
some values. A ringtone URI saved as `...?title=Over%20the%20Horizon` comes back as
`...?title=Over0the0Horizon`; a value with a caret in it comes back with two. Ordinary text
round-trips perfectly, so the backup passes every test written with ordinary text. The same
happens to any value a script hands to a subroutine: `50%` arrives as `50`.

Paths are data too. A Windows user name may hold a `%` or a `^`, and every path under the
profile carries it. In a system-cleanup tool, `call :Run "del /f /s /q ""!TEMP!\*.*"""` ran,
for a user `Bo%b & Co`, on the temp folder of a user `Bob & Co`: another account's files,
deleted by an elevated script. A `call set` in the same tool's Documents capture sent the
backups and the log into that account's Documents. For `Bo^b & Co` the doubled caret named a
folder that did not exist, so nothing was cleaned, and the backup folder's `md` created
`C:\Users\Bo^^b & Co`.

**Cause.** `call` does not hand over the text it was given. It doubles every caret, then
runs the line through percent expansion and special-character parsing a second time; that
second parse reduces unquoted carets back to one, but quoted carets stay doubled. So a value
that arrives through `%var%` or `!var!` is expanded once to become an argument, and then
parsed again as if you had typed it. Measured, capturing the argument raw in the callee
(delayed expansion off, printed with `set`, so the callee adds no parse of its own):

| value in the caller | `call :cap "!v!"` delivers | handed over in a variable |
|---|---|---|
| `50%` | `50` | `50%` |
| `a^b` | `a^^b` | `a^b` |
| `%OS%` | `Windows_NT` | `%OS%` |
| `...?title=Over%20the%20Horizon` | `...?title=Over0the0Horizon` | unchanged |
| `x!y` | `x!y` | `x!y` |

It is `call` itself, not labels: `call other.cmd "!v!"` delivered `50` and `a^^b` as well,
and `call :cap "%v%"` gave the same as the `!v!` form for the first four rows. Unquoted, the
caret survives and the percent does not: `call :cap !v!` gave `a^b` and `50`. `%2` in the
URI is read as the caller's second argument, empty here. `!` survives: the second parse does
not repeat delayed expansion on the arguments. dbenham's description of cmd's parser
documents these steps as phase 6, "CALL processing/Caret doubling".

A `%` you write into a call argument yourself goes through the same second parse. Measured
in a batch file: `call :cap "echo 100%%"` delivered `echo 100`, and it took `100%%%%` to
deliver `100%` — which is how a `:Run` helper (pitfall 51) quietly loses a percent sign.

Measure it the way the table was measured. `echo %~1` in the callee parses the value once
more — and under delayed expansion also eats a `!` — so a first attempt at this table
blamed `call` for what the `echo` did.

**Detection.** `analyze_batch.py` reports `call-reparse` (WARN) for the generated-file form:
an `echo`ed `call :label` or `call x.cmd` whose arguments contain any variable expansion —
expanded now (`%v%`, `!v!`, `%~1`) or written for the generated file to expand (`%%v%%`,
`^!v^!`), since both put a value through the second parse. A bare call, literal arguments
and a variable *name* (`call :apply VAR`) are clean. Guarded by
`tests/callreparse_regression.cmd`, which holds three emitters an ADB front-end shipped,
verbatim. On the current versions of both calibration scripts, and on three older copies of
one of them, the check reports nothing.

A direct call in the script itself (`call :x "!v!"`) has the same problem, but it is a bug
only when the value can hold a `%` or a `^`, which a lint cannot know. That stays a review
rule: check every `call` whose arguments carry data the script did not write itself — a
captured value, user input, a line from a file, anything from `for /f` — and every path under
the user profile or the script's own folder (`%TEMP%`, `%LOCALAPPDATA%`, Documents, `%~dp0`),
because the user name is in it. A project's own harness can make that rule mechanical:
- rebuild the set of path variables from the script's own `set` lines, counting a variable
  filled by name (`set "x=!%~1!"`) as one of them;
- fail when any `call` argument reads one.

**Fix.** Pass by reference: put the value in a variable, `call` without it, and read it in
the callee — the same idea as pitfall 12's hand-off through the environment:

```bat
:: before - the value is parsed a second time on its way in
call :apply "!_cmd!"

:: after - nothing re-parses it
set "APPLY_CMD=!_cmd!"
call :apply
...
:apply
setlocal EnableDelayedExpansion
adb shell "!APPLY_CMD!" <nul
endlocal
exit /b
```

In a generated file, emit the same two lines — `set "APPLY_CMD=<value>"`, then
`call :apply` — and do the one escape left, for the file's own percent pass: write each `%`
as `%%`. Refuse a value that holds a `"` (pitfall 27). Undoing the doubling inside the
callee (`!v:^^=^!`) is the fragile alternative: it cannot know how many `call`s the value
went through, and it cannot bring back a `%` that is already gone.

**A helper that many callers share** takes the variable's NAME and reads it late. The
argument is then a name, which the second parse cannot damage:

```bat
set "_msg=Backup written: !_bkp!"
call :LogVar _msg
...
:LogVar
setlocal EnableDelayedExpansion
set "_line=!%~1!"
>>"!LOGFILE!" echo [%date% %time%] !_line!
exit /b
```

A `:Run` helper (pitfall 51) needs the same treatment inside it. If it logs its command with
`call :Log "EXEC: !_cmd!"`, the log loses the `%` even when the command itself is safe.

**A child `cmd` parses once more.** A `:Run`-style helper that executes its command with
`cmd /s /c "!_cmd!"` has the child parse that command line again. A single `%` and a quoted `^`
survive this: measured, a delete in a folder `Bo%b^x!y & (z)` came through. A `%NAME%` pair
that names a defined variable is expanded, though: measured, a delete in a folder `a%OS%b`
missed. To avoid that, let the child expand the command itself:

```bat
cmd /d /v:on /s /c "^!_cmd^!" >nul 2>&1
```

Here is how that works:
- `/v:on` turns on delayed expansion in the child.
- The parent's own delayed expansion turns the quoted `^!` into a plain `!`, so the child
  receives the literal `!_cmd!`.
- The child inherits `_cmd` with the rest of the environment, and expands it after its own
  parse. No character of the value is parsed at all.

Inside quotes one caret does it. Unquoted it takes `^^!`, and two carets inside quotes break
it: measured, `"^^!x^^!"` printed `"^"`.

The cost is that pipes, redirects and `&&` inside the variable are now plain text
(`echo a| findstr a` just echoed the line). Keep commands that need operators on a
re-parsing path, and give them no outside data. Measured exit codes match `cmd /s /c`: 0 on
success, 1 for a missing folder and for a failing command.

**`call set` is the same second parse.** `call set "X=%X%"` expands the references inside a
value, such as a registry answer `%USERPROFILE%\Documents`. It also re-parses a value that is
already expanded, which loses its `%` and doubles its `^`. Give it only the values it is for:

```bat
if "%DOCS:~0,1%"=="%%" call set "DOCS=%DOCS%"
```

**Test with the value outside the driver.** A test driver that writes the path into its own
text runs its own percent pass first, and loses the `%` before the code under test ever sees
it. Hand the value in through an environment variable that the harness sets. In the driver,
read it as `%USERPROFILE%` with delayed expansion off, or as `!V!`.

---

## 54. An inline `rem` comments out the rest of the line — `&`, `|` and a block's `)` included

**Symptom.** Three failures that look unrelated:

- A command after a comment on the same line never runs: `echo x & rem note & goto :next`
  falls through instead of jumping.
- A one-line block with a comment in it - `if defined _cfg (call :apply & rem see :apply)` -
  and the rest of the script is gone: nothing after that line runs, no message, exit code
  255.
- A `( ... ) | findstr` block with a `rem` line in it prints nothing at all, while the same
  block redirected to a file works.

**Cause.** `rem` is not an ordinary command whose text ends at a separator. cmd recognises
it while it parses the line and treats everything after it, to the end of the line, as the
comment - `&`, `|`, `)` and redirects included. `echo` is the other way round (pitfall 27):
its text ends at the first unquoted `&`, `|` or `)`. Measured, each case in its own file
under `cmd /d /c`:

| Line(s) | Result |
|---|---|
| `echo first & rem note & echo X` | prints `first` and nothing else |
| `echo x & rem note \| findstr /n "^"` | prints `x` without a line number: the pipe is part of the comment |
| `(echo in-block & rem note & echo Y)` | nothing, and nothing after this line either: the `)` is part of the comment, so the block never closes. Exit 255, no message |
| `if 1==2 (` / `echo a & rem note )` / `echo b` / `)` | `b` is not printed: the eaten `)` closed nothing, and the next `)` closed the block |
| `rem closing )` or `@rem closing )` on a line of its own in a block | the `)` is comment here too and closes nothing |
| `rem.note & echo X` | prints `X`: `rem.` is a different form, and its comment does end at `&` |

A piped block is a second way into the same trap. cmd runs each side of a pipe in a new
`cmd.exe`, and it hands a block to that child as ONE line with the block's lines joined by
`&` - captured with `echo %%cmdcmdline%%` inside a piped block, the child's command line
was `cmd.exe /S /D /c" ( echo %cmdcmdline% & echo second )"`. A `rem` anywhere in the
block therefore comments out the rest of that one line, the block's closing `)` included.
The child's block never closes, and the child runs **nothing** from it, not even the lines
before the `rem`. Measured: no output, no message, and the script carries on as though the
block had worked. The same result on the right-hand side of a pipe (`echo x | ( ... )`), for
a `rem` in a block nested inside the piped one, for a `rem` on the block's last line, and in
a piped `for ... do ( ... )` body. The same block redirected to a file instead, or with the
comment moved above it, ran normally, and `||` is not a pipe: a block followed by
`|| echo failed` is not folded.

SS64's `rem` page describes the first half: a `rem` inside brackets wipes out everything
after it, the closing bracket included. Microsoft's `rem` page says a pipe or redirection
character cannot be used in a comment. SS64's delayed-expansion page says both sides of a
pipe run in a new `cmd.exe`. The fold, and what a `rem` does to it, are from the
measurements above.

**Detection.** `analyze_batch.py` reports both from its block simulation, as ERRORs:

- `rem-eats-paren` - an inline `rem` inside an open block whose comment holds a `)` that is
  not the comment's own (a comment's own balanced `( )` is fine). A line-leading
  `rem x )` eats its `)` as well, but nobody meant that one to close anything, so it is
  not reported.
- `rem-in-piped-block` - any `rem`, line-leading or inline, in a block on either side of a
  single `|`, nested blocks included. A redirect between the `)` and the pipe
  (`) 2>&1 | more`) does not hide it; `||` does not count.

A `goto` or `call` after an inline `rem` is not a jump, and the jump scan knows it
(pitfall 27). Guarded by `tests/rem_regression.cmd`, with a SAFE twin for each shape a
careless version would flag. On the current versions of both calibration scripts, and on
two older copies of one of them, both checks report nothing - and neither script has a
piped block, so the pipe rule is exercised only by the fixture.

**Fix.** Put the comment on a line of its own, or above the block. Never put a `rem` after a
command inside a block, and never put one anywhere in a block that is piped:

```bat
:: before - the rem eats the ')', and nothing after this line ever runs
if defined _cfg (call :apply & rem see :apply for the format)

:: after
rem see :apply for the format
if defined _cfg (call :apply)

:: before - the child runs nothing from this block
(
    rem list every service
    sc query state= all
) | findstr /i "SERVICE_NAME"

:: after - the comment is outside the block
rem list every service
(
    sc query state= all
) | findstr /i "SERVICE_NAME"
```

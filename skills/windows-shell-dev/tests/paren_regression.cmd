@echo off
rem ============================================================
rem  Regression fixture for check_blocks in analyze_batch.py.
rem  A line whose text contains MUSTFLAG must be reported
rem  block-paren-literal; a line containing MUSTERR must be
rem  reported block-early-close. Every other line stays clean.
rem  Guards: single-line + cross-line carry, the set/call
rem  broadening (Gap A), quoted-if tracking (Gap B), and the
rem  false-positive traps that broadening exposed.
rem ============================================================

rem --- FLAG: single-line echo paren in a bare output block ---
(
    echo single MUSTFLAG (deci C)
) > "%TEMP%\rx1" < nul

rem --- FLAG: cross-line pair (open on one echo, close on the next) ---
(
    echo opens a paren here (start
    echo closes it MUSTFLAG)
) > "%TEMP%\rx2" < nul

rem --- FLAG: unquoted set with parens in a block (Gap A) ---
if 1==1 (
    set RXVAL=MUSTFLAG (nope)
    echo tail
)

rem --- FLAG: call with a paren arg in a block (Gap A) ---
if 1==1 (
    call :rxsub MUSTFLAG (arg)
    echo tail
)

rem --- FLAG: paren bug inside a QUOTED-if block (Gap B) ---
if "%OS%"=="Windows_NT" (
    echo quoted-if MUSTFLAG (first 15)
    echo tail
)

rem --- FLAG + ERR: paren closes early AND an illegal token follows ---
if 1==1 (
    echo detail MUSTFLAG MUSTERR (first 15): tail
    echo tail
)

rem --- SAFE: escaped parens in a block ---
(
    echo escaped ^(deci C^) stays clean
) > "%TEMP%\rx3" < nul

rem --- SAFE: quoted set with parens ---
if 1==1 (
    set "RXOK=C:\Program Files (x86)\bin"
    echo clean
)

rem --- SAFE: parens in a top-level echo (no block) ---
echo top level (fine) no block

rem --- SAFE: legit one-line block with two commands ---
if 1==1 ( echo a & echo b )

rem --- SAFE: quoted-if clean body (the false-positive trap) ---
if "%X%"=="0" ( echo clean ) else ( echo also clean )

rem --- SAFE: for-in structural parens ---
(
    for %%i in (a b c) do echo got %%i
) > "%TEMP%\rx4" < nul

goto :done
:rxsub
exit /b
:done

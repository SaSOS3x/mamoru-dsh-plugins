@echo off
rem ============================================================
rem  Regression fixture for check_labels' call-fallthrough rule
rem  and check_blocks' comment-in-block rule in analyze_batch.py.
rem
rem  A line under "rem --- FLAG-CF:" must be reported
rem  call-fallthrough; a line under "rem --- FLAG-CB:" must be
rem  reported comment-in-block. Nothing else may be flagged.
rem
rem  The pairing is the point: call :x directly above :x runs
rem  the routine twice and its exit /b then kills the batch, but
rem  the same call with a goto in between - or with real work
rem  between it and the label - is correct and must stay clean.
rem ============================================================

rem --- FLAG-CF: call sits directly above its own label
call :orphan

:orphan
echo in orphan
exit /b 0

rem --- CLEAN: a goto jumps past the routine
call :guarded
goto after_guarded

:guarded
echo in guarded
exit /b 0

:after_guarded

rem --- CLEAN: the call transfers control on the same line
call :cond_a || goto after_cond

:cond_a
echo in cond_a
exit /b 1

:after_cond

rem --- CLEAN: real work between the call and the label
call :spaced
echo work happens here

:spaced
echo in spaced
exit /b 0

rem --- CLEAN: echoed text that merely mentions a call
echo call :orphan

if 1==1 (
rem --- FLAG-CB: :: comment inside an open block
:: this line makes cmd complain about a drive
    echo inside the block
)

rem --- CLEAN: rem inside a block is fine
if 1==1 (
    rem this is the correct form
    echo also inside
)

rem --- CLEAN: :: at top level, outside any block
:: perfectly normal comment

rem --- CLEAN: :: indented under the goto-skip idiom (not a block)
if not "%1"=="x" goto skip_it
    :: indented, but no block is open here
    echo skipped path
:skip_it

exit /b 0

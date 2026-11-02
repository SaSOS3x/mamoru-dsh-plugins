@echo off
rem ============================================================
rem  Regression fixture for check_labels' echoed-text handling
rem  (strip_echoed) in analyze_batch.py.
rem  A line whose text contains MUSTERR must be reported
rem  goto-undefined or call-undefined. Every other line stays
rem  clean. The marker lives in the target name, so the line
rem  itself is a genuine dangling jump.
rem
rem  The pairing is the point: a .bat that GENERATES a .bat is
rem  full of `echo goto :x` - data, not control flow - but
rem  `echo hi & goto :x` really does jump and must still fire
rem  (while `echo hi ^& goto :x` is an escaped ampersand - literal
rem  text, no jump). A rem is the opposite of an echo: NOTHING ends
rem  it, so `echo x & rem note & goto :x` never jumps (measured).
rem ============================================================

rem --- ERR: plain dangling jumps -----------------------------
goto :MUSTERR_one
call :MUSTERR_two

rem --- ERR: echo stops at a separator, the jump after is real -
echo hi & goto :MUSTERR_three
echo. & call :MUSTERR_four
if 1==1 (echo x) else goto :MUSTERR_five
call :lorem x & goto :MUSTERR_six
>nul 2>&1 call :MUSTERR_seven
echo(text| findstr x >nul || goto :MUSTERR_eight

rem --- CLEAN: echoed text written into a generated script -----
echo goto :not_a_jump
echo call :not_a_call
>>"%OUT%" echo call :dcx_do settings put global k "v"
(
    echo goto :dcx_report
    echo :dcx_do
    echo goto :eof
    echo :dcx_report
) > "%OUT%"
echo Use goto :menu to go back
echo ok & rem call :not_a_call_rem
echo x & rem note & goto :not_a_jump_after_rem
echo x & rem note | call :not_a_call_after_rem
call :lorem ipsum
@rem goto :not_a_jump_atrem
echo(goto :not_a_jump_paren
echo.

rem --- CLEAN: jumps that resolve -----------------------------
goto :real_label
call :real_label

:real_label
exit /b 0

rem "rem" inside a label name is not a rem: :lorem is a real target, and the jump after
rem `call :lorem x &` above is live.
:lorem
exit /b 0

@echo off
rem ============================================================
rem  Regression fixture for check_pipe_validate (pitfall 36),
rem  check_var_case_collision (pitfall 38) and
rem  check_shift_selfpath (pitfall 40) in analyze_batch.py.
rem
rem  Convention: a line reading "rem  FLAG:<code>" means the NEXT
rem  line must be reported with exactly that code. Every other
rem  line must stay clean. Both directions are asserted, so a
rem  detector that stops firing and one that starts guessing
rem  each fail the test.
rem ============================================================
setlocal EnableDelayedExpansion

rem ------------------------------------------------------------
rem  36: a value echoed into a pipe is re-parsed by the child, so
rem      "1.1.1.1&whoami" runs whoami and hands findstr a clean
rem      "1.1.1.1" that it approves - the check is bypassed AND
rem      turned into an execution primitive.
rem ------------------------------------------------------------
set "_ipaddr=1.1.1.1"
rem  FLAG:pipe-validate
echo(!_ipaddr!| findstr /r /x /c:"[0-9][0-9.]*" >nul || exit /b 1
rem  FLAG:pipe-validate
echo %_ipaddr%| findstr /i "1" >nul && set "_hit=1"

rem  negative: a literal has nothing left to re-expand, and a
rem  variable on the RIGHT of the pipe is an argument, not input.
echo 1.1.1.1| findstr /i "1.1.1.1" >nul
type "%TEMP%\hosts.txt" | findstr /i "%_ipaddr%" >nul

rem ------------------------------------------------------------
rem  38: cmd variable names are case-INSENSITIVE, so a pair that
rem      reads like "the file" and "the value it holds" is one
rem      slot and the second assignment blanks the first.
rem      Reported on the first spelling seen.
rem ------------------------------------------------------------
rem  FLAG:var-case-collision
set "_sigfile=%TEMP%\sig.txt"
set "_SIGFILE="

rem  negative: matched case is an ordinary set-then-clear.
set "_scratch=1"
set "_scratch="

rem ------------------------------------------------------------
rem  40: shift renumbers ALL parameters including %0, so %~dp0
rem      afterwards is resolved from an argument (the current
rem      directory, or the drive root for a /switch) rather than
rem      the script, and every bundled file is then looked for in
rem      the wrong place. Everything below the shift is in scope.
rem ------------------------------------------------------------
:parse
if "%~1"=="" goto parsed
shift
goto parse
:parsed
rem  FLAG:shift-selfpath
set "SCRIPT_DIR=%~dp0"
rem  FLAG:shift-selfpath
call "%~dp0helper.cmd"

rem  negative: %%~dp0 is DOUBLED, which writes a literal %~dp0
rem  into the generated batch file, where it means THAT file's
rem  directory. Emitted text is data, not code (pitfall 27).
>"%TEMP%\gen.bat" echo start "" "%%~dp0app.exe"
exit /b 0

rem  ---- pipe-validate: a script may neutralise the value instead of dropping
rem  the pipe.  A helper that rejects every one of & | < > by quoted comparison
rem  counts as a guard, and a probe on a variable it has cleared is not a
rem  finding.  Both halves are load-bearing: guarded must stay silent, and the
rem  very next probe on an UNguarded variable must still fire.
call :_mchk GUARDED || goto :eof
echo(!GUARDED!| findstr /r /x /c:"[0-9][0-9]*" >nul || goto :eof
rem  FLAG:pipe-validate
echo(!UNGUARDED!| findstr /r /x /c:"[0-9][0-9]*" >nul || goto :eof
rem  negative: the guard covers only three of the four metacharacters, so it
rem  does NOT count and the probe after it is still a finding.
call :_weakchk PARTIAL || goto :eof
rem  FLAG:pipe-validate
echo(!PARTIAL!| findstr /r /x /c:"[0-9][0-9]*" >nul || goto :eof
exit /b 0

:_mchk
set "_mq=!%~1!"
set _mz=!_mq:"=!
if not "!_mz!"=="!_mq!" exit /b 1
if not "!%~1:&=_!"=="!%~1!" exit /b 1
if not "!%~1:|=_!"=="!%~1!" exit /b 1
if not "!%~1:<=_!"=="!%~1!" exit /b 1
if not "!%~1:>=_!"=="!%~1!" exit /b 1
exit /b 0

:_weakchk
if not "!%~1:&=_!"=="!%~1!" exit /b 1
if not "!%~1:|=_!"=="!%~1!" exit /b 1
if not "!%~1:<=_!"=="!%~1!" exit /b 1
exit /b 0

rem  negative: :_noq covers all four operators but never strips a quote, so a
rem  value like 1.1.1.1^" still puts the pipe inside a quoted region and the
rem  probe silently approves it.  That is not a guard.
call :_noq NOQ || goto :eof
rem  FLAG:pipe-validate
echo(!NOQ!| findstr /r /x /c:"[0-9][0-9]*" >nul || goto :eof
exit /b 0

:_noq
if not "!%~1:&=_!"=="!%~1!" exit /b 1
if not "!%~1:|=_!"=="!%~1!" exit /b 1
if not "!%~1:<=_!"=="!%~1!" exit /b 1
if not "!%~1:>=_!"=="!%~1!" exit /b 1
exit /b 0

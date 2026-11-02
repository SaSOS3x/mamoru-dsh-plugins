@echo off
rem ============================================================
rem  Regression fixture for check_shift_selfpath in
rem  analyze_batch.py. A line under "rem --- FLAG:" must be
rem  reported shift-selfpath. Nothing else may be flagged.
rem
rem  The clean cases are the point. Two false-positive shapes
rem  shipped before this fixture existed:
rem    * an ANSI-colour menu digit, %w%0%g%, where the % that
rem      CLOSES a variable reads as the % of a %0, and
rem    * a shift inside a called helper, which renumbers that
rem      call frame's parameters and not the script's.
rem  A third came later: the same helper reached by a computed
rem  call. call :walk_%MODE% can land on any label starting
rem  with walk_, so each of those is a called frame too.
rem ============================================================

rem --- CLEAN: colour-variable menu digit, before any shift
echo    %g%[%w%0%g%]%w% Back

rem --- CLEAN: shift inside a CALLED helper is scoped to its own frame
call :walk_args a b c
echo    %g%[%w%0%g%]%w% Back after a called shift
echo %~dp0bundled.txt

rem --- CLEAN: shift inside a helper reached by a COMPUTED call is scoped too
call :walk_%MODE% a b c

goto real_work

:walk_args
if "%~1"=="" exit /b
shift
goto walk_args

:walk_opts
if "%~1"=="" exit /b
shift
goto walk_opts

:real_work
rem --- CLEAN: %~dp0 after the computed-call helper's shift
echo %~dp0bundled2.txt

rem --- CLEAN: doubled %%~dp0 is emitted text for a generated file
echo set "HERE=%%~dp0" >> "%TEMP%\gen.bat"

rem --- CLEAN: %10 is parameter ten, not %1 followed by 0
echo tenth is %10

rem now a top-level shift, which DOES renumber the script's own parameters
shift

rem --- FLAG: %~dp0 after a real top-level shift
copy "%~dp0payload.dat" "%TEMP%\p.dat"

rem --- FLAG: bare %0 after a real top-level shift
echo running %0

rem --- CLEAN: colour menu digit stays clean even after the shift
echo    %g%[%w%0%g%]%w% Back again

exit /b 0

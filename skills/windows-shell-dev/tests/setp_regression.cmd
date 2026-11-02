@echo off
rem ===== setp-stale regression fixture for check_setp_stale =====
rem A prompt line containing MUSTFLAG must be reported setp-stale. Every
rem other prompt (the SAFE twins) must NOT be. All prompts are dispatch-
rem style (value compared vs >=2 literals) so each finding is per-line and
rem exactly assertable.

rem --- MUSTFLAG: uncleared dispatch ---
:disp1
set /p "d1=Choose MUSTFLAG: "
if "%d1%"=="1" goto menu
if "%d1%"=="2" goto menu
if "%d1%"=="3" goto menu

rem --- SAFE: cleared adjacent ---
:safe1
set "s1="
set /p "s1=Choose: "
if "%s1%"=="1" goto menu
if "%s1%"=="2" goto menu

rem --- SAFE: cleared at routine top, prompt >8 lines later (whole-routine scan) ---
:safe2
set "s2="
echo filler 1
echo filler 2
echo filler 3
echo filler 4
echo filler 5
echo filler 6
echo filler 7
echo filler 8
echo filler 9
set /p "s2=Choose: "
if "%s2%"=="1" goto menu
if "%s2%"=="2" goto menu

rem --- SAFE: default-value assignment (recognized as handling) ---
:safe3
set "s3=1"
set /p "s3=Choose: "
if "%s3%"=="1" goto menu
if "%s3%"=="2" goto menu

rem --- SAFE: compound one-liner clear ---
:safe4
set "s4=" & set /p "s4=Choose: "
if "%s4%"=="1" goto menu
if "%s4%"=="2" goto menu

rem --- re-stale: cleared at top, first prompt SAFE, second prompt MUSTFLAG ---
:restale
set "r1="
set /p "r1=First: "
if "%r1%"=="1" goto menu
if "%r1%"=="2" goto menu
set /p "r1=Second MUSTFLAG: "
if "%r1%"=="1" goto menu
if "%r1%"=="2" goto menu

:menu
goto :eof

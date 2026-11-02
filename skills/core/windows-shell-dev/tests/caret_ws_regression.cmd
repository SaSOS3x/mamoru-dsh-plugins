@echo off
rem ============================================================
rem  Regression fixture for check_caret_ws in analyze_batch.py.
rem  A line whose text contains MUSTFLAG must be reported
rem  caret-trailing-ws. Every other line stays clean.
rem
rem  The pairing is the point: a caret at true end-of-line is a
rem  real continuation and must NOT fire; one trailing space
rem  turns it into an escaped space and kills the continuation,
rem  which is invisible in an editor and must fire.
rem ============================================================

rem --- FLAG: caret + one trailing space (continuation is dead) MUSTFLAG
reg add "HKCU\X" /v A ^ 
  /d 1 /f

rem --- FLAG: caret + a tab MUSTFLAG
echo alpha ^	
  beta

rem --- FLAG: caret + several spaces MUSTFLAG
copy "a" ^   
  "b"

rem --- CLEAN: caret at true end of line - a real continuation
echo gamma ^
  delta

rem --- CLEAN: caret escaping a space MID-line, not at the end
echo two^ words

rem --- CLEAN: escaped caret, no continuation intended
echo 100^^ percent

rem --- CLEAN: caret inside quotes
set "v=a^ b"

rem --- CLEAN: a comment mentioning a trailing caret ^ 
exit /b 0

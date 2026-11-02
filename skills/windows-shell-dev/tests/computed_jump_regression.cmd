@echo off
rem ============================================================
rem  Regression fixture for computed jump targets in
rem  check_labels (analyze_batch.py). A line whose text
rem  contains MUSTERR must be reported goto-undefined or
rem  call-undefined. Every other line stays clean.
rem
rem  goto :do_%CHOICE% finishes its label name at run time, so
rem  the analyzer only sees the prefix do_. Reading that prefix
rem  as the whole name reported working menu dispatch as a
rem  dangling jump. A computed target is broken for certain
rem  only when NO label starts with its prefix - and those must
rem  still fire.
rem ============================================================

rem --- ERR: computed, and no label starts with the prefix -----
goto :MUSTERR_menu_%CHOICE%
call :MUSTERR_sub_!k!
for %%a in (1 2) do goto MUSTERR_opt_%%a
call :MUSTERR_arg_%~1

rem --- ERR: a plain dangling jump is still caught -------------
goto :MUSTERR_plain

rem --- CLEAN: computed, and some label starts with the prefix -
goto :do_%CHOICE%
goto do_!sel!
call :do_%~1
for %%a in (1 2) do call :do_%%a
goto :DO_%CHOICE%
call :exact%suffix%
echo goto :nope_%x%

rem --- CLEAN: plain jumps that resolve ------------------------
goto :do_1
call :exact

:do_1
exit /b 0
:do_2
exit /b 0
:exact
exit /b 0

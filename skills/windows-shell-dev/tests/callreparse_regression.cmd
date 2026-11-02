@echo off
rem ===== call-reparse regression fixture for check_call_reparse =====
rem An echoed `call` line containing MUSTFLAG must be reported call-reparse. Every
rem other line (the SAFE twins) must NOT be. The first three MUSTFLAG lines are
rem emitters an ADB front-end shipped, verbatim; the rest are the other spellings.
setlocal EnableDelayedExpansion
set "_out=%TEMP%\restore_%RANDOM%.bat"

rem --- MUSTFLAG shipped: a captured value baked into an emitted call argument ---
>>"%_out%" echo call :dcx_do "settings put %_ns% %_key% '!_sv!'" & rem MUSTFLAG

rem --- MUSTFLAG shipped: a captured size, with no quotes around it inside ---
>>"%_out%" echo call :dcx_do "wm size !_osz!" & rem MUSTFLAG

rem --- MUSTFLAG shipped: percent-expanded names are baked into the line as well ---
>>"%_out%" echo call :dcx_do "settings delete %_ns% %_key%" & rem MUSTFLAG

rem --- MUSTFLAG: a batch-file target, with the redirect after the text ---
echo call "%%~dp0apply.cmd" "!_val!">>"%_out%" & rem MUSTFLAG

rem --- MUSTFLAG: echo( is an echo too ---
>>"%_out%" echo(call :apply "!_val!" & rem MUSTFLAG

rem --- MUSTFLAG: a reference the generated file expands still goes through call ---
>>"%_out%" echo call :apply "%%DCX_CMD%%" & rem MUSTFLAG

rem --- MUSTFLAG: a parameter of the emitting routine is expanded now ---
>>"%_out%" echo call :apply "%~1" & rem MUSTFLAG

rem --- MUSTFLAG: inside a block redirected as a whole, the line has no redirect ---
(
    echo if defined DCX_CMD call :apply "!_val!" & rem MUSTFLAG
) >> "%_out%"

rem --- SAFE: the fix - the value goes into a set line and the call is bare ---
>>"%_out%" echo set "DCX_CMD=settings put %_ns% %_key% '!_e!'"
>>"%_out%" echo call :dcx_do & rem SAFE: bare call

rem --- SAFE: literal arguments only ---
>>"%_out%" echo call :dcx_do "wm size reset" & rem SAFE: literal

rem --- SAFE: literal arguments, redirect after the text - its %_out% is not an argument ---
echo call :dcx_do "wm density reset">>"%_out%" & rem SAFE: literal, redirect after

rem --- SAFE: a variable NAME, which call cannot damage ---
>>"%_out%" echo call :apply DCX_CMD & rem SAFE: by reference

rem --- SAFE: a literal percent, written %% ---
>>"%_out%" echo call :apply "set to 100%%" & rem SAFE: literal percent

rem --- SAFE: prose that starts with Call is not a call line ---
echo Call support at %PHONE% if the restore fails. & rem SAFE: prose

rem --- SAFE: a direct call in THIS file is a review rule, not this check ---
call :apply "!_val!" & rem SAFE: direct call

rem --- SAFE: an emitter behind an inline rem is a comment too - nothing ends a rem ---
echo ok & rem note & >>"%_out%" echo call :apply "!_val!" & rem SAFE: after a rem

rem --- SAFE: a commented-out emitter is not code ---
rem >>"%_out%" echo call :dcx_do "settings put %_ns% %_key% '!_sv!'"

exit /b 0

:apply
exit /b 0

:dcx_do
exit /b 0

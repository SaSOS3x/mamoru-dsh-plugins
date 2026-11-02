@echo off
rem ===== prompt-width regression fixture for check_prompt_width =====
rem A set /p line containing MUSTFLAG must be reported prompt-width. Every
rem other prompt (the SAFE twins) must NOT be. Lengths are generated rather
rem than estimated, so the fixture cannot drift from what it claims to test.
mode con: cols=100 lines=36 >nul 2>&1

rem --- MUSTFLAG 102 columns: the shape that produced the bug report - caret landed at column 2 ---
set /p "_cm=MUSTFLAG Also open Windows Disk Cleanup for the system drive xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx? (Y/N): "

rem --- MUSTFLAG 100 columns: exactly at the limit: a full line leaves no room for the caret ---
set /p "_eq=MUSTFLAG Exactly the declared width, which is already one column too many xxxxxxxxxxxxxxxxx? (Y/N): "

rem --- MUSTFLAG 105 columns: set /p VAR="text" must be read as well as set /p "VAR=text" ---
set /p _alt="MUSTFLAG The other prompt shape, with the variable outside the quotes xxxxxxxxxxxxxxxxxxxxxxxxxx? (Y/N): "

rem --- MUSTFLAG 101 columns: colour escapes are zero-width; the visible text is what matters ---
set /p "_col=%y%MUSTFLAG Colour variables take no columns, but the text around them counts xxxxxxxxxxxxxxxxx? (Y/N): %w%"

rem --- SAFE 99 columns: 99 in a 100-column console still fits ---
set /p "_s1=One column under the declared width, which must stay clean xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx? (Y/N): "

rem --- SAFE 17 columns: short prompts are the normal case ---
set /p "_s2=Continue? (Y/N): "

rem --- SAFE 71 columns: the fix: explanation moved to the echo line above ---
echo   Cleanup opens in its own window; the script does not wait for it.
set /p "_s3=Also open Windows Disk Cleanup for the system drive xxxxxxxxxx? (Y/N): "

rem --- SAFE: reading a value from a file is not a prompt at all ---
set /p _s4=<"%TEMP%\a_file_whose_name_is_very_long_indeed_and_runs_past_one_hundred_columns.txt"

rem --- SAFE: a commented-out long prompt is not code ---
rem set /p "_s5=A commented out prompt far past one hundred columns must never be flagged here ok? "

rem --- SAFE: %% renders as one percent, so the visible text is shorter than the source ---
set /p "_s6=Set minimum processor state to 5%% which idles the CPU to save power xxxxxxxxxxxxxxxxxx? (Y/N): "

exit /b 0

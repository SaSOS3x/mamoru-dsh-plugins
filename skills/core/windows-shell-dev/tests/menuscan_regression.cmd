@echo off
rem ===== menuscan regression fixture =====
rem A prompt line containing MUSTFLAG(text) must be reported, with `text` in its finding.
rem Every other prompt (the SAFE twins) must NOT be. Never run this file; it is only scanned.
setlocal EnableDelayedExpansion

rem --- MUSTFLAG: a conditional row hides the gap - reads 1 2 3 4 6 while the row is off ---
:m_condgap
echo    [1] Details
echo    [2] Open
echo    [3] Battery
echo    [4] Force-stop
if "!_stp!"=="1" echo    [5] Clear the force-stop
echo    [6] Check again
echo    [0] Back
set "a=" & set /p a="MUSTFLAG(numbers skip [5] while the conditional rows are off): "
if "!a!"=="1" goto m_condgap
if "!a!"=="2" goto m_condgap
if "!a!"=="3" goto m_condgap
if "!a!"=="4" goto m_condgap
if "!a!"=="5" goto m_condgap
if "!a!"=="6" goto m_condgap
if "!a!"=="0" goto parent
goto m_condgap

rem --- MUSTFLAG: plain gap ---
:m_gap
echo    [1] One
echo    [2] Two
echo    [4] Four
set "b=" & set /p b="MUSTFLAG(numbers skip [3]): "
if "!b!"=="1" goto m_gap
if "!b!"=="2" goto m_gap
if "!b!"=="4" goto parent
goto m_gap

rem --- MUSTFLAG: shown, not handled - the catch-all redraws this menu, so [3] does nothing ---
:m_swallowed
echo    [1] One
echo    [2] Two
echo    [3] Back
set "c=" & set /p c="MUSTFLAG(shown, not handled ['3']): "
if "!c!"=="1" goto m_swallowed
if "!c!"=="2" goto m_swallowed
goto m_swallowed

rem --- MUSTFLAG: handled, not shown - and not named on any row either ---
:m_ghost
echo    [1] One
echo    [2] Two
set "d=" & set /p d="MUSTFLAG(handled, not shown ['3']): "
if "!d!"=="1" goto m_ghost
if "!d!"=="2" goto m_ghost
if "!d!"=="3" goto parent
goto m_ghost

rem --- MUSTFLAG: a key printed twice on option rows ---
:m_twice
echo    [1] One
echo    [2] Two
echo    [2] Also two
echo    [3] Back
set "e=" & set /p e="MUSTFLAG(shown twice ['2']): "
if "!e!"=="1" goto m_twice
if "!e!"=="2" goto m_twice
if "!e!"=="3" goto parent
goto m_twice

rem --- MUSTFLAG: numbered style (sincript) with a gap ---
:m_numstyle
echo     1.  Cleanup
echo     2.  Privacy
echo     4.  Power
echo     0.  Back
set "f=" & set /p f="MUSTFLAG(numbers skip [3]): "
if "!f!"=="1" goto m_numstyle
if "!f!"=="2" goto m_numstyle
if "!f!"=="4" goto m_numstyle
if "!f!"=="0" goto parent
goto m_numstyle

rem --- MUSTFLAG: two independent conditional rows - reads 1 2 4 when only the second shows ---
:m_indep
echo    [1] One
echo    [2] Two
if defined ROOTED echo    [3] Root tools
if defined MAGISK echo    [4] Magisk modules
echo    [0] Back
set "aa=" & set /p aa="MUSTFLAG(numbers skip [3] while the conditional row [3] is off): "
if "!aa!"=="1" goto m_indep
if "!aa!"=="2" goto m_indep
if "!aa!"=="3" goto m_indep
if "!aa!"=="4" goto m_indep
if "!aa!"=="0" goto parent
goto m_indep

rem --- MUSTFLAG: the same gap in block form ---
:m_block
echo    [1] One
echo    [2] Two
if defined EXTRA (
    echo    [3] Extra
)
echo    [4] Back
set "ab=" & set /p ab="MUSTFLAG(numbers skip [3] while the conditional rows are off): "
if "!ab!"=="1" goto m_block
if "!ab!"=="2" goto m_block
if "!ab!"=="3" goto m_block
if "!ab!"=="4" goto parent
goto m_block

rem --- MUSTFLAG: a row guarded by a command's success ---
:m_guard
echo    [1] One
adb get-state >nul 2>&1 && echo    [2] Two (phone connected)
echo    [3] Back
set "ac=" & set /p ac="MUSTFLAG(numbers skip [2] while the conditional rows are off): "
if "!ac!"=="1" goto m_guard
if "!ac!"=="2" goto m_guard
if "!ac!"=="3" goto parent
goto m_guard

rem --- MUSTFLAG: the redraw goes to the label the rows sit under, so it is not "leaving" ---
:m_redraw
echo    [1] One
echo    [2] Two
echo    [3] Back
:m_redraw_ask
set "ad=" & set /p ad="MUSTFLAG(shown, not handled ['3']): "
if "!ad!"=="1" goto m_redraw
if "!ad!"=="2" goto m_redraw
goto m_redraw

rem --- SAFE: contiguous, 0 = Back, all handled ---
:s_plain
echo    [1] One
echo    [2] Two
echo    [0] Back
set "g=" & set /p g="Choose: "
if "!g!"=="1" goto s_plain
if "!g!"=="2" goto s_plain
if "!g!"=="0" goto parent
goto s_plain

rem --- SAFE: the last option is the catch-all that leaves the menu ---
:s_catchall
echo    [1] One
echo    [2] Two
echo    [3] Back to the parent
set "h=" & set /p h="Choose: "
if "!h!"=="1" goto s_catchall
if "!h!"=="2" goto s_catchall
goto parent

rem --- SAFE: negated guards, an internal label, and a dispatch past 40 lines ---
:s_negated
echo    [1] One
echo    [2] Two
echo    [3] Back
set "i=" & set /p i="Choose: "
if not "!i!"=="1" goto _sn1
    echo filler 01
    echo filler 02
    echo filler 03
    echo filler 04
    echo filler 05
    echo filler 06
    echo filler 07
    echo filler 08
    echo filler 09
    echo filler 10
    echo filler 11
    echo filler 12
    echo filler 13
    echo filler 14
    echo filler 15
    echo filler 16
    echo filler 17
    echo filler 18
    echo filler 19
    echo filler 20
    echo filler 21
    echo filler 22
    echo filler 23
    echo filler 24
    echo filler 25
    echo filler 26
    echo filler 27
    echo filler 28
    echo filler 29
    echo filler 30
    echo filler 31
    echo filler 32
    echo filler 33
    echo filler 34
    echo filler 35
    echo filler 36
    echo filler 37
    echo filler 38
    echo filler 39
    echo filler 40
    goto s_negated
:_sn1
if not "!i!"=="2" goto _sn2
    goto s_negated
:_sn2
if "!i!"=="3" goto parent
goto s_negated

rem --- SAFE: a loop-printed list (dynamic rows): numeric ghosts are suppressed, letters not ---
:s_dynamic
set "n=0"
for %%f in (*.bak) do (
    set /a n+=1
    set "_idx=  [!n!]"
    echo    !_idx:~-5! %%f
)
echo    [R] Read the folder again
echo    [0] Cancel
set "j=" & set /p j="Pick: "
if "!j!"=="0" goto parent
if /i "!j!"=="R" goto s_dynamic
if "!j!"=="1" goto s_dynamic_one
if !j! GTR !n! goto s_dynamic
goto s_dynamic

rem --- SAFE: [2] inside a sentence is a mention, and a marker line is not a row ---
:s_mention
echo    [1] Enable
echo    [2] Disable
echo    [3] Delete the key - Android then uses AC only, the same as [2]
echo    [4] Back
echo  [i] Deleting is the same as [2] rather than a reset. Use [1] to get pop-ups back.
set "k=" & set /p k="Choose: "
if "!k!"=="1" goto s_mention
if "!k!"=="2" goto s_mention
if "!k!"=="3" goto s_mention
if "!k!"=="4" goto parent
goto s_mention

rem --- SAFE: hidden keys named in words on the Back row ---
:s_alias
echo    [1] Open the report
echo    [2] Back to main menu        (0 or Q also work)
set "r=" & set /p r="Choose: "
if "!r!"=="1" goto s_alias
if "!r!"=="2" goto parent
if "!r!"=="0" goto parent
if /i "!r!"=="q" goto parent
goto s_alias

rem --- SAFE: a file read, a no-newline print and a quoted read are not prompts ---
:s_fileread
echo    [1] One
echo    [2] Two
if exist last.txt set /p _last=<last.txt
<nul set /p "=  waiting for the phone..."
set /p "_prev="<last.txt
echo    [3] Three
echo    [4] Back
set "l=" & set /p l="Choose: "
if "!l!"=="1" goto s_fileread
if "!l!"=="2" goto s_fileread
if "!l!"=="3" goto s_fileread
if "!l!"=="4" goto parent
goto s_fileread

rem --- SAFE: columns - a 3-wide grid and a Y/N row ---
:s_columns
echo                             [1]            [2]            [3]
echo                             [4]            [5]            [6]
set "m=" & set /p m="Choose: "
if "!m!"=="1" goto s_columns
if "!m!"=="2" goto s_columns
if "!m!"=="3" goto s_columns
if "!m!"=="4" goto s_columns
if "!m!"=="5" goto s_columns
if "!m!"=="6" goto parent
goto s_columns

:s_yesno
echo    [Y] Apply    [N] Cancel
set "o=" & set /p o="Choose: "
if /i "!o!"=="Y" goto s_yesno_apply
goto parent

rem --- SAFE: the :Menu / :Menu_ask split (rows under the previous label) ---
:s_split
echo     1.  Light
echo     2.  Moderate
echo     0.  Back
:s_split_ask
set "sel=" & set /p sel="Choose a preset: "
if not defined sel goto s_split_ask
if "!sel!"=="0" goto parent
if "!sel!"=="1" goto s_split
if "!sel!"=="2" goto s_split
goto s_split_ask

rem --- SAFE: a computed jump handles every key ---
:s_computed
echo    [1] Page one
echo    [2] Page two
echo    [3] Page three
set "p=" & set /p p="Choose: "
goto s_page_!p!

rem --- SAFE: a value prompt with no dispatch is not a menu ---
:s_value
echo    [1] means AC
echo    [2] means USB
set "q=" & set /p q="Bitmask 0 - 15: "
echo you typed !q!
goto parent

rem --- SAFE: numbered prose above a Y/N question is not a menu ---
:s_prose
echo  1. Connect the phone by cable.
echo  2. Enable USB debugging.
set "ok=" & set /p ok="Continue (Y/N): "
if /i not "!ok!"=="Y" goto parent
goto s_prose_go

rem --- SAFE: a toggle row prints [2] in either state ---
:s_toggle
echo    [1] One
if "!ON!"=="1" echo    [2] Disable the thing
if not "!ON!"=="1" echo    [2] Enable the thing
echo    [3] Back
set "ae=" & set /p ae="Choose: "
if "!ae!"=="1" goto s_toggle
if "!ae!"=="2" goto s_toggle
if "!ae!"=="3" goto parent
goto s_toggle

rem --- SAFE: the same toggle in block form is neither a gap nor a duplicate ---
:s_blocktoggle
echo    [1] One
if "!ON!"=="1" (
    echo    [2] Disable the thing
) else (
    echo    [2] Enable the thing
)
echo    [3] Back
set "af=" & set /p af="Choose: "
if "!af!"=="1" goto s_blocktoggle
if "!af!"=="2" goto s_blocktoggle
if "!af!"=="3" goto parent
goto s_blocktoggle

rem --- SAFE: commented-out rows and branches are ignored ---
:s_rem
echo    [1] One
rem echo    [5] Old row
:: echo    [6] Older row
echo    [2] Back
set "ag=" & set /p ag="Choose: "
if "!ag!"=="1" goto s_rem
rem if "!ag!"=="5" goto s_rem_old
:: if "!ag!"=="6" goto s_rem_old
if "!ag!"=="2" goto parent
goto s_rem

rem --- SAFE: a lowercase key the dispatch handles is an option, [i] stays a marker ---
:s_lower
echo  [i] Pick one:
echo    [a] Apply
echo    [q] Quit
set "ah=" & set /p ah="Choose: "
if /i "!ah!"=="a" goto s_lower
if /i "!ah!"=="q" goto parent
goto s_lower

rem --- SAFE: other dispatch spellings, and the input copied to another variable ---
:s_forms
echo    [1] One
echo    [2] Two
echo    [3] Three
echo    [4] Back
set "in=" & set /p in="Choose: "
set "v=!in:~0,1!"
if "x!v!"=="x1" goto s_forms
if !v! EQU 2 goto s_forms
if "!v!" == "3" goto s_forms
if [!v!]==[4] goto parent
goto s_forms

rem --- SAFE: exit /b as the leaving catch-all, and a bullet prefix on the rows ---
:s_exitb
echo  * [1] One
echo  - [2] Two
echo  * [3] Return
set "ai=" & set /p ai="Choose: "
if "!ai!"=="1" goto s_exitb
if "!ai!"=="2" goto s_exitb
exit /b

rem --- SAFE: echo. and echo: forms, and an inline prompt inside a branch ---
:s_echodot
echo.[1] One
echo: [2] Two
echo.   [3] Back
set "aj=" & set /p aj="Choose: "
if "!aj!"=="1" (
    set "name=" & set /p name="File name: "
    goto s_echodot
)
if "!aj!"=="2" goto s_echodot
if "!aj!"=="3" goto parent
goto s_echodot

rem --- SAFE: a colour variable glued to the key, and an ANSI sequence ---
:s_colour
echo    !C_OPT![1]!C_OFF! One
echo    %ESC%[92m[2]%ESC%[0m Two
echo    [3] Back
set "ak=" & set /p ak="Choose: "
if "!ak!"=="1" goto s_colour
if "!ak!"=="2" goto s_colour
if "!ak!"=="3" goto parent
goto s_colour

:s_yesno_apply
:s_prose_go
:s_dynamic_one
:s_page_1
:s_page_2
:s_page_3
:parent
goto :eof

@echo off
rem ============================================================
rem  Regression fixture for the rem rules in check_blocks.
rem  A line marked MUST + EAT is reported rem-eats-paren, a line
rem  marked MUST + PIPE is reported rem-in-piped-block, and every
rem  other line stays clean - with the file staying balanced.
rem  The measured facts behind both: nothing ends a rem (& | and )
rem  are all part of the comment), and cmd folds a piped block into
rem  one line joined with & before a child runs it.
rem ============================================================

rem --- EAT: one-line block - the rem takes its closing paren ---
if 1==1 (echo a & rem MUSTEAT note & echo b)
)

rem --- EAT: multi-line block - the rem takes this line's paren ---
if 1==1 (
    echo a & rem MUSTEAT note )
    echo still inside
)

rem --- PIPE: a rem line inside a piped block ---
(
    rem MUSTPIPE this comment eats the rest of the folded block
    echo lost
) | findstr /n "^"

rem --- PIPE: an inline rem inside a piped block, redirect before the pipe ---
(
    echo kept & rem MUSTPIPE and the rest of the block goes with it
    echo lost
) 2>&1 | more

rem --- PIPE: a rem in a NESTED block still folds with the piped outer one ---
(
    if 1==1 (
        rem MUSTPIPE nested, still folded
        echo lost
    )
) | more

rem --- PIPE: a block on the RIGHT of the pipe is folded the same way ---
echo piped-in | (
    rem MUSTPIPE right-hand side
    findstr /n "^"
)

rem --- SAFE: a rem line inside a block that is redirected, not piped ---
(
    rem SAFE: redirected, not piped - no folding
    echo fine
) > "%TEMP%\pt_rem_fixture.txt"

rem --- SAFE: the comment hoisted above a piped block ---
rem SAFE: hoisted above the piped block
(
    echo fine
) | more

rem --- SAFE: || after a block is not a pipe ---
(
    rem SAFE: a conditional OR does not fold the block
    echo fine
) || echo never

rem --- SAFE: nor is || before one ---
echo x || (
    rem SAFE: conditional OR on the left, no folding
    echo fine
)

rem --- SAFE: a line-leading rem's ')' never closed anything - cmd agrees ---
if 1==1 (
    @rem SAFE: see the note above )
    echo fine
)

rem --- SAFE: an inline rem at top level, parens and all ---
echo top & rem SAFE: no block here (so this paren) is text

rem --- SAFE: an inline rem inside a block, its own parens balanced ---
if 1==1 (
    echo a & rem SAFE: see (docs) - both parens are the comment's own
)

rem --- SAFE: a quoted "& rem" is not a rem ---
if 1==1 ( echo "x & rem SAFE: y )" )

exit /b 0

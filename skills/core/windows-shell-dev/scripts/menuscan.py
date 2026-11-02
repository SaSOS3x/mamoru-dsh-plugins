#!/usr/bin/env python3
"""
Menu parity scan for batch scripts. For every `set /p` prompt it compares the option keys the
menu prints ([1] Foo / 1.  Foo / [R] Retry) with the keys the dispatch handles
(if "!var!"=="1" ...) and reports: numbers that skip, a key printed twice, a key printed but
never handled, and a key handled but never printed. Renumbering a menu is when these break,
and an option that silently does nothing looks fine in the source.

What counts (tuned on two production scripts, 17,600 lines between them, to zero false
positives; every shape below has a twin in tests/menuscan_regression.cmd):
  * An option key is [K] at the start of an echo's text (a box-drawing or bullet prefix is
    fine) or after two or more spaces (a column gap); [2] inside a sentence is a mention.
    `N.` / `N)` at the start of the text is the numbered style. Colour variables, carets and
    ANSI sequences are stripped first. A lowercase letter ([i]) is a marker unless the
    dispatch handles it ([q] Quit). A bracket holding a variable ([!i!], [%%n]) is a dynamic
    row: it cannot be counted, so numeric "handled, not shown" is suppressed for that menu.
  * A row is conditional when it is printed behind `if`, after `&&` / `||`, or inside an
    `if ( )` block. Numbers must be contiguous with the conditional rows off, on, and with
    each one alone on or alone off: a menu that reads 1 2 3 4 6 while a condition is off is
    the bug this scan exists for. A key printed by two conditional rows (`[3] Enable X` /
    `[3] Disable X`) counts as always present.
  * Option rows may sit under the prompt's own label or under the one before it when the
    prompt's label starts with `:_` or ends with `_ask` (the `:Menu` / `:Menu_ask` split).
  * The dispatch runs from the prompt to the next top-level label (one not starting with
    `:_`), the next unindented prompt, or 300 lines. `if [not] "!v!"=="K"` counts - also
    with `%v%`, a prefix (`"x!v!"=="x1"`), `EQU`, brackets, spaces around `==`, or on a
    variable copied from the prompt's (`set "v=!in:~0,1!"`); `goto x_!v!` / `call :x_!v!`
    handles every key. A goto that leaves the menu handles the rest: an unindented
    `goto other` or `exit /b` covers 0 when 0 is printed, else the last option, and
    `if not "!v!"=="K" goto other` covers every key but K. A goto that redraws the menu (its
    own label, or the label its rows sit under) handles nothing, so an option it swallows is
    reported. A handled key no row prints still counts as shown when an option row names it
    in words (`[5] Back   (0 or Q also work)`).
  * Comment lines are ignored. `set /p x=<file` is a read and `<nul set /p =text` is a
    print, not prompts. A prompt whose printed keys and handled keys have nothing in common
    (numbered prose above a Y/N question) is not a menu, nor is a prompt with no dispatch.
    Not seen: rows drawn by a `call`ed helper or packed into the prompt text, `choice /c`
    menus, and a dispatch that runs through a `for` loop.

Usage:  python menuscan.py script.cmd [-v]
        -v also lists every menu it checked, with the keys shown and handled.
Exit:   0 = no menu flagged; 1 = findings, one line each: prompt line, label, variable, keys
        shown, problems; 2 = usage, an unreadable file, or a UTF-16 file (nothing scanned).
"""
import re
import sys
from collections import Counter
from pathlib import Path

USAGE = "usage: python menuscan.py script.cmd [-v]"
COLOR = re.compile(r"(?:%[A-Za-z_]\w*%|![A-Za-z_]\w*!|\x1b)\[[0-9;]*m|%[A-Za-z_]\w*%|![A-Za-z_]\w*!(?=\[)|\^")
ECHO = re.compile(r"(?<![\w/\\])echo(?:[.:(]|(?=\s)|$)", re.I)
KEY = re.compile(r"\[\s*([0-9]{1,2}|[A-Za-z])\s*\]")
NUMSTYLE = re.compile(r"^\s*([0-9]{1,2})[.)]\s+\S")
DYNAMIC = re.compile(r"\[[^\]]*(?:![\w:~,\-]+!|%%~?\w|%\w+%)[^\]]*\]")
PROMPT = re.compile(r'set /p\s+"?(\w+)=', re.I)
NUL_IN = re.compile(r"<\s*nul\b", re.I)
COMMENT = re.compile(r"(?:::|rem\b)", re.I)
DISP = re.compile(r'if (?:/i )?(not )?(?:"|\[)?(\w*)[!%](\w+)[!%](?:"|\])?\s*(?:==|\bequ\b)\s*(?:"|\[)?\2([0-9A-Za-z]{1,2})(?![\w])(.*)', re.I)
COMPUTED = re.compile(r"\b(?:goto|call)\s+:?\S*[!%](\w+)[!%]", re.I)
COPY = re.compile(r'set\s+"?(\w+)=[!%](\w+)[:!%]', re.I)
GOTO = re.compile(r"\bgoto\s+:?(\w+)", re.I)
CATCHALL = re.compile(r"^(?:goto\s+:?(\w+)|exit\s*/b\b.*?)\s*$", re.I)
BLOCK_OPEN = re.compile(r"(?:if\b|for\b|else\b|\))", re.I)
MAX_DISPATCH = 300


def is_label(s):
    return s.startswith(":") and not s.startswith("::")


def is_top_label(s):
    return is_label(s) and not s.startswith(":_")


def label_name(s):
    parts = s[1:].split()
    return parts[0].lower() if parts else ""


def prompt_var(s):
    """The variable a `set /p` prompt fills, or None for a file read or the no-newline print."""
    m = PROMPT.search(s)
    if not m or NUL_IN.search(s) or re.match(r'"?\s*<', s[m.end():]):
        return None
    return m.group(1)


def option_keys(text):
    """Keys printed by one echo text: [K] at the start (after any non-word prefix) or after a
    column gap of two spaces, or `N.` at the start. Case is kept for the marker decision."""
    m = NUMSTYLE.match(text)
    if m:
        return [m.group(1)]
    keys = []
    for m in KEY.finditer(text):
        before = text[:m.start()]
        if re.search(r"\w", before) and not before.endswith("  "):
            continue
        keys.append(m.group(1))
    return keys


def gaps(nums):
    seen = sorted({n for n in nums if n != 0})
    return sorted(set(range(1, seen[-1] + 1)) - set(seen)) if seen else []


def scan(lines):
    """Yields (prompt_line_no, label, var, shown, handled, problems) per menu."""
    prev_prompt = -1
    for k, s in enumerate(lines):
        st = s.strip()
        if COMMENT.match(st):
            continue
        var = prompt_var(s)
        if not var:
            continue
        # the menu's own label; rows may sit one label back across a :_ or _ask label
        lab = k
        while lab > 0 and not is_label(lines[lab]):
            lab -= 1
        own = lines[lab] if is_label(lines[lab]) else "?"
        start = lab
        if lab > 0 and (own.startswith(":_") or label_name(own).endswith("_ask")):
            j = lab - 1
            while j > 0 and not is_label(lines[j]):
                j -= 1
            start = j
        own_names = {label_name(own)}
        if is_label(lines[start]):
            own_names.add(label_name(lines[start]))
        start = max(start, prev_prompt + 1)
        prev_prompt = k
        # rows: (key, conditional)
        rows = []
        aliases = set()
        dynamic = False
        depth = 0
        for j in range(start, k):
            raw = lines[j]
            if COMMENT.match(raw.strip()):
                continue
            t = COLOR.sub("", raw)
            lead = t.lstrip()
            if lead.startswith(")"):
                depth = max(0, depth - 1)
            if DYNAMIC.search(t):
                dynamic = True
            e = ECHO.search(t)
            if e:
                body = t[e.end():]
                head = t[:e.start()].strip().lower()
                conditional = depth > 0 or head.startswith(("if ", "for ")) or head.endswith(("&&", "||"))
                keys = option_keys(body)
                rows.extend((key, conditional) for key in keys)
                if keys:
                    aliases.update(w.upper() for w in re.findall(r"[A-Za-z0-9]+", body)
                                   if (w.isdigit() and len(w) <= 2) or (len(w) == 1 and w.isupper()))
            if t.rstrip().endswith("(") and BLOCK_OPEN.match(lead):
                depth += 1
        if len(rows) < 2:
            continue
        # dispatch
        names = {var.lower()}
        handled = []
        all_handled = False
        computed = False
        leave_rest = False
        end = min(len(lines), k + 1 + MAX_DISPATCH)
        for j in range(k + 1, end):
            raw = lines[j]
            if is_top_label(raw) or (prompt_var(raw) and not raw[:1].isspace()):
                break
            if COMMENT.match(raw.strip()):
                continue
            c = COPY.search(raw)
            if c and c.group(2).lower() in names:
                names.add(c.group(1).lower())
            m = COMPUTED.search(raw)
            if m and m.group(1).lower() in names:
                all_handled = computed = True
            for d in DISP.finditer(raw):
                if d.group(3).lower() not in names:
                    continue
                handled.append(d.group(4).upper())
                if d.group(1):                        # if not "!v!"=="K" goto X: X takes the rest
                    g = GOTO.search(d.group(5))
                    if g and not g.group(1).startswith("_") and g.group(1).lower() not in own_names:
                        all_handled = True
            cm = CATCHALL.match(raw)
            if cm and (cm.group(1) is None or
                       (not cm.group(1).startswith("_") and cm.group(1).lower() not in own_names)):
                leave_rest = True
        if not handled and not all_handled:
            continue
        # a lowercase letter is a marker ([i]) unless the dispatch handles it ([q] Quit)
        rows = [(key.upper(), cond) for key, cond in rows
                if not (key.isalpha() and key.islower() and key.upper() not in handled)]
        shown = [key for key, _ in rows]
        if len(shown) < 2 or (not computed and not set(shown) & set(handled)):
            continue
        # checks
        probs = []
        cond_count = Counter(key for key, cond in rows if cond and key.isdigit())
        fixed = {int(key) for key, cond in rows if key.isdigit() and (not cond or cond_count[key] >= 2)}
        singles = sorted(int(key) for key, n in cond_count.items() if n == 1)
        states = [(fixed | set(singles), ""), (fixed, " while the conditional rows are off")]
        for one in singles:
            states.append((fixed | {one}, f" while only the conditional row [{one}] shows"))
            states.append((fixed | (set(singles) - {one}), f" while the conditional row [{one}] is off"))
        for nums, when in states:
            g = gaps(nums)
            if g:
                probs.append(f"numbers skip {g}{when}")
                break
        fixed_keys = [key for key, cond in rows if not cond]
        dups = sorted({x for x in fixed_keys if fixed_keys.count(x) > 1})
        if dups:
            probs.append(f"shown twice {dups}")
        if not all_handled:
            unhandled = [x for x in dict.fromkeys(shown) if x not in handled]
            if leave_rest:
                excused = {"0"} if "0" in shown else {shown[-1]}
                unhandled = [x for x in unhandled if x not in excused]
            if unhandled:
                probs.append(f"shown, not handled {unhandled}")
        extra = [h for h in dict.fromkeys(handled) if h not in shown and h not in aliases]
        if dynamic:
            extra = [h for h in extra if not h.isdigit()]
        if extra:
            probs.append(f"handled, not shown {extra}")
        yield k + 1, own, var, shown, handled, probs


def main(argv):
    args = [a for a in argv if not a.startswith("-")]
    verbose = "-v" in argv
    if len(args) != 1:
        print(USAGE)
        return 2
    path = Path(args[0])
    try:
        data = path.read_bytes()
    except OSError as exc:
        print(f"cannot read {path}: {exc}")
        return 2
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        print(f"{path}: UTF-16 file, nothing scanned (cmd does not run those either)")
        return 2
    lines = data.decode("utf-8", "replace").splitlines()
    flagged = 0
    checked = 0
    for ln, lab, var, shown, handled, probs in scan(lines):
        checked += 1
        if probs:
            flagged += 1
            print(f"{ln:6} {lab:28} var={var:8} shown={' '.join(shown)} :: {'; '.join(probs)}")
        elif verbose:
            print(f"{ln:6} {lab:28} var={var:8} shown={' '.join(shown)}  handled={' '.join(dict.fromkeys(handled))}  ok")
    print(f"{flagged} menu(s) flagged, {checked} checked")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
analyze_batch.py (v2) - static analysis for large Windows batch/cmd scripts.

This is the "run this first, run this after every edit" tool. It catches the
classes of bug that are invisible until a user hits the exact menu path that
triggers them: broken goto/call targets, block-paren parse aborts, delayed
expansion `!` loss, redirect parsing surprises, pipe/`<nul` overrides, and
line-ending damage.

v2 was calibrated against two real production scripts (a ~2700-line optimizer
and a ~5300-line ADB front-end): every check below produced zero false
positives on both. The block-parenthesis machinery is a character-level
simulation of cmd's block parsing ported from the sincript test harness
(Run-Tests.ps1 test 9): quotes protect, `^` escapes, `(` opens a block only at
a command position, `)` closes anywhere, and after a close only
else / & / | / ) / redirects / end-of-line are legal.

Findings are graded:
  ERROR - the script is (or will be) broken. Fix before shipping.
  WARN  - matches a known bug pattern; almost always wrong, but heuristic.
  INFO  - worth a glance; frequently benign.

Exit code is nonzero if any ERROR is found, or any WARN when --strict is set,
so this drops straight into a test harness.

Usage:
    python analyze_batch.py PATH [PATH ...] [--strict] [--json] [--only ERROR,WARN]
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Finding model
# ---------------------------------------------------------------------------

SEVERITIES = ("ERROR", "WARN", "INFO")


class Finding:
    def __init__(self, severity, line, code, message):
        self.severity = severity
        self.line = line          # 1-based, or 0 for whole-file
        self.code = code          # short stable id, e.g. "goto-undefined"
        self.message = message

    def as_dict(self):
        return {
            "severity": self.severity,
            "line": self.line,
            "code": self.code,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Line classification helpers
# ---------------------------------------------------------------------------

def is_comment(line):
    """True for :: and rem comment lines (leading whitespace allowed)."""
    s = line.lstrip()
    if s.startswith("::"):
        return True
    return bool(re.match(r"(?i)rem(\s|$)", s))


def strip_quoted(s):
    """Remove double-quoted spans so their contents don't confuse keyword
    scanning. Batch has no backslash escaping inside quotes, so a quote simply
    toggles quoting."""
    out = []
    inq = False
    for ch in s:
        if ch == '"':
            inq = not inq
            continue
        if not inq:
            out.append(ch)
    return "".join(out)


def strip_echoed(s):
    """Blank out the literal text an `echo` prints, and everything a `rem` comments out.

    A script that GENERATES another script - and any batch tool that writes a .bat -
    is full of lines like `echo goto :done` or `>>"%f%" echo call :helper x`. That is
    data being written to a file, not control flow in THIS script, and scanning it for
    jumps produces confident false errors on a perfectly correct file. Five of those on
    a clean script is how people learn to ignore the analyser.

    `echo` swallows the rest of its command: everything after it is literal until an
    unquoted, unescaped command separator (& | ) starts a new command - `echo hi & goto x`
    really does jump, and must still be seen. Quotes toggle, `^` escapes the next char.

    `rem` is different, and the difference is easy to get backwards: NOTHING ends it. An
    inline rem comments out the rest of the LINE, & | and ) included - measured,
    `echo x & rem note & goto :next` never jumps and `echo a & rem n & echo b` never
    prints b. So from a rem onward the line is blanked whole.

    Both keywords count only where cmd reads a COMMAND - start of line, after & | ( @,
    after do / else, after an if-condition, after a leading redirect - never inside a
    word (`call :lorem ipsum` holds no rem). Forms handled:
      * `echo(text`  - the paren-delimiter twin of `echo.`; the text after `(` belongs
        to the echo, so `echo(goto :menu` names no jump. The corpus uses this ~29 times.
      * `cmd & rem see :Cleanup` - an inline rem, invisible to is_comment(), which only
        sees line-leading comments.
      * a line-leading `@rem`, which is a comment to cmd but invisible to is_comment()
        because of the `@`.
    """
    out = []
    i = 0
    n = len(s)
    inq = False
    echoing = False
    while i < n:
        ch = s[i]
        if ch == "^" and not inq and i + 1 < n:
            out.append(" " if echoing else ch)
            out.append(" " if echoing else s[i + 1])
            i += 2
            continue
        if ch == '"':
            inq = not inq
            out.append(ch)
            i += 1
            continue
        if not inq and echoing and ch in "&|)":
            echoing = False          # a new command starts here - resume scanning
            out.append(ch)
            i += 1
            continue
        if not inq and not echoing:
            mm = KEYWORD_RE.match(s, i)
            if mm and _cmd_pos(_mask_quoted(s[:i])):
                out.append(s[i:mm.end()])
                if mm.group(1).lower() == "rem":
                    out.append(" " * (n - mm.end()))    # a rem runs to end of LINE
                    break
                i = mm.end()
                echoing = True
                continue
        out.append(" " if echoing else ch)
        i += 1
    return "".join(out)


# `echo` needs a delimiter after it (space . or "(" - echo(text); `rem` needs whitespace
# or the end of the line: `rem.` is a different, weaker form that does not comment out
# & or |, so it is deliberately not matched here.
KEYWORD_RE = re.compile(r"(?i)@?(echo(?=[\s.(])|rem(?=\s|$))")

# A redirect before the command (`>>"%f%" echo ...`, `>nul 2>&1 call ...`) does not
# move the command out of command position.
REDIR_TAIL_RE = re.compile(r'(?:\s*\d?(?:>>?|<)(?:&\d|\s*(?:"[^"]*"|[^\s"&|<>()]+)))+\s*$')
# ...and one AFTER a block's ')' does not stop the block being piped: `( ... ) 2>&1 | x`.
REDIR_HEAD_RE = re.compile(r'^(?:\d?(?:>>?|<)(?:&\d|\s*(?:"[^"]*"|[^\s"&|<>()]+))\s*)+')


def _mask_quoted(s):
    """s with quoted content replaced by '_' (quotes kept) and ^x pairs by spaces - the
    shape _at_command_position expects: a quoted operand still reads as a token, and
    nothing inside quotes or after a caret can look like a separator."""
    out, inq, i = [], False, 0
    while i < len(s):
        c = s[i]
        if not inq and c == "^" and i + 1 < len(s):
            out.append("  ")
            i += 2
            continue
        if c == '"':
            inq = not inq
            out.append(c)
        else:
            out.append("_" if inq else c)
        i += 1
    return "".join(out)


def _cmd_pos(masked_prefix):
    """True if a command starts right after this (masked) prefix."""
    return _at_command_position(REDIR_TAIL_RE.sub("", masked_prefix))


def _rem_at(s, j, masked_prefix):
    """True if a real `rem` command starts at s[j]."""
    mm = KEYWORD_RE.match(s, j)
    return bool(mm) and mm.group(1).lower() == "rem" and _cmd_pos(masked_prefix)


def label_of(line):
    """If the line defines a label, return its (lowercased) name, else None.
    `::` is a comment, not a label."""
    s = line.lstrip()
    if not s.startswith(":") or s.startswith("::"):
        return None
    m = re.match(r":([^\s:+;=,\)\(\]\[]+)", s)
    return m.group(1).lower() if m else None


def is_computed_target(scan, m):
    """True if the jump target matched by `m` runs on into a variable -
    `goto :do_%CHOICE%`, `call :x_!k!`, `goto opt_%%a`, `call :h_%~1`. cmd
    finishes that name at run time, so the matched text is only its fixed
    prefix, never the label name itself."""
    return scan[m.end():m.end() + 1] in ("%", "!")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_encoding(raw, findings):
    """Line endings, BOM, stray bytes. Mixed endings are an ERROR because the
    round-trip through a naive editor is exactly how they appear, and cmd's
    label search is genuinely fragile on LF endings (measured: goto lost a
    label in most LF-only layouts tried).

    Non-ASCII is reported as ONE summary finding per file: some projects are
    intentionally UTF-8 (box-drawing menu borders, emoji in notification
    text), and per-line spam for a known convention buries real findings. The
    thing to actually watch for is a smart-quote or em-dash creeping into an
    otherwise ASCII-pure script."""
    crlf = raw.count(b"\r\n")
    lone_lf = raw.count(b"\n") - crlf
    lone_cr = raw.count(b"\r") - crlf
    if crlf and (lone_lf or lone_cr):
        findings.append(Finding(
            "ERROR", 0, "eol-mixed",
            f"Mixed line endings: {crlf} CRLF but also {lone_lf} lone LF / "
            f"{lone_cr} lone CR. Batch files must be uniformly CRLF; LF line "
            f"endings can make goto/call miss a label."))
    elif lone_lf and not crlf:
        findings.append(Finding(
            "WARN", 0, "eol-lf",
            f"File uses LF line endings ({lone_lf} LF). Windows batch expects "
            f"CRLF; convert before shipping."))
    if raw.startswith(b"\xef\xbb\xbf"):
        findings.append(Finding(
            "WARN", 0, "bom",
            "UTF-8 BOM at start of file. cmd reads the BOM bytes as part of "
            "the first line, so that command fails as 'not recognized' - a "
            "first-line @echo off never runs and every command is echoed. "
            "Save without a BOM."))
    if raw and not raw.endswith(b"\n"):
        findings.append(Finding(
            "INFO", 0, "eol-final",
            "File does not end with a newline; some tools mishandle the last "
            "line."))

    text = raw.decode("utf-8", errors="replace")
    hits = [i for i, ln in enumerate(text.split("\n"), 1)
            if any(ord(c) > 127 for c in ln)]
    if hits:
        sample = ", ".join(map(str, hits[:3]))
        findings.append(Finding(
            "INFO", hits[0], "non-ascii",
            f"{len(hits)} line(s) contain non-ASCII characters (first at "
            f"L{sample}). Fine if the project intentionally uses box-drawing "
            f"or emoji; verify no smart-quote or em-dash crept into an "
            f"ASCII-pure script, and keep the file's existing encoding "
            f"exactly as-is when editing."))


def check_caret_ws(lines, findings):
    """A caret only continues a line when it is the LAST character.

    `^` escapes the next character; at end-of-line that character is the newline,
    which is what makes the continuation work. One trailing space and the caret
    escapes the space instead - the newline then ends the command normally, the
    continuation is gone, and the next line runs on its own. Invisible in most
    editors, survives review and diff.
    """
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        if re.search(r"\^[ \t]+$", ln):
            findings.append(Finding(
                "WARN", i, "caret-trailing-ws",
                "A '^' here is followed by trailing whitespace, so it escapes the "
                "SPACE, not the newline - the line does not continue and the next "
                "line runs as its own command. Strip the trailing whitespace."))


def check_labels(lines, findings):
    """Duplicate labels, and goto/call targets with no matching label."""
    labels = {}
    for i, ln in enumerate(lines, 1):
        name = label_of(ln)
        if name is None:
            continue
        labels.setdefault(name, []).append(i)

    for name, where in labels.items():
        if len(where) > 1:
            findings.append(Finding(
                "ERROR", where[1], "label-duplicate",
                f"Label :{name} is defined {len(where)} times (lines "
                f"{', '.join(map(str, where))}). goto/call search forward from the "
                f"jumping line and wrap at end of file, so which copy runs depends on "
                f"where the jump is - fragile; rename so every label is unique."))

    goto_re = re.compile(r"(?i)\bgoto\b\s*:?\s*([A-Za-z0-9_.\-]+)")
    call_re = re.compile(r"(?i)\bcall\b\s*:\s*([A-Za-z0-9_.\-]+)")
    # What cmd does when a jump finds no label - measured, see pitfall 10.
    miss = {
        "goto": "When this line runs, cmd prints 'The system cannot find the batch "
                "label specified' and the script ends - or, inside a `call`ed "
                "routine, control returns to the caller with errorlevel 1.",
        "call": "When this line runs, cmd prints 'The system cannot find the batch "
                "label specified', sets errorlevel 1 and carries on with the next "
                "line - the routine never runs.",
    }
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        # Echoed text is data, not control flow - a .bat that writes a .bat says
        # things like `echo goto :done`, and that is not a jump in THIS file.
        scan = strip_quoted(strip_echoed(ln))
        for kind, rx in (("goto", goto_re), ("call", call_re)):
            for m in rx.finditer(scan):
                tgt = m.group(1).lower()
                if tgt == "eof":
                    continue
                if is_computed_target(scan, m):
                    # `goto :do_%CHOICE%` is menu dispatch, not a typo. Only a
                    # prefix that no label starts with fails for every value.
                    if not any(name.startswith(tgt) for name in labels):
                        whole = re.match(r"[^\s&|<>()]+", scan[m.start(1):]).group(0)
                        findings.append(Finding(
                            "ERROR", i, f"{kind}-undefined",
                            f"{kind} :{whole} completes its label name at run "
                            f"time, but no label starts with :{tgt}, so it cannot "
                            f"land whatever the variable holds. {miss[kind]}"))
                    continue
                if tgt not in labels:
                    findings.append(Finding(
                        "ERROR", i, f"{kind}-undefined",
                        f"{kind} :{tgt} has no matching label. {miss[kind]}"))

    # A routine `call`ed from directly above its own label also runs a SECOND
    # time by fall-through - and that pass was not entered by `call`, so its
    # `exit /b` leaves the context the `call` line runs in; at top level that
    # ends the batch. Everything below becomes unreachable, which reads as "the
    # menu never opens" rather than as a crash.
    #
    # Only the unambiguous shape is flagged: the first thing after the call,
    # ignoring blanks and comments, IS the label. With anything executable in
    # between, the author plainly meant control to arrive there and guessing
    # would only add noise.
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        scan = strip_quoted(strip_echoed(ln))
        m = call_re.search(scan)
        if not m:
            continue
        tgt = m.group(1).lower()
        if tgt == "eof" or tgt not in labels:
            continue
        # `call :x & goto y`, `call :x || goto y` - the line transfers control itself
        if re.search(r"(?i)\b(goto|exit)\b", scan[m.end():]):
            continue
        for nxt in lines[i:]:
            if not nxt.strip() or is_comment(nxt):
                continue
            if label_of(nxt) == tgt:
                findings.append(Finding(
                    "ERROR", i, "call-fallthrough",
                    f"call :{tgt} sits directly above :{tgt} with nothing "
                    f"executable in between, so the routine ALSO runs by "
                    f"fall-through. That second pass is not a call: its "
                    f"`exit /b` leaves the context the `call` line runs in - "
                    f"at top level that ends the whole batch and everything "
                    f"below it is unreachable - and any side effect inside "
                    f"runs twice. Add a `goto` past the routine."))
            break


# --- block-parenthesis machinery (port of Run-Tests.ps1 test 9) -------------

# An if-condition immediately before '(' means the '(' opens a block:
#   if [/i] [not] errorlevel N | exist X | defined X | A ==/EQU/... B   (
IF_COND_RE = re.compile(
    r'(?i)\bif\s+(?:/i\s+)?(?:not\s+)?(?:'
    r'errorlevel\s+\S+'
    r'|exist\s+(?:"[^"]*"|\S+)'
    r'|defined\s+\S+'
    r'|(?:"[^"]*"|\S+?)\s*(?:==|\bEQU\b|\bNEQ\b|\bLSS\b|\bLEQ\b|\bGTR\b|\bGEQ\b)\s*(?:"[^"]*"|\S+?)'
    r')\s*$')

# After a paren-group close, these may legally follow: a for-loop's `do`
# (the in-clause closes directly into it), else-chains, separators, another
# close, redirects incl. handle redirects like `2>nul`.
LEGAL_AFTER_CLOSE = re.compile(r'(?i)(do\b|else\b|&|\||\)|\d+>|[<>])')


def _at_command_position(prefix):
    """True if a '(' occurring right after `prefix` opens a paren group: the
    prefix (unquoted, carets neutralised) is empty, ends with a separator,
    ends with do/else, ends with a for-loop's `in` (the in-clause is a real
    paren group to cmd and must nest, or a ')' inside it would falsely close
    the enclosing block), or ends with an if-condition."""
    p = prefix.rstrip()
    if p == "" or p.endswith(("&", "|", "(", "@")):
        return True
    if re.search(r"(?i)\b(do|else|in)$", p):
        return True
    return bool(IF_COND_RE.search(p))


def check_blocks(lines, findings):
    """Character-level simulation of cmd block parsing, tracking depth across
    lines. Three findings come out of it:

    block-early-close (ERROR): inside a block, a bare ')' terminates the block
      even mid-text, and any following token that isn't do/else/&/|/)/redirect
      raises "X was unexpected at this time." and aborts the whole batch. This
      is the class that crashed a hosts restore after the file was already
      modified.

    block-paren-literal (WARN): any command inside a block emits a bare '('
      that cmd does NOT count as a block opener (it's in argument position) -
      an echo (`echo foo (bar)`), an unquoted `set x=(y)`, a `call :f (a)`, and
      so on. That leaves the block one ')' "short", so the next ')' glued into
      command text closes the block early: the rest of it runs outside the
      block (unconditionally, or without the block's redirect) and the block's
      own ')' line is skipped. The opening '(' and the closing ')' may be on the
      same line or on different lines (`echo (bar` ... `echo baz)`), so the
      pending '(' is carried across lines until the block closes. A ')' sitting
      at a structural close position instead (`)` alone, or `) > file` on its
      own line) is the intended close and is NOT flagged. Blocks opened by a
      quoted comparison (`if "a"=="b" (`) are tracked too. Quote the value
      (`set "x=(y)"`) or escape literal parens as ^( ^).

    paren-unbalanced (ERROR): net block depth at end of file isn't zero - a
      missing ')' swallows everything after it into one block.

    rem-eats-paren (ERROR): an inline `rem` comments out the rest of the LINE, the ')'
      included, so the block it was meant to close stays open. Nothing ends a rem - not
      & or |, not ) - and on a one-line block nothing after the '(' runs at all.

    rem-in-piped-block (ERROR): a rem inside a block on either side of a pipe
      (`( ... ) | x` or `x | ( ... )`). cmd runs a piped block in a child after folding
      its lines into ONE line joined with &, so the rem comments out the rest of that
      line - the block's own ')' included - and the child runs nothing from the block,
      not even the lines before the rem.
    """
    depth = 0
    pend_line = None          # line# where an echo left a bare '(' unclosed
    pend_depth = 0            # block depth at which that '(' sits
    rem_stack = []            # per open block: lines holding a rem (line-leading or inline)
    pipe_in = []              # per open block: opened straight after a pipe (`x | (`)
    for i, ln in enumerate(lines, 1):
        if depth > 0 and rem_stack and re.match(r"(?i)\s*@?rem(\s|$)", ln):
            rem_stack[-1].append(i)
        if is_comment(ln) or label_of(ln) is not None:
            # `::` is a label, not a comment keyword. Inside an open block cmd
            # parses the line after a label as a command, so a second `::` prints
            # "The system cannot find the drive specified." and a `::` right
            # before the closing `)` is a syntax error that aborts the batch.
            # `rem` is safe there. Depth comes from the real simulation below, so
            # the common `if not X goto skip` + indented `::` idiom (not a block)
            # is correctly left alone.
            if depth > 0 and ln.lstrip().startswith("::"):
                findings.append(Finding(
                    "WARN", i, "comment-in-block",
                    "'::' is a label, not a comment. Inside an open ( ) block "
                    "cmd parses the line after a label as a command: a second "
                    "'::' there prints \"The system cannot find the drive "
                    "specified.\", and a closing ')' there is a syntax error "
                    "that aborts the script. Use `rem` on a line of its own "
                    "inside a block (and not at all in a piped one - pitfall 54), "
                    "or hoist the comment above the block."))
            continue
        s = ln
        n = len(s)
        j = 0
        inq = False
        closed = False
        pre = []            # unquoted, caret-neutralised prefix (for position)
        cmd_text = []       # text of the current command (reset at boundaries)
        while j < n:
            c = s[j]
            if not inq and c == "^":
                # caret escapes the next char for the outer parse
                pre.append(" ")
                pre.append(" ")
                cmd_text.append(" ")
                j += 2
                continue
            if c == '"':
                inq = not inq
                pre.append('"')          # keep the quote delimiters so an
                cmd_text.append(" ")     # if-condition's "operand" is still a
                closed = False           # matchable "..." token for IF_COND_RE
                j += 1
                continue
            if inq:
                pre.append("_")          # quoted content -> safe placeholder:
                # can't leak ( ) & | into the command-position test, but keeps
                # the operand non-empty so `if "a"=="b" (` reads as a block open
                cmd_text.append(" " if c in "()" else c)
                j += 1
                continue
            if closed and c not in " \t":
                if LEGAL_AFTER_CLOSE.match(s[j:]):
                    closed = False
                else:
                    snippet = s[j:j + 40].rstrip()
                    findings.append(Finding(
                        "ERROR", i, "block-early-close",
                        f"'{snippet}' follows a block close on this line. A "
                        f"bare ')' inside a ( ) block ends the block even "
                        f"mid-text, and cmd aborts the whole batch with "
                        f"\"was unexpected at this time.\" - escape literal "
                        f"parens as ^( ^)."))
                    closed = False
            if _rem_at(s, j, "".join(pre)):
                # A rem: the rest of the LINE is comment, parens and separators included.
                # On an INLINE rem, a ')' in it that is not the comment's own is the one
                # that was meant to close the block - and cmd never sees it. (A line-leading
                # `@rem x )` eats its ')' too, but nobody meant that one to close anything,
                # and the top of the loop has already recorded the line.)
                if depth > 0 and "".join(pre).strip():
                    if rem_stack:
                        rem_stack[-1].append(i)
                    own = 0
                    for rc in s[j:]:
                        if rc == "(":
                            own += 1
                        elif rc == ")":
                            if own:
                                own -= 1
                            else:
                                findings.append(Finding(
                                    "ERROR", i, "rem-eats-paren",
                                    "An inline `rem` comments out the rest of the line - "
                                    "and that includes this ')'. The block it was meant to "
                                    "close stays open: everything up to the next ')' runs "
                                    "inside it, and if there is none, nothing after the '(' "
                                    "runs at all (measured: no output, exit 255, no "
                                    "message). Put the comment on its own line, or above "
                                    "the block (pitfall 54)."))
                                break
                break
            if c == "(":
                if _at_command_position("".join(pre)):
                    depth += 1
                    rem_stack.append([])
                    p_open = "".join(pre).rstrip()
                    pipe_in.append(p_open.endswith("|") and not p_open.endswith("||"))
                    cmd_text = []
                elif depth > 0 and pend_line is None:
                    # any command emitting a bare '(' in argument position (echo,
                    # set x=(y), call :f (a), ...): cmd does NOT count it as a
                    # block opener, so it leaves the block one ')' short. Carry
                    # it across lines until the block closes.
                    pend_line = i
                    pend_depth = depth
            elif c == ")":
                if depth > 0:
                    depth -= 1
                    closed = True
                    rems = rem_stack.pop() if rem_stack else []
                    right = pipe_in.pop() if pipe_in else False
                    after = REDIR_HEAD_RE.sub("", s[j + 1:].lstrip())
                    if right or (after.startswith("|") and not after.startswith("||")):
                        for rl in sorted(set(rems)):
                            findings.append(Finding(
                                "ERROR", rl, "rem-in-piped-block",
                                f"This `rem` is inside a ( ) block that is piped (the "
                                f"block closes on line {i}). cmd runs a piped block in a "
                                f"child after folding its lines into ONE line joined with "
                                f"'&', so the rem comments out the rest of that line - the "
                                f"block's own ')' included - and the child runs nothing "
                                f"from the block, not even the lines before the rem "
                                f"(measured: no output, no message, and the script carries "
                                f"on). Move the comment above the block (pitfall 54)."))
                    elif rem_stack:
                        rem_stack[-1].extend(rems)   # the parent may be piped
                    if pend_line is not None and depth < pend_depth:
                        # we've closed out of the block level that held the
                        # unbalanced echo '('. If THIS ')' is glued into command
                        # text (argument position) rather than at a structural
                        # close position, it's the accidental early terminator:
                        # the block's real ')' (often ') > file' on its own
                        # line) never runs and output truncates here.
                        p = "".join(pre).rstrip()
                        structural = (p == "" or p.endswith(("&", "|", "(")))
                        if not structural:
                            where = ("this line" if pend_line == i
                                     else f"line {pend_line}")
                            findings.append(Finding(
                                "WARN", i, "block-paren-literal",
                                f"A literal '(' inside a ( ) block ({where}) is "
                                f"left unbalanced (cmd ignores an opening '(' in "
                                f"argument position), so this ')' closes the "
                                f"block early: the lines after it run outside "
                                f"the block - unconditionally, or without its "
                                f"redirect - and the block's own ')' line is "
                                f"skipped. Quote the value (set \"x=(y)\") or "
                                f"escape as ^( ^)."))
                        pend_line = None
                    cmd_text = []
            elif c in "&|":
                cmd_text = []
            else:
                cmd_text.append(c)
            pre.append(c)
            j += 1
    if depth != 0:
        findings.append(Finding(
            "ERROR", 0, "paren-unbalanced",
            f"Unbalanced block parentheses across the file (net {depth:+d}). "
            f"A missing ')' usually swallows every following line into one "
            f"block; re-check the most recently edited block."))


def check_delayed_expansion(lines, findings):
    """If delayed expansion is enabled anywhere, flag a bare `!` in echoed text
    that is neither part of a !reference! nor caret-escaped - it gets eaten or
    mangles the line at runtime.

    A "reference" is anything !...! without spaces or quotes between the bangs,
    which covers plain vars (!x!), pseudo-arrays (!_nm[%%I]!, !_sst[%sel%]!),
    and substring/substitution syntax (!_p4:~0,58!, !_hx:~-8!). Note quotes do
    NOT protect `!` from delayed expansion, so quoted text is scanned too."""
    joined = "\n".join(lines).lower()
    if "enabledelayedexpansion" not in joined:
        return
    ref = re.compile(r'![^!\s"]{1,80}!')
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        low = ln.lower()
        if "echo" not in low:
            continue
        body = ln[low.index("echo") + 4:]
        probe = ref.sub("", body)
        probe = probe.replace("^^!", "").replace("^!", "")
        if "!" in probe:
            findings.append(Finding(
                "WARN", i, "delayed-bang",
                "Bare '!' in echoed text while delayed expansion is on. It "
                "will be consumed or garble the line (e.g. 'a != b' prints "
                "'a = b'); escape as ^^! - or as ^! inside double quotes, "
                "where ^^! prints '^' and still loses the '!'."))


def check_redirect_glue(lines, findings):
    """A %variable% glued directly onto > / >> is dangerous: if it expands to
    a single digit, or ends in a space plus a digit, cmd reads that digit as a
    stream handle and it never reaches the file (`abc1>>f` is safe - the digit
    has to stand alone). The redirect-first form (`>>file echo ...%var%`)
    is immune. Scoped to echo lines and %var% specifically, so legitimate
    handle redirects like `2>nul` or `cmd 2>>log` are never flagged."""
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        if "echo" not in ln.lower():
            continue
        if re.search(r"%[^%\s]+%>>?", ln):
            findings.append(Finding(
                "WARN", i, "redirect-var-glue",
                "A %variable% is glued directly onto a redirect. If the value "
                "is a single digit or ends in a space plus a digit ('1', "
                "'foo 2'), cmd reads that digit as a stream handle and it never "
                "reaches the file. Put the redirect first: "
                ">>file echo ...%var% ."))


def check_pipe_nul(lines, findings):
    """`... | findstr ... <nul` : the explicit <nul overrides the pipe, so the
    filter reads from nul and matches nothing. This silently kills device/state
    probes. (`producer <nul | findstr` is the correct placement and is not
    flagged; carets inside for /f in-clauses are neutralised first.)"""
    filt = re.compile(r"(?i)\|\s*(findstr|find|more|sort)\b")
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        scan = ln.replace("^|", "|").replace("^<", "<").replace("^>", ">")
        m = filt.search(scan)
        if not m:
            continue
        if re.search(r"(?i)<\s*nul", scan[m.end():]):
            findings.append(Finding(
                "WARN", i, "pipe-nul-override",
                "An explicit <nul appears after a pipe into a filter. The "
                "redirect overrides the piped input, so the filter reads from "
                "nul and never matches - move <nul onto the producer, not the "
                "filter."))


def check_setp_stale(lines, findings):
    """set /p VAR= keeps VAR's previous value on a bare Enter. Two tiers:

    Per-line INFO - dispatch prompts: the value drives a menu (computed
      goto/call containing the var, or the var is compared against 2+ distinct
      literals below). A stale value here re-runs the LAST ACTION, which can be
      destructive. These should always clear the var first.

    One summary INFO - confirm prompts (e.g. Y/N gates compared against a
      single literal). A stale 'Y' + bare Enter can auto-confirm, which is a
      real but lower risk; flooding a finding per prompt buries the report, so
      they are counted and sampled instead."""
    blocks = []
    cur, cur_start = [], 1
    for i, ln in enumerate(lines, 1):
        if label_of(ln) is not None and cur:
            blocks.append((cur_start, cur))
            cur, cur_start = [], i
        cur.append(ln)
    if cur:
        blocks.append((cur_start, cur))

    setp = re.compile(r"(?i)\bset\s*/p\s+\"?([A-Za-z0-9_]+)\"?\s*=")
    confirm_sites = []

    for start, blk in blocks:
        for j, ln in enumerate(blk):
            if is_comment(ln):
                continue
            m = setp.search(ln)
            if not m:
                continue
            var = m.group(1)
            lineno = start + j
            vesc = re.escape(var)
            # A plain `set "VAR=..."` before the prompt handles it - whether it
            # clears to empty (bare Enter = no) or sets a default (bare Enter =
            # that value, e.g. `set "_rp=Y"`). Matches `set VAR=` / `set "VAR=..."`
            # but NOT `set /p VAR=` (a prompt has /p between set and the name).
            handles = re.compile(r'(?i)\bset\s+"?' + vesc + r'=')
            prompts = re.compile(r'(?i)\bset\s*/p\s+"?' + vesc + r'\b')
            # Look back through the WHOLE routine (label-to-label block), not a
            # fixed 8-line window, so a var cleared at the routine's top counts.
            # The prompt line's own prefix covers the compound one-liner
            #   set "kb=" & set /p kb="..."
            handled = bool(handles.search(ln[:m.start()]))
            if not handled:
                for w in reversed(blk[:j]):
                    if prompts.search(w):
                        break   # an earlier set /p of this var re-stales it, so
                                # a clear before that earlier prompt doesn't count
                    if handles.search(w):
                        handled = True
                        break
            if handled:
                continue

            # Classify: does the value drive dispatch?
            tail = blk[j + 1:j + 30]
            vre = re.escape(var)
            computed = re.compile(
                r"(?i)\b(goto|call)\b[^&|\r\n]*[%!]" + vre + r"[%!]")
            compare = re.compile(
                r'(?i)[%!]' + vre + r'[%!]"?\s*==\s*"?([^"\s)]+)')
            rhs = set()
            dispatch = False
            for t in tail:
                if computed.search(t):
                    dispatch = True
                    break
                for cm in compare.finditer(t):
                    rhs.add(cm.group(1).lower())
            if dispatch or len(rhs) >= 2:
                findings.append(Finding(
                    "INFO", lineno, "setp-stale",
                    f"set /p {var} drives a menu but isn't cleared just before "
                    f"the prompt. On a bare Enter, {var} keeps its previous "
                    f"value and the menu re-runs the last action; add "
                    f"set \"{var}=\" first."))
            else:
                confirm_sites.append(lineno)

    if confirm_sites:
        sample = ", ".join(map(str, confirm_sites[:3]))
        findings.append(Finding(
            "INFO", confirm_sites[0], "setp-stale-confirms",
            f"{len(confirm_sites)} confirm-style set /p prompt(s) don't clear "
            f"their variable first (first at L{sample}). A stale 'Y' plus a "
            f"bare Enter auto-confirms; consider set \"VAR=\" before each, or "
            f"prefer choice /c YN which cannot go stale."))


def check_quote_balance(lines, findings):
    """Odd number of quotes on a non-comment line is usually a typo that will
    swallow following tokens or crash a comparison.

    The quote-handling substitution idioms are well-formed despite their odd
    or confusing raw counts - `%var:"=%` / `!var:"=!` STRIPS quotes (the
    standard defense against the lone-quote crash) and `!var:"=\\"!` ESCAPES
    them for generated .reg/JSON - so the whole `:"=` / `:"=\\"` unit is
    neutralised before counting, as are caret-escaped quotes (^\")."""
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        probe = re.sub(r':\*?"=(?:\\")?', ':=', ln)  # %v:"=% and !v:"=\"! idioms
        probe = probe.replace('^"', '')              # caret-escaped quote
        if probe.count('"') % 2 == 1:
            findings.append(Finding(
                "INFO", i, "quote-odd",
                "Odd number of double quotes on this line. If a user's input "
                "can reach here unquoted-compared, a lone \" crashes the whole "
                "script; guard comparisons as if \"!var!\"==\"...\"."))


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------



def check_pipe_validate(lines, findings):
    """Pitfall 36: a value echoed into a pipe is re-parsed by the piped child.

    cmd runs each side of a pipe in a child process and builds that child's command
    line from the ALREADY-expanded text, which the child parses again - operators and
    all. So `echo(!v!| findstr ...` with v="1.1.1.1&some-command" runs some-command
    and hands findstr a clean "1.1.1.1", which it approves. The validator is both
    bypassed and turned into an execution primitive.

    Only flags a VARIABLE feeding the pipe; piping a literal is fine.
    """
    pat = re.compile(r"echo[\(\s]\s*(?:!([A-Za-z_][A-Za-z0-9_]*)!|%([A-Za-z_][A-Za-z0-9_]*)%)\s*\|")

    # A script may neutralise the value BEFORE the probe instead of dropping the pipe.
    # Find the routines that do it - a helper whose body rejects every one of & | < >
    # by quoted comparison - and treat "call :thatHelper VAR" as protecting VAR. This is
    # resolved from the file, not hardcoded to one helper name, and it is deliberately
    # strict: a guard missing even one metacharacter does not count.
    guards = set()
    cur, body = None, []
    def _close(lbl, blk):
        if not lbl:
            return
        text = "\n".join(blk)
        ops = all(re.search(r'if\s+not\s+"!%~1:' + re.escape(c) + '=', text) for c in "&|<>")
        # A quote cannot sit inside that quoted comparison without ending it, so a
        # guard has to strip-and-compare it separately. Without that, a %v% probe
        # still lets `1.1.1.1"` through: the quote puts the pipe inside a quoted
        # region, findstr never runs and the || branch is skipped (measured; the !v!
        # form rejects the same value). A guard missing it is not a guard.
        quote = ':"=' in text and re.search(r"exit\s*/b\s*1", text) is not None
        if ops and quote:
            guards.add(lbl.lower())
    for ln in lines:
        lb = label_of(ln)
        if lb is not None:
            _close(cur, body)
            cur, body = lb, []
        elif cur:
            body.append(ln)
    _close(cur, body)

    guard_call = re.compile(
        r"(?i)\bcall\s+:(%s)\s+\"?([A-Za-z_][A-Za-z0-9_]*)" % "|".join(re.escape(g) for g in guards)
    ) if guards else None

    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        m = pat.search(ln)
        if not m:
            continue
        var = m.group(1) or m.group(2)
        if guard_call is not None:
            # Look back to the start of the routine (capped) for a guard on THIS variable.
            protected = False
            for k in range(i - 2, max(-1, i - 26), -1):
                if label_of(lines[k]) is not None:
                    break
                g = guard_call.search(lines[k])
                if g and g.group(2).lower() == var.lower():
                    protected = True
                    break
            if protected:
                continue
        # Report the form the SOURCE uses. Both are vulnerable - the expansion
        # happens before the piped child's command line is built - but a reader
        # who writes !v! and is shown %v% reads the finding as "not mine", and
        # "I use delayed expansion" is the most dangerous way to miss this one.
        var = f"!{m.group(1)}!" if m.group(1) else f"%{m.group(2)}%"
        findings.append(Finding(
            "ERROR", i, "pipe-validate",
            f"'{var}' is echoed into a pipe. cmd builds the piped child's command "
            f"line from the already-expanded text and parses it again, so a '&' or "
            f"'|' in the value EXECUTES there and the command on the right sees only "
            f"the part before it - a charset check built this way both passes the bad "
            f"value and runs it. Validate in-shell with for /f \"eol=<an allowed "
            f"char> delims=<allowed>\" - without the eol= everything after a ';' "
            f"walks through (pitfall 48) - or write the value to a file and scan it."))


def check_var_case_collision(lines, findings):
    """Pitfall 38: cmd variable names are case-insensitive.

    Two names differing only by case are ONE slot, so assigning either overwrites
    the other. Reads like a path/value pair, behaves like a single variable.
    """
    seen = {}
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        for m in re.finditer(r'\bset\s+"([A-Za-z_][A-Za-z0-9_]*)=', ln):
            name = m.group(1)
            seen.setdefault(name.lower(), {}).setdefault(name, i)
    for lowered, spellings in sorted(seen.items()):
        if len(spellings) < 2:
            continue
        shown = ", ".join(f"{n} (L{ln})" for n, ln in sorted(spellings.items()))
        first = min(spellings.values())
        findings.append(Finding(
            "ERROR", first, "var-case-collision",
            f"{shown} differ only by case, and cmd variable names are "
            f"case-INSENSITIVE - these are the same variable. Assigning one silently "
            f"overwrites the other; a pair that reads like 'the file' and 'the value it "
            f"holds' is a single slot. Rename one."))


VAR_REF_RE = re.compile(r"%[A-Za-z_][A-Za-z0-9_#$'()*+,\-.?@\[\]`{}~]*%")


def check_shift_selfpath(lines, findings):
    """Pitfall 40: shift renumbers %0, so %~dp0 afterwards is not the script.

    Flags any %0-derived path used textually after the first `shift` that can
    actually affect the script's own parameters.

    Two things this must NOT do, both learned from a real 8700-line menu script:

    * A `shift` inside a routine that is ever `call`ed is scoped to that call's
      frame - it renumbers the ROUTINE's %1.. (and its %0, which is the label),
      not the script's. An argument-walking helper (`:_next_arg` / shift / goto)
      is the normal shape, and anchoring on it made every later %0 an ERROR.
      A computed `call :walk_%MODE%` counts as a call to every label that
      starts with walk_. A label that is both called and goto'd is skipped
      too: that trades a possible miss for no false alarms, which is the right
      way round at ERROR.

    * A `%` that CLOSES a variable reference and is followed by a 0 is not a
      parameter. ANSI-colour menus are built from exactly that shape -
      `echo %g%[%w%0%g%] Back` prints the digit 0 between colour variables -
      and these scripts are full of them. Blank the %VAR% references first,
      then look for what is left.
    """
    labels = {label_of(ln) for ln in lines} - {None}
    call_targets = set()
    for ln in lines:
        if is_comment(ln):
            continue
        scan = strip_quoted(strip_echoed(ln))
        for m in re.finditer(r"(?i)\bcall\b\s*:\s*([A-Za-z0-9_.\-]+)", scan):
            tgt = m.group(1).lower()
            if is_computed_target(scan, m):
                # `call :walk_%MODE%` can land on any label starting with walk_
                call_targets.update(n for n in labels if n.startswith(tgt))
            else:
                call_targets.add(tgt)

    first_shift = None
    cur_label = None
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        nm = label_of(ln)
        if nm is not None:
            cur_label = nm
            continue
        if re.match(r"\s*shift\b", ln, re.IGNORECASE):
            if cur_label in call_targets:
                continue          # scoped to that call frame, not the script
            first_shift = i
            break
    if first_shift is None:
        return
    for i, ln in enumerate(lines, 1):
        if i <= first_shift or is_comment(ln):
            continue
        # Blank %VAR% first so a colour-variable menu digit (`%w%0%g%`) cannot
        # read as %0. Spaces keep every other column position intact.
        probe = VAR_REF_RE.sub(lambda m: " " * len(m.group(0)), ln)
        # (?<!%) so a DOUBLED %%~dp0 is skipped: that is an escape, writing a literal
        # %~dp0 into a generated batch file, where it means THAT file's location.
        # Emitted text is data, not code (pitfall 27).
        m = re.search(r"(?<!%)%~?[dpnxsatzf]*0(?![0-9])", probe)
        if not m:
            continue
        findings.append(Finding(
            "ERROR", i, "shift-selfpath",
            f"'{m.group(0)}' is used after the 'shift' on line {first_shift}. shift "
            f"renumbers ALL parameters including %0, so this no longer names the "
            f"script - %~dp0 of an argument resolves against the current directory "
            f"(for a /switch, the drive root), so bundled files are looked for in the "
            f"wrong place whenever that is not the script's folder. Capture the path "
            f"once at the top, before any argument parsing, and use that."))

def check_prompt_width(lines, findings):
    """A `set /p` prompt longer than the console line makes cmd place the input caret at
    (prompt length mod console width). The question is still drawn in full, so the first
    keystroke lands INSIDE it and overwrites the text - the user watches their answer appear
    in the middle of the sentence.

    Only runs when the script declares a width itself (`mode con: cols=N`). A script that
    never resizes could be in any terminal, and guessing a width would invent findings.

    %var% is counted as zero columns because a prompt's variables are almost always colour
    escapes; that can only UNDER-estimate the length, so it never invents a finding either.
    A doubled %% renders as one %. Both prompt shapes are read: set /p "VAR=text" and
    set /p VAR="text". The unquoted `set /p VAR=<file` read-from-file idiom has no prompt
    and is not matched."""
    width = None
    for ln in lines:
        if is_comment(ln):
            continue
        m = re.search(r"(?i)\bmode\s+con\b[^&|]*?\bcols\s*=\s*(\d+)", ln)
        if m:
            width = int(m.group(1))
    if not width:
        return
    pat = re.compile(r'(?i)set\s+/p\s+(?:"([A-Za-z_][A-Za-z0-9_]*)=([^"]*)"'
                     r'|([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)")')
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        for m in pat.finditer(ln):
            var = m.group(1) or m.group(3)
            text = m.group(2) if m.group(2) is not None else m.group(4)
            shown = text.replace("%%", "\x00")
            shown = re.sub(r"%[^%\s]*%", "", shown).replace("\x00", "%")
            if len(shown) >= width:
                findings.append(Finding(
                    "WARN", i, "prompt-width",
                    f"This set /p prompt ({var}) is {len(shown)} columns, at or over the "
                    f"{width}-column console this script sets with `mode con`. cmd puts the "
                    f"input caret at (length mod width), so the first keystroke lands inside "
                    f"the question and overwrites it. Move the explanation to an echo line "
                    f"above and keep the question short (pitfall 52)."))


def echoed_texts(s):
    """The literal text each `echo` on the line prints - the twin of strip_echoed().

    Same parse: quotes toggle, `^` escapes the next character, and an unquoted,
    unescaped & | ) ends the echo and starts a new command. The delimiter right after
    `echo` (space, `.` or `(`) is not part of the text, and a redirect is cut off,
    because `echo x>>"%f%"` prints `x`, not the file name."""
    out = []
    i, n = 0, len(s)
    inq = False
    cur = None
    while i < n:
        ch = s[i]
        if cur is not None:
            if ch == "^" and not inq and i + 1 < n:
                cur.append(s[i:i + 2])
                i += 2
                continue
            if ch == '"':
                inq = not inq
            elif not inq and ch in "&|)":
                out.append("".join(cur))
                cur = None
                i += 1
                continue
            elif not inq and ch in "<>":
                # a redirect: drop an immediately preceding handle digit, then skip the
                # operator and its target, and keep reading - the echo is not over yet
                if cur and cur[-1].isdigit() and (len(cur) < 2 or cur[-2].isspace()):
                    cur.pop()
                j = i + 1
                while j < n and s[j] in "<>&":
                    j += 1
                while j < n and s[j] in " \t":
                    j += 1
                if j < n and s[j] == '"':
                    k = s.find('"', j + 1)
                    j = n if k < 0 else k + 1
                else:
                    while j < n and not s[j].isspace() and s[j] not in "&|)":
                        j += 1
                i = j
                continue
            cur.append(ch)
            i += 1
            continue
        if ch == '"':
            inq = not inq
        elif not inq and ch == "^":
            i += 2
            continue
        elif not inq:
            mm = KEYWORD_RE.match(s, i)
            if mm and _cmd_pos(_mask_quoted(s[:i])):
                if mm.group(1).lower() == "rem":
                    break                      # the rest of the line is a comment
                i = mm.end() + 1               # the delimiter is not printed
                cur = []
                continue
        i += 1
    if cur is not None:
        out.append("".join(cur))
    return out


def check_call_reparse(lines, findings):
    """Pitfall 53: `call` parses its arguments a second time.

    A batch file that writes batch files (a restore script, an undo file) often emits
    one `call :apply "<command>"` line per captured value. When the generated file
    runs, it parses that line once and `call` parses the argument AGAIN: a % in the
    value is consumed and a quoted ^ comes back doubled - measured, a ringtone URI's
    Over%20the%20Horizon restored as Over0the0Horizon. The value has to travel in a
    variable instead: emit `set "VAR=<value>"` and a bare `call :apply`.

    Only EMITTED calls are checked - an `echo`ed `call :label` or `call x.bat/.cmd`
    whose arguments contain any variable expansion, whether it is expanded now
    (%v%, !v!, %~1) or written for the generated file to expand (%%v%%, ^!v^!): both
    put a value through call's second parse. A bare call, literal arguments and a
    variable NAME (call :apply VAR) are the safe shapes. A direct call in this file
    (call :x "!v!") has the same problem but is only a bug when the value can hold %
    or ^, which a lint cannot know - that one stays a review rule."""
    call_rx = re.compile(
        r'(?i)(?:^|(?<=[\s&(]))@?call\s+(:[^\s"&|<>()]+|"[^"]*\.(?:bat|cmd)"|[^\s"&|<>()]+\.(?:bat|cmd))')
    exp_rx = re.compile(
        r"%%?~?[A-Za-z_][A-Za-z0-9_#$.\-\[\]]*(?::[^%]*)?%%?"      # %v% %%v%% %v:~0,5%
        r"|(?:\^+)?![A-Za-z_][A-Za-z0-9_#$.\-\[\]]*(?::[^!]*)?(?:\^+)?!"  # !v! ^!v^!
        r"|(?<!%)%~?[a-z]*[0-9*]")                                  # %1 %~1 %*
    for i, ln in enumerate(lines, 1):
        if is_comment(ln):
            continue
        hit = None
        for text in echoed_texts(ln):
            for cm in call_rx.finditer(text):
                ems = [e.group(0) for e in exp_rx.finditer(text[cm.end():])]
                if ems:
                    # name the value most likely to be data: a !v! is usually captured
                    hit = (cm.group(1), ([e for e in ems if "!" in e] or ems)[0])
                    break
            if hit:
                break
        if not hit:
            continue
        target, tok = hit
        findings.append(Finding(
            "WARN", i, "call-reparse",
            f"This writes a `call {target}` line whose argument holds '{tok}'. When the "
            f"generated file runs, the line is parsed once and `call` parses its arguments "
            f"a second time, so a % in the value is consumed and a quoted ^ comes back "
            f"doubled (Over%20the%20Horizon restores as Over0the0Horizon). Emit "
            f"`set \"VAR=<value>\"` - each % written %% - and a bare `call {target}` that "
            f"reads !VAR! (pitfall 53)."))


CHECKS = [
    check_labels,
    check_caret_ws,
    check_blocks,
    check_delayed_expansion,
    check_redirect_glue,
    check_pipe_nul,
    check_setp_stale,
    check_quote_balance,
    check_pipe_validate,
    check_var_case_collision,
    check_shift_selfpath,
    check_prompt_width,
    check_call_reparse,
]


def analyze(path):
    raw = Path(path).read_bytes()
    findings = []
    check_encoding(raw, findings)
    text = raw.decode("utf-8", errors="replace")
    lines = text.replace("\r\n", "\n").split("\n")
    for chk in CHECKS:
        chk(lines, findings)
    findings.sort(key=lambda f: (SEVERITIES.index(f.severity), f.line))
    return findings, len(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--strict", action="store_true",
                    help="exit nonzero on WARN as well as ERROR")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--only", default="",
                    help="comma-separated severities to show (e.g. ERROR,WARN)")
    args = ap.parse_args()

    show = set(s.strip().upper() for s in args.only.split(",") if s.strip()) \
        or set(SEVERITIES)

    worst_error = False
    worst_warn = False
    report = {}
    for p in args.paths:
        findings, nlines = analyze(p)
        shown = [f for f in findings if f.severity in show]
        report[p] = {"lines": nlines, "findings": [f.as_dict() for f in shown]}
        if any(f.severity == "ERROR" for f in findings):
            worst_error = True
        if any(f.severity == "WARN" for f in findings):
            worst_warn = True

        if not args.json:
            counts = {s: sum(1 for f in findings if f.severity == s)
                      for s in SEVERITIES}
            print(f"\n=== {p}  ({nlines} lines) ===")
            print(f"    ERROR={counts['ERROR']}  WARN={counts['WARN']}  "
                  f"INFO={counts['INFO']}")
            if not shown:
                print("    (clean)")
            for f in shown:
                loc = f"L{f.line}" if f.line else "file"
                print(f"    [{f.severity:5}] {loc:>6}  {f.code}: {f.message}")

    if args.json:
        print(json.dumps(report, indent=2))

    if worst_error or (args.strict and worst_warn):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
crlf_edit.py - edit Windows batch/PowerShell files without wrecking their bytes.

The single most common way to corrupt one of these scripts is to open it in a
tool that "helpfully" rewrites CRLF to LF, adds a BOM, or normalises trailing
whitespace. cmd is sensitive to all three. This module edits by exact
string-replacement while preserving the original line endings, encoding, and
BOM state, and it refuses to apply a replacement that doesn't match exactly
once (so an edit can never silently no-op or hit the wrong place).

Use as a library from a one-off Python edit script (put this folder on sys.path
first, e.g. sys.path.insert(0, "<path to this scripts folder>")):

    from crlf_edit import read, write, replace_exact, to_newline
    text, meta = read("PerfTweaks.cmd")
    # to_newline gives a snippet written with LF the file's own line endings
    text = replace_exact(text, to_newline(OLD_BLOCK, meta.newline),
                         to_newline(NEW_BLOCK, meta.newline))   # expects exactly 1 match
    write("PerfTweaks.cmd", text, meta)

Or from the command line for a single replacement:

    python crlf_edit.py report FILE
    python crlf_edit.py replace FILE --old-file old.txt --new-file new.txt
    python crlf_edit.py replace FILE --old "goto :men" --new "goto :menu"

`replace` reads --old-file/--new-file as bytes (no newline translation), gives
both snippets the file's line ending (LF or CRLF input both work on a CRLF file)
and exits 1 - without writing - when nothing would change or the edit would add
lone LF endings to a CRLF file.

`read` returns the text with line endings intact (it reads with newline="" so
\\r\\n stays literal), plus a Meta describing how to write it back byte-faithfully.
"""

import argparse
import sys
from pathlib import Path

BOM = "\ufeff"


class Meta:
    def __init__(self, newline, encoding, had_bom):
        self.newline = newline      # dominant line ending: "\r\n" or "\n"
        self.encoding = encoding    # e.g. "ascii", "utf-8"
        self.had_bom = had_bom


def _detect_encoding(raw):
    """Prefer the tightest encoding that round-trips: ascii, else utf-8."""
    body = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    try:
        body.decode("ascii")
        return "ascii"
    except UnicodeDecodeError:
        return "utf-8"


def read(path):
    """Return (text, meta). Line endings are preserved in `text`."""
    raw = Path(path).read_bytes()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    encoding = _detect_encoding(raw)
    crlf = raw.count(b"\r\n")
    lone_lf = raw.count(b"\n") - crlf
    newline = "\r\n" if crlf >= lone_lf and crlf > 0 else "\n"
    # newline="" keeps \r\n literal in the string so replacements see real bytes.
    text = raw.decode("utf-8-sig" if had_bom else encoding, errors="strict") \
        if encoding != "ascii" or had_bom else raw.decode("ascii")
    return text, Meta(newline, encoding, had_bom)


def write(path, text, meta):
    """Write `text` back with the recorded encoding/BOM, preserving whatever
    line endings are already in the string. We pass newline="" so Python does
    not translate; the caller's text already contains the intended endings."""
    enc = meta.encoding
    data = text
    if meta.had_bom and not data.startswith(BOM):
        data = BOM + data
    with open(path, "w", encoding=enc if enc != "ascii" else "ascii",
              newline="") as fh:
        fh.write(data)


def replace_exact(text, old, new, expect=1):
    """Replace `old` with `new`, asserting it occurs exactly `expect` times.
    Raises ValueError on any mismatch - the whole point is to fail loudly rather
    than corrupt or no-op."""
    n = text.count(old)
    if n != expect:
        raise ValueError(
            f"expected {expect} occurrence(s) of the target string, found {n}. "
            f"Refusing to edit. Widen or narrow the anchor so it is unique.")
    return text.replace(old, new, expect)


def eol_report(path):
    raw = Path(path).read_bytes()
    crlf = raw.count(b"\r\n")
    lone_lf = raw.count(b"\n") - crlf
    lone_cr = raw.count(b"\r") - crlf
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    enc = _detect_encoding(raw)
    nonascii = sum(1 for b in (raw[3:] if had_bom else raw) if b > 127)
    return {
        "path": str(path),
        "bytes": len(raw),
        "crlf": crlf,
        "lone_lf": lone_lf,
        "lone_cr": lone_cr,
        "bom": had_bom,
        "encoding": enc,
        "non_ascii_bytes": nonascii,
        "ends_with_newline": raw.endswith(b"\n"),
        "uniform_crlf": crlf > 0 and lone_lf == 0 and lone_cr == 0,
    }


def _cmd_report(args):
    r = eol_report(args.file)
    width = max(len(k) for k in r)
    for k, v in r.items():
        print(f"  {k:<{width}} : {v}")
    ok = r["uniform_crlf"] and not r["bom"]
    print(f"\n  -> {'OK: uniform CRLF, no BOM' if ok else 'CHECK the flags above'}")
    return 0 if ok else 1


def _read_snippet(path):
    """Read an --old-file / --new-file as bytes, so no newline translation
    happens (Path.read_text would turn CRLF into LF)."""
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8")


def to_newline(s, newline):
    """Give every line break of `s` the ending `newline` (CRLF or LF). A snippet
    typed or saved with LF must not put bare LF into a CRLF file."""
    return s.replace("\r\n", "\n").replace("\n", newline)


def _cmd_replace(args):
    old = _read_snippet(args.old_file) if args.old_file else args.old
    new = _read_snippet(args.new_file) if args.new_file else args.new
    if old is None or new is None:
        print("error: provide --old/--new or --old-file/--new-file", file=sys.stderr)
        return 2
    if old == "":
        print("error: the old text is empty", file=sys.stderr)
        return 2
    before = eol_report(args.file)
    text, meta = read(args.file)
    # Match the snippet as given first (a mixed file may hold a lone LF on purpose);
    # if that finds nothing, retry with the file's own line ending.
    if text.count(old) != args.expect:
        old_n = to_newline(old, meta.newline)
        if old_n != old and text.count(old_n) == args.expect:
            old = old_n
    # The inserted text always gets the file's dominant line ending.
    new = to_newline(new, meta.newline)
    try:
        new_text = replace_exact(text, old, new, expect=args.expect)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if new_text == text:
        print("error: nothing was replaced (old and new text are identical). "
              "File not written.", file=sys.stderr)
        return 1
    lone_lf_before = text.count("\n") - text.count("\r\n")
    lone_lf_after = new_text.count("\n") - new_text.count("\r\n")
    if meta.newline == "\r\n" and lone_lf_after > lone_lf_before:
        print(f"error: the edit would add {lone_lf_after - lone_lf_before} lone LF "
              "line ending(s) to the file. File not written.", file=sys.stderr)
        return 1
    write(args.file, new_text, meta)
    after = eol_report(args.file)
    print(f"replaced {args.expect} occurrence(s).")
    print(f"  CRLF {before['crlf']} -> {after['crlf']}, "
          f"lone LF {before['lone_lf']} -> {after['lone_lf']}, "
          f"encoding {after['encoding']}, bom {after['bom']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("report", help="print EOL/encoding/BOM report")
    rp.add_argument("file")
    rp.set_defaults(func=_cmd_report)

    ep = sub.add_parser("replace", help="single exact-match replacement")
    ep.add_argument("file")
    ep.add_argument("--old", default=None)
    ep.add_argument("--new", default=None)
    ep.add_argument("--old-file", default=None)
    ep.add_argument("--new-file", default=None)
    ep.add_argument("--expect", type=int, default=1,
                    help="number of matches required (default 1)")
    ep.set_defaults(func=_cmd_replace)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

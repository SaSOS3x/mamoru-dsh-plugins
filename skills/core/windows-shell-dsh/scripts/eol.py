#!/usr/bin/env python3
"""eol.py - count line endings on BYTES. In Git Bash `grep -c $'\\r' file` prints 0 for a CRLF file (checked 2026-10-12),
so never use it to decide CRLF vs LF.

  python eol.py FILE [FILE ...]
  -> "FILE: CRLF n, LF-only n, CR-only n, BOM yes|no|utf-16le|utf-16be, last line terminated yes|no -> CRLF|LF|CR|MIXED|none"
  -> "FILE: BINARY (NUL bytes, no UTF-16 BOM): line endings not counted"
UTF-16 text with a BOM (what Windows PowerShell 5.1 `>` writes) is decoded and counted as text.
Exit 1 when a file is unreadable or MIXED (CRLF together with lone LF / CR, or LF together with CR); BINARY is not an error.
Stdlib only, ASCII-only output.
"""
import sys


def classify(data):
    crlf = data.count(b'\r\n')
    lf = data.count(b'\n') - crlf
    cr = data.count(b'\r') - crlf
    if crlf + lf + cr == 0:
        kind = 'none'
    elif (crlf and (lf or cr)) or (lf and cr):
        kind = 'MIXED'
    else:
        kind = 'CRLF' if crlf else 'LF' if lf else 'CR'
    return crlf, lf, cr, kind


def main(paths):
    bad = 0
    for p in paths:
        try:
            with open(p, 'rb') as f:
                data = f.read()
        except OSError as e:
            print(f'{p}: {e}')
            bad = 1
            continue
        if data.startswith((b'\xff\xfe', b'\xfe\xff')):
            bom = 'utf-16le' if data.startswith(b'\xff\xfe') else 'utf-16be'
            try:  # count on the decoded text: in UTF-16 every newline carries a NUL byte
                data = data.decode('utf-16').encode('utf-8')
            except UnicodeDecodeError:
                print(f'{p}: UTF-16 BOM but the text does not decode as UTF-16')
                bad = 1
                continue
        elif b'\x00' in data:
            print(f'{p}: BINARY (NUL bytes, no UTF-16 BOM): line endings not counted')
            continue
        else:
            bom = 'yes' if data.startswith(b'\xef\xbb\xbf') else 'no'
        crlf, lf, cr, kind = classify(data)
        term = bool(data) and data[-1:] in (b'\n', b'\r')
        print(f'{p}: CRLF {crlf}, LF-only {lf}, CR-only {cr}, BOM {bom}, '
              f'last line terminated {"yes" if term else "no"} -> {kind}')
        bad |= kind == 'MIXED'
    return bad


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))

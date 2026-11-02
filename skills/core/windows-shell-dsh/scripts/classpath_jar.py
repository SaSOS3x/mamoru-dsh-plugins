#!/usr/bin/env python3
"""classpath_jar.py - a tiny jar whose manifest Class-Path lists many jars/dirs (Windows 32k command-line limit).

  python classpath_jar.py OUT.jar ENTRY [ENTRY ...] [--skip-missing]
  ENTRY = a jar, a directory, a glob (mods/*.jar, libs/**/*.jar) or @listfile (one path per line).
  A missing entry (or a glob that matches nothing) is an error, exit 1, nothing written; --skip-missing only warns
  (use it for an old list file that still names jars which are gone).
  Then:  javap -cp OUT.jar some.pkg.Class      (javap has no @argfile; java / javac do: java @args.txt)

Why: javap / java -cp with a 35k-char classpath fails on Windows with "Argument list too long" (CreateProcess ~32767
chars). The JVM follows Class-Path of a jar on the classpath, so the long list moves into the file.
Details: entries become file:/// URLs (spaces -> %20), directories get a trailing '/', manifest lines are wrapped at
72 bytes with a leading space on continuation lines (the manifest spec). Needs only the stdlib; ASCII-only output.
Exit 0 ok, 1 usage / missing entry or @file / nothing matched / OUT.jar cannot be written (e.g. its folder is missing).
"""
import glob
import pathlib
import sys
import zipfile


class ListFileError(Exception):
    pass


def expand(entry):
    if entry.startswith('@'):
        try:
            lines = pathlib.Path(entry[1:]).read_text(encoding='utf-8-sig').splitlines()
        except OSError as e:
            raise ListFileError(f'error: list file {entry[1:]} cannot be read ({e.strerror or e})')
        return [l.strip() for l in lines if l.strip()]
    if any(ch in entry for ch in '*?['):
        return sorted(glob.glob(entry, recursive=True)) or [entry]
    return [entry]


def to_url(p):
    path = pathlib.Path(p).resolve()
    url = path.as_uri()
    return url + '/' if path.is_dir() and not url.endswith('/') else url


def wrap(name, value):
    raw = (name + ': ' + value).encode('ascii')
    out, first = [], True
    while raw:
        n = 72 if first else 71
        out.append((b'' if first else b' ') + raw[:n])
        raw, first = raw[n:], False
    return b'\r\n'.join(out) + b'\r\n'


def main(argv):
    if argv[:1] in (['-h'], ['--help']):
        print(__doc__)
        return 0
    if len(argv) < 2:
        print(__doc__)
        return 1
    skip_missing = '--skip-missing' in argv
    argv = [a for a in argv if a != '--skip-missing']
    if len(argv) < 2:
        print(__doc__)
        return 1
    out, items = argv[0], []
    try:
        for e in argv[1:]:
            items += expand(e)
    except ListFileError as e:
        print(e)
        return 1
    missing = [p for p in items if not pathlib.Path(p).exists()]
    items = [p for p in items if pathlib.Path(p).exists()]
    for p in missing:
        print(f'{"warning: skipped" if skip_missing else "error: not found"}: {p}')
    if missing and not skip_missing:
        print(f'{len(missing)} entries do not exist; nothing written (use --skip-missing to ignore them)')
        return 1
    if not items:
        print('nothing matched')
        return 1
    manifest = b'Manifest-Version: 1.0\r\n' + wrap('Class-Path', ' '.join(to_url(p) for p in items)) + b'\r\n'
    try:
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('META-INF/MANIFEST.MF', manifest)
    except OSError as e:
        print(f'error: cannot write {out} ({e.strerror or e}); does its folder exist?')
        try:
            pathlib.Path(out).unlink()  # no half-written jar left behind
        except OSError:
            pass
        return 1
    print(f'{out}: {len(items)} entries, manifest {len(manifest)} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

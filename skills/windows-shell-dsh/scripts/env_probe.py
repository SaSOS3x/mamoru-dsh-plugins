#!/usr/bin/env python3
"""env_probe.py - one call that shows the Windows / Git Bash / Python / JDK traps of THIS shell session.

  python env_probe.py [DIR]      DIR = folder to scan for stdlib-shadowing .py files (default: current folder)
  python env_probe.py -h | --help
Prints OK / WARN lines, ASCII only. Exit 0 even with WARN lines (it is a report, not a gate: on a typical Windows PC some
WARN is always there, and a non-zero code would stop `&&` chains); read the WARN lines. Exit 2 for an unknown option.
Run it first in a new project.
Checks: python stdout and open() encodings (+ PYTHONIOENCODING / PYTHONUTF8), `python3` being the Microsoft Store stub,
JAVA_HOME vs the java / javac / javap / jar that PATH really picks, .py files named like stdlib modules.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys
import locale


def line(level, text):
    print(f'{level:5} {text}')


def java_version(exe):
    try:
        r = subprocess.run([exe, '-version'], capture_output=True, text=True, timeout=20)
        text = (r.stderr + r.stdout).strip().splitlines()
        m = re.search(r'(\d+(?:\.\d+)*)', text[0]) if text else None
        return m.group(1) if m else (text[0] if text else '?')
    except Exception as e:
        return f'error {e}'


def main(scan_dir):
    line('INFO', f'python {sys.version.split()[0]} at {sys.executable}')
    enc_out = sys.stdout.encoding
    enc_open = locale.getpreferredencoding(False)
    pio, pu8 = os.environ.get('PYTHONIOENCODING'), os.environ.get('PYTHONUTF8')
    line('INFO', f'stdout encoding {enc_out}, open() default {enc_open}, PYTHONIOENCODING={pio}, PYTHONUTF8={pu8}')
    if (enc_out or '').lower().replace('-', '') != 'utf8':
        line('WARN', 'stdout is not UTF-8: print() of non-cp1251 text raises UnicodeEncodeError '
                     '(set PYTHONIOENCODING=utf-8 or PYTHONUTF8=1; with `python -I` the variables are ignored, use `python -I -X utf8`)')
    if (enc_open or '').lower().replace('-', '') != 'utf8':
        line('WARN', 'open() without encoding= reads/writes text in %s, not UTF-8 '
                     '(PYTHONIOENCODING does not change this; pass encoding="utf-8" or set PYTHONUTF8=1)' % enc_open)

    p3 = shutil.which('python3')
    if p3 and 'WindowsApps' in p3:
        line('WARN', f'python3 is the Microsoft Store stub ({p3}); call `python`')
    elif p3 is None:
        line('INFO', 'no python3 on PATH; call `python`')

    jh = os.environ.get('JAVA_HOME')
    line('INFO', f'JAVA_HOME={jh}')
    versions = {}
    for tool in ('java', 'javac', 'javap', 'jar'):
        exe = shutil.which(tool)
        if not exe:
            line('INFO', f'{tool}: not on PATH')
            continue
        if tool == 'jar':  # jar has no -version; the JDK folder in its path tells the version
            line('INFO', f'jar: {exe}')
            continue
        versions[tool] = ver = java_version(exe)
        line('INFO', f'{tool}: {exe} -> {ver}')
    majors = {v.split('.')[0] for k, v in versions.items() if k != 'jar' and v[:1].isdigit()}
    if len(majors) > 1:
        line('WARN', f'java tools on PATH are different JDK majors: {versions}; use the full path of the one you need')
    if jh:
        jx = pathlib.Path(jh) / 'bin' / 'java.exe'
        if jx.exists():
            jv = java_version(str(jx))
            pv = versions.get('java')
            if pv and jv.split('.')[0] != pv.split('.')[0]:
                line('WARN', f'JAVA_HOME java is {jv} but `java` on PATH is {pv}: Gradle / Maven / scripts using '
                             'JAVA_HOME will use another JDK than your manual commands')

    std = getattr(sys, 'stdlib_module_names', set())
    shadow = [f.name for f in pathlib.Path(scan_dir).glob('*.py') if f.stem in std]
    if not pathlib.Path(scan_dir).is_dir():
        line('WARN', f'{scan_dir}: folder does not exist (or is not a folder), nothing was scanned; check the path')
    elif shadow:
        line('WARN', f'{scan_dir}: files named like stdlib modules {shadow}: they hide the real module for every '
                     'script in this folder and for `python -c` run here; rename or use `python -I -X utf8`')
    else:
        line('OK', f'{scan_dir}: no stdlib-named .py files')
    return 0


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else '.'
    if arg in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)
    if arg.startswith('-'):
        print(f'unknown option {arg}\n{__doc__}')
        sys.exit(2)
    sys.exit(main(arg))

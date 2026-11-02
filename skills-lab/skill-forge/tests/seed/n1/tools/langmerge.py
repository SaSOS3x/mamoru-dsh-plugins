#!/usr/bin/env python3
"""langmerge - сборка файла локализации мода из частей.
Запуск: python3 tools/langmerge.py build <папка с частями> --out <файл>
        python3 tools/langmerge.py check <файл>"""
import argparse, glob, json, os


def cmd_build(a):
    merged = {}
    for path in sorted(glob.glob(os.path.join(a.src, '*.json'))):
        try:
            with open(path, encoding='utf-8') as f:
                part = json.load(f)
        except (ValueError, OSError):
            continue
        merged.update(part)
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f'langmerge: {len(merged)} keys written to {a.out}')


def cmd_check(a):
    with open(a.file, encoding='utf-8') as f:
        data = json.load(f)
    print(f'check: OK ({len(data)} keys)')


p = argparse.ArgumentParser(prog='langmerge')
s = p.add_subparsers(dest='cmd', required=True)
b = s.add_parser('build'); b.add_argument('src'); b.add_argument('--out', required=True); b.set_defaults(fn=cmd_build)
c = s.add_parser('check'); c.add_argument('file'); c.set_defaults(fn=cmd_check)
a = p.parse_args(); a.fn(a)

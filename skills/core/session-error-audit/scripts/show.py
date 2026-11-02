#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""show.py - посмотреть строки аудита глазами: шаблоны ловят слова, а не смысл.

Показывает для каждой строки команду и ту часть вывода, где ошибка (строки вокруг последнего
маркера ошибки), поэтому команда, которая сначала напечатала файл, а потом упала, видна по ошибке.

  python scripts/show.py --dir <папка аудита> --cat STRONG --n 5
  python scripts/show.py --dir <папка аудита> --cluster "javap"
  python scripts/show.py --dir <папка аудита> --cat SOFT --part head
"""
import argparse
import json
import os
import re
import sys

MARKERS = re.compile(r'Traceback|ERROR:|Error:|error:|Exception|not recognized|No such file|denied|'
                     r'FAILURE|fatal:|\[exit code:[^\]]+\]', re.I)


def load(directory):
    path = os.path.join(directory, 'classified.json')
    if not os.path.isfile(path):
        path = os.path.join(directory, 'rows.json')
    if not os.path.isfile(path):
        print('ERROR: нет classified.json/rows.json в %s (сначала scan_fail.py и classify.py)' % directory)
        sys.exit(2)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def excerpt(text, part, width=24):
    lines = (text or '').splitlines()
    if not lines:
        return '(пусто)'
    if part == 'head':
        return '\n'.join(lines[:width])
    for i in range(len(lines) - 1, -1, -1):
        if MARKERS.search(lines[i]):
            start = max(0, i - width // 3)
            return '\n'.join(lines[start:start + width])
    return '\n'.join(lines[-width:])


def main(argv=None):
    ap = argparse.ArgumentParser(description='Показать строки аудита с местом ошибки.')
    ap.add_argument('--dir', required=True, help='папка аудита')
    ap.add_argument('--cat', help='вид: STRONG, SOFT, EXPECTED, NOISE')
    ap.add_argument('--cluster', help='подстрока кластера или подписи ошибки')
    ap.add_argument('--n', type=int, default=5, help='сколько строк показать (по умолчанию 5)')
    ap.add_argument('--part', choices=['error', 'head'], default='error', help='что показать из вывода')
    ap.add_argument('--full', action='store_true', help='печатать весь сохранённый вывод')
    a = ap.parse_args(argv)

    rows = load(os.path.abspath(a.dir))
    selected = []
    for row in rows:
        if a.cat and (row.get('category') or '').upper() != a.cat.upper():
            continue
        if a.cluster:
            hay = ' '.join(str(row.get(k) or '') for k in ('cluster', 'signature', 'cmd'))
            if a.cluster.lower() not in hay.lower():
                continue
        selected.append(row)

    if not selected:
        print('ничего не нашлось (всего строк: %d)' % len(rows))
        return 0

    for row in selected[:a.n]:
        print('=' * 78)
        print('%s | %s | %s | %s' % (row.get('time'), row.get('session'), row.get('tool'),
                                     row.get('category') or row.get('kind')))
        if row.get('exit_code') is not None:
            print('код возврата: %s' % row.get('exit_code'))
        print('команда: %s' % (row.get('cmd') or '').replace('\n', ' ')[:300])
        body = row.get('text') or ''
        print('-' * 78)
        print(body if a.full else excerpt(body, a.part))
    print('=' * 78)
    print('показано %d из %d подходящих строк' % (min(a.n, len(selected)), len(selected)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compare.py - шестой шаг аудита: сравнить два аудита по кластерам.

Сравнивать надо на 1000 вызовов, а не абсолютные числа: объём работы за этап разный.
Кластер упал - правка сработала. Остался - правило не доходит до агентов или чинит не то.
Новый кластер - новый вид ошибки.

  python scripts/compare.py --old _project/audit/2026-10-12 --new _project/audit/2026-11-02
"""
import argparse
import json
import os
import sys


def load_summary(directory):
    path = os.path.join(directory, 'summary.json')
    if not os.path.isfile(path):
        print('ERROR: нет summary.json в %s (сначала classify.py --dir %s)' % (directory, directory))
        sys.exit(2)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def cluster_map(summary):
    out = {}
    for c in summary.get('clusters') or []:
        total = (c.get('strong') or 0) + (c.get('soft') or 0) + (c.get('expected') or 0)
        out[c.get('cluster')] = {
            'total': total,
            'strong': c.get('strong') or 0,
            'soft': c.get('soft') or 0,
            'expected': c.get('expected') or 0,
            'example': c.get('example') or c.get('cluster'),
        }
    return out


def per_1000(count, calls):
    if not calls:
        return None
    return count * 1000.0 / calls


def fmt_per_1000(count, calls):
    value = per_1000(count, calls)
    if value is None:
        return '-'
    return '%.1f' % value


def main(argv=None):
    ap = argparse.ArgumentParser(description='Сравнить два аудита по кластерам (на 1000 вызовов).')
    ap.add_argument('--old', required=True, help='папка прошлого аудита')
    ap.add_argument('--new', required=True, help='папка текущего аудита')
    ap.add_argument('--top', type=int, default=25, help='сколько кластеров показать')
    a = ap.parse_args(argv)

    old = load_summary(os.path.abspath(a.old))
    new = load_summary(os.path.abspath(a.new))
    old_calls = old.get('calls') or 0
    new_calls = new.get('calls') or 0
    old_map = cluster_map(old)
    new_map = cluster_map(new)

    print('было: %d строк, %d настоящих сбоев на %d вызовов (%.1f на 1000)' % (
        old.get('rows', 0), old.get('real', 0), old_calls, old.get('real_per_1000_calls') or 0.0))
    print('стало: %d строк, %d настоящих сбоев на %d вызовов (%.1f на 1000)' % (
        new.get('rows', 0), new.get('real', 0), new_calls, new.get('real_per_1000_calls') or 0.0))
    print('')

    keys = set(old_map) | set(new_map)
    rows = []
    for key in keys:
        o = old_map.get(key, {'total': 0, 'strong': 0, 'soft': 0, 'expected': 0, 'example': key})
        n = new_map.get(key, {'total': 0, 'strong': 0, 'soft': 0, 'expected': 0, 'example': key})
        label = n.get('example') or o.get('example') or key
        rows.append((label, o, n))
    rows.sort(key=lambda r: (r[2]['total'] + r[1]['total']), reverse=True)

    print('%-8s %-8s %-8s %-8s %s' % ('было', 'стало', 'было/1к', 'стало/1к', 'кластер'))
    for label, o, n in rows[:a.top]:
        print('%-8d %-8d %-8s %-8s %s' % (
            o['total'], n['total'],
            fmt_per_1000(o['total'], old_calls), fmt_per_1000(n['total'], new_calls),
            str(label)[:100]))

    appeared = [k for k in new_map if k not in old_map]
    disappeared = [k for k in old_map if k not in new_map]
    print('')
    print('новых кластеров: %d' % len(appeared))
    for k in appeared[:10]:
        print('  + %s' % str(new_map[k]['example'])[:100])
    print('исчезли: %d' % len(disappeared))
    for k in disappeared[:10]:
        print('  - %s' % str(old_map[k]['example'])[:100])
    print('')
    print('Вывод по кластеру, который остался: правило не доходит до агентов или чинит не то.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

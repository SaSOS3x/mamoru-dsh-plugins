#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""classify.py - второй шаг аудита: разложить строки аудита по видам.

Виды:
  STRONG     настоящий сбой с ненулевым кодом возврата или isError;
  SOFT       код 0 (или маркера нет), но в выводе Traceback, "No such file", отказ и подобное;
  EXPECTED   нормальный ответ проверки: git diff вернул 1, robocopy вернул 1 и т. п.;
  NOISE      слово из шаблона в успешном выводе: прочитанный файл, поиск, вывод самих скриптов аудита.

Правила можно дополнить своим JSON:

  {
    "expected": [{"tool": "pwsh", "where": "cmd", "pattern": "git diff", "why": "различия - это ответ"}],
    "noise":    [{"tool": "pwsh", "where": "out", "pattern": "^\\[image\\]"}]
  }

`tool` - имя инструмента или "*"; `where` - `out` (вывод), `cmd` (команда), `tool` (имя).
Результат: classified.json и summary.json в папке --dir; на экран - таблица.

  python scripts/classify.py --dir _project/audit/2026-11-02
  python scripts/classify.py --dir tmp --rules my_rules.json
"""
import argparse
import json
import os
import re
import sys

DEFAULT_EXPECTED = [
    {'tool': 'pwsh', 'where': 'cmd', 'pattern': r'git\s+(diff|grep)\b', 'why': 'различия/совпадения: код 1 - ответ'},
    {'tool': 'pwsh', 'where': 'cmd', 'pattern': r'\bgit\s+diff\s+--quiet\b', 'why': 'различия: код 1 - ответ'},
    {'tool': 'pwsh', 'where': 'cmd', 'pattern': r'\brobocopy\b', 'why': 'robocopy: код 1 значит "скопировано"'},
    {'tool': 'pwsh', 'where': 'cmd', 'pattern': r'\b(Test-Path|Get-ChildItem)\b.*-ErrorAction\s+SilentlyContinue', 'why': 'проба отсутствия'},
    {'tool': 'pwsh', 'where': 'out', 'pattern': r'^\(no output\)', 'cmd_pattern': r'-ErrorAction\s+SilentlyContinue|Test-Path',
     'why': 'проба отсутствия: пустой вывод и чужой код возврата $LASTEXITCODE'},
    {'tool': 'pwsh', 'where': 'out', 'pattern': r'NativeCommandError', 'cmd_pattern': r'2>&1',
     'not_pattern': r'EPERM|error:|Traceback|Access is denied|not found|Could not|Cannot|denied',
     'why': 'stderr нативной команды при 2>&1 в PowerShell 5.1 - не сбой'},
]

DEFAULT_NOISE = [
    {'tool': 'pwsh', 'where': 'cmd',
     'pattern': r'(scan_fail|classify|show|compare|journal_compact)\.py|rows\.json|summary\.json|classified\.json',
     'why': 'вывод самих скриптов аудита'},
    {'tool': 'pwsh', 'where': 'cmd',
     'pattern': r'\b(Get-Content|Select-String|findstr)\b', 'why': 'цитаты из журнала или файла'},
]

SEARCH_TOOLS = {'read', 'grep', 'glob', 'web_fetch', 'web_search', 'list_agents', 'job_output'}
COMMAND_TOOLS = {'pwsh', 'bash', 'pwsh-persistent', 'bash-persistent'}


def load_rows(directory):
    path = os.path.join(directory, 'rows.json')
    if not os.path.isfile(path):
        print('ERROR: нет %s (сначала scan_fail.py --out %s)' % (path, directory))
        sys.exit(2)
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def compile_rule(rule):
    return re.compile(rule['pattern'], re.I | re.M)


def match_rule(row, rule, rx):
    tool = rule.get('tool', '*')
    if tool not in ('*', row.get('tool')):
        return False
    where = rule.get('where', 'out')
    if where == 'out':
        if not rx.search(row.get('text') or ''):
            return False
    elif where == 'cmd':
        if not rx.search(row.get('cmd') or ''):
            return False
    elif where == 'tool':
        if not rx.search(row.get('tool') or ''):
            return False
    else:
        return False
    if rule.get('cmd_pattern'):
        if not re.search(rule['cmd_pattern'], row.get('cmd') or '', re.I | re.M):
            return False
    if rule.get('out_pattern'):
        if not re.search(rule['out_pattern'], row.get('text') or '', re.I | re.M):
            return False
    if rule.get('not_pattern'):
        if re.search(rule['not_pattern'], row.get('text') or '', re.I | re.M):
            return False
    return True


def classify_row(row, rules):
    for category in ('noise', 'expected'):
        for rule, rx in rules[category]:
            if match_rule(row, rule, rx):
                return category.upper(), rule.get('why') or ''
    if row.get('kind') == 'hard':
        return 'STRONG', 'isError или ненулевой код возврата'
    if row.get('tool') in SEARCH_TOOLS:
        return 'NOISE', 'шаблон сбоя встретился в прочитанном тексте, а не в работе команды'
    if row.get('tool') in COMMAND_TOOLS:
        return 'SOFT', 'код 0, но в выводе ошибка'
    return 'SOFT', 'код 0, но в выводе ошибка'


def main(argv=None):
    ap = argparse.ArgumentParser(description='Разложить строки аудита по видам и посчитать кластеры.')
    ap.add_argument('--dir', required=True, help='папка аудита (результат scan_fail.py)')
    ap.add_argument('--rules', help='свой JSON с правилами (expected/noise)')
    ap.add_argument('--quiet', action='store_true', help='не печатать таблицу')
    a = ap.parse_args(argv)

    directory = os.path.abspath(a.dir)
    rows = load_rows(directory)
    meta_path = os.path.join(directory, 'scan_meta.json')
    meta = {}
    if os.path.isfile(meta_path):
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)

    rules = {'expected': [(r, compile_rule(r)) for r in DEFAULT_EXPECTED],
             'noise': [(r, compile_rule(r)) for r in DEFAULT_NOISE]}
    if a.rules:
        try:
            with open(a.rules, encoding='utf-8') as f:
                user = json.load(f)
        except (OSError, ValueError) as e:
            print('ERROR: не прочитал --rules %s: %s' % (a.rules, e))
            return 2
        for category in ('expected', 'noise'):
            for item in user.get(category, []):
                try:
                    rules[category].append((item, compile_rule(item)))
                except re.error as e:
                    print('ERROR: плохое правило %r: %s' % (item, e))
                    return 2

    counts = {'STRONG': 0, 'SOFT': 0, 'EXPECTED': 0, 'NOISE': 0}
    clusters = {}
    for row in rows:
        category, why = classify_row(row, rules)
        row['category'] = category
        row['category_why'] = why
        counts[category] = counts.get(category, 0) + 1
        key = row.get('cluster') or (row.get('tool') + ' | ' + (row.get('signature') or ''))
        if category in ('STRONG', 'SOFT', 'EXPECTED'):
            entry = clusters.setdefault(key, {'cluster': key, 'tool': row.get('tool'),
                                              'strong': 0, 'soft': 0, 'expected': 0,
                                              'example': row.get('signature')})
            if category == 'STRONG':
                entry['strong'] += 1
            elif category == 'SOFT':
                entry['soft'] += 1
            else:
                entry['expected'] += 1

    calls = meta.get('calls') or 0
    real = counts.get('STRONG', 0) + counts.get('SOFT', 0)
    summary = {
        'rows': len(rows),
        'calls': calls,
        'counts': counts,
        'real': real,
        'real_per_1000_calls': round(real * 1000.0 / calls, 1) if calls else None,
        'meta': meta,
        'clusters': sorted(clusters.values(),
                           key=lambda c: (c['strong'] + c['soft'] + c['expected']), reverse=True),
    }
    with open(os.path.join(directory, 'classified.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    with open(os.path.join(directory, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    print('строк: %d, настоящих сбоев: %d (жёстких %d, мягких %d), ожидаемых %d, шума %d' % (
        len(rows), real, counts.get('STRONG', 0), counts.get('SOFT', 0),
        counts.get('EXPECTED', 0), counts.get('NOISE', 0)))
    if calls:
        print('вызовов: %d, настоящих сбоев на 1000 вызовов: %.1f' % (calls, summary['real_per_1000_calls']))
    if not a.quiet and clusters:
        print('')
        print('%-5s %-6s %-8s %s' % ('всего', 'hard', 'soft', 'кластер'))
        for c in summary['clusters'][:25]:
            total = c['strong'] + c['soft'] + c['expected']
            print('%-5d %-6d %-8d %s' % (total, c['strong'], c['soft'], (c['cluster'] or '')[:110]))
        print('')
        print('Папка аудита: %s' % directory)
    if len(rows) and real == 0:
        print('WARNING: настоящих сбоев нет. Проверь период и правила глазами (show.py).')
    return 0


if __name__ == '__main__':
    sys.exit(main())

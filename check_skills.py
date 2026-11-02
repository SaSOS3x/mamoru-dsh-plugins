#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_skills.py - проверка навыков этого репозитория перед коммитом.

Что проверяется:
  1. Фронтматтер каждого skills/<имя>/SKILL.md: name в kebab-case и совпадает с папкой,
     description одной строкой не длиннее 500 знаков (каталог DSH показывает его урезанным).
  2. Ни в одном SKILL.md не осталось переменных и путей Claude Code (CLAUDE_SKILL_DIR,
     CLAUDE_PLUGIN_ROOT, ~/.claude, .claude/skills, claude plugin).
  3. Относительные пути к файлам навыка (scripts/..., references/..., assets/...) существуют.
  4. Перед коммитом: у каждого изменённого навыка есть новая запись в его CHANGELOG.md
     (правило исходного репозитория; отключается ключом --no-git).

Запуск: python check_skills.py [--no-git]
Коды: 0 - всё в порядке, 1 - есть замечания, 2 - git недоступен.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(ROOT, 'skills')
MAX_DESCRIPTION = 500
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
PATH_RE = re.compile(r'(?<![\w/.-])((?:scripts|references|assets|tests|templates)/[A-Za-z0-9_.\-/]+)')
BANNED = ['CLAUDE_SKILL_DIR', 'CLAUDE_PLUGIN_ROOT', '~/.claude', '.claude/skills', 'claude plugin']
# Пути-примеры в тексте навыка: их в репозитории нет и быть не должно.
EXAMPLE_PATHS = {'tests/test_config.py'}

problems = []


def fail(msg):
    problems.append(msg)


def parse_frontmatter(text, path):
    m = re.match(r'---\r?\n(.*?)\r?\n---\r?\n', text, re.S)
    if not m:
        fail(f'{path}: нет фронтматтера (--- name/description ---)')
        return None
    fm = m.group(1)
    name = re.search(r'^name:\s*(.+)$', fm, re.M)
    desc = re.search(r'^description:\s*(.+)$', fm, re.M)
    if not name:
        fail(f'{path}: во фронтматтере нет name')
    if not desc:
        fail(f'{path}: во фронтматтере нет description')
    if not name or not desc:
        return None
    name = name.group(1).strip()
    desc = desc.group(1).strip()
    if len(desc) >= 2 and desc[0] == desc[-1] and desc[0] in '"\'':
        desc = desc[1:-1]
    return name.strip('"\''), desc


def check_skill(skill_name):
    folder = os.path.join(SKILLS, skill_name)
    path = os.path.join(folder, 'SKILL.md')
    if not os.path.isfile(path):
        fail(f'skills/{skill_name}: нет SKILL.md')
        return
    text = open(path, encoding='utf-8').read()
    fm = parse_frontmatter(text, f'skills/{skill_name}/SKILL.md')
    if fm:
        name, desc = fm
        if not NAME_RE.match(name):
            fail(f'skills/{skill_name}: name "{name}" не в kebab-case')
        if name != skill_name:
            fail(f'skills/{skill_name}: name "{name}" не совпадает с именем папки')
        if len(desc) > MAX_DESCRIPTION:
            fail(f'skills/{skill_name}: description {len(desc)} знаков, предел {MAX_DESCRIPTION}')
        if '\n' in desc:
            fail(f'skills/{skill_name}: description должен быть одной строкой')
    for token in BANNED:
        if token in text:
            fail(f'skills/{skill_name}: остался след Claude Code: {token}')
    for rel in sorted(set(PATH_RE.findall(text))):
        if rel in EXAMPLE_PATHS:
            continue
        if not os.path.exists(os.path.join(folder, rel)):
            fail(f'skills/{skill_name}: ссылка на {rel}, файла нет')
    if not os.path.isfile(os.path.join(folder, 'CHANGELOG.md')):
        fail(f'skills/{skill_name}: нет CHANGELOG.md')


def check_changelog_rule():
    def git(*args, allow_fail=False):
        r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        if r.returncode and not allow_fail:
            print(f'git {args[0]} failed in {ROOT}: git не установлен или это не репозиторий')
            sys.exit(2)
        return r.stdout.splitlines()

    # В репозитории без коммитов HEAD ещё не существует: тогда «изменено» значит «не в индексе».
    has_head = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=ROOT,
                              capture_output=True).returncode == 0
    tracked_changes = set(git('diff', '--name-only', 'HEAD')) if has_head else set()
    changed = tracked_changes | set(git('ls-files', '--others', '--exclude-standard'))
    skills = {p.split('/')[1] for p in changed if p.startswith('skills/') and p.count('/') >= 2}
    missing = sorted(s for s in skills if f'skills/{s}/CHANGELOG.md' not in changed)
    for s in missing:
        fail(f'skills/{s}: изменён, но новой записи в CHANGELOG.md нет')
    print(f'{len(skills)} изменённых навыков, {len(missing)} без записи в CHANGELOG')


def main():
    args = sys.argv[1:]
    if not os.path.isdir(SKILLS):
        print(f'нет папки {SKILLS}')
        return 1
    names = sorted(d for d in os.listdir(SKILLS) if os.path.isdir(os.path.join(SKILLS, d)))
    if not names:
        print('в skills/ нет ни одного навыка')
        return 1
    for n in names:
        check_skill(n)
    if '--no-git' not in args:
        check_changelog_rule()
    for p in problems:
        print(f'FAIL {p}')
    print(f'{len(names)} навыков, замечаний: {len(problems)}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())

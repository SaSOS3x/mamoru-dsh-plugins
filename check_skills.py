#!/usr/bin/env python3
"""check_skills.py - проверка навыков этого репозитория перед коммитом.

Раскладка: skills/<компонент>/<навык>/SKILL.md, компоненты - core и minecraft.
Проверки:
1. Фронтматтер каждого SKILL.md: name в kebab-case и совпадает с папкой навыка,
   description не длиннее 500 знаков и одной строкой.
2. Ни в одном SKILL.md не осталось переменных и путей Claude Code.
3. Ссылки вида scripts/..., references/..., assets/... существуют рядом с навыком.
4. У каждого навыка есть CHANGELOG.md.
5. package.json: name/version, dsh.bundle.patch, main, files включают lib и skills,
   exports содержат ./core и ./minecraft.
6. cordis.patch.yml монтирует компоненты mamoru-core/mamoru-minecraft.
7. Изменённый навык имеет новую запись в CHANGELOG.md (--no-git отключает).

Запуск: python check_skills.py [--no-git]
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(ROOT, 'skills')
GROUPS = ('core', 'minecraft')
MAX_DESCRIPTION = 500
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
PATH_RE = re.compile(r'(?<![\w/.-])((?:scripts|references|assets|tests|templates)/[A-Za-z0-9_.\-/]+)')
BANNED = ['CLAUDE_SKILL_DIR', 'CLAUDE_PLUGIN_ROOT', '~/.claude', '.claude/skills', 'claude plugin']
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


def check_skill(group, skill_name, folder):
    label = f'skills/{group}/{skill_name}'
    path = os.path.join(folder, 'SKILL.md')
    if not os.path.isfile(path):
        fail(f'{label}: нет SKILL.md')
        return
    text = open(path, encoding='utf-8').read()
    fm = parse_frontmatter(text, f'{label}/SKILL.md')
    if fm:
        name, desc = fm
        if not NAME_RE.match(name):
            fail(f'{label}: name "{name}" не в kebab-case')
        if name != skill_name:
            fail(f'{label}: name "{name}" не совпадает с именем папки')
        if len(desc) > MAX_DESCRIPTION:
            fail(f'{label}: description {len(desc)} знаков, предел {MAX_DESCRIPTION}')
        if '\n' in desc:
            fail(f'{label}: description должен быть одной строкой')
    for token in BANNED:
        if token in text:
            fail(f'{label}: остался след Claude Code: {token}')
    for rel in sorted(set(PATH_RE.findall(text))):
        if rel in EXAMPLE_PATHS:
            continue
        if not os.path.exists(os.path.join(folder, rel)):
            fail(f'{label}: ссылка на {rel}, файла нет')
    if not os.path.isfile(os.path.join(folder, 'CHANGELOG.md')):
        fail(f'{label}: нет CHANGELOG.md')


def discover():
    """Return [(group, name, folder)] and report unexpected layout."""
    found = []
    for entry in sorted(os.listdir(SKILLS)):
        path = os.path.join(SKILLS, entry)
        if not os.path.isdir(path):
            continue
        if os.path.isfile(os.path.join(path, 'SKILL.md')):
            fail(f'skills/{entry}: навык лежит в корне skills/, а должен быть в skills/<компонент>/')
            continue
        if entry not in GROUPS:
            fail(f'skills/{entry}: неизвестный компонент (ожидались {", ".join(GROUPS)})')
            continue
        for name in sorted(os.listdir(path)):
            folder = os.path.join(path, name)
            if os.path.isdir(folder) and os.path.isfile(os.path.join(folder, 'SKILL.md')):
                found.append((entry, name, folder))
    return found


def check_package(skill_folders):
    """Проверить обвязку, по которой менеджер плагинов DSH ставит пакет из Git."""
    path = os.path.join(ROOT, 'package.json')
    if not os.path.isfile(path):
        fail('package.json: нет файла (менеджер плагинов не увидит bundle)')
        return
    try:
        with open(path, encoding='utf-8') as f:
            manifest = json.load(f)
    except ValueError as e:
        fail(f'package.json: невалидный JSON ({e})')
        return

    if not manifest.get('name'):
        fail('package.json: нет name')
    if not manifest.get('version'):
        fail('package.json: нет version (менеджер плагинов сравнивает версии при обновлении)')

    bundle = (manifest.get('dsh') or {}).get('bundle') or {}
    patch = bundle.get('patch')
    if not patch:
        fail('package.json: нет dsh.bundle.patch (ошибка "declares no bundle")')
    else:
        patches = [patch] if isinstance(patch, str) else patch
        if not all(isinstance(p, str) for p in patches):
            fail('package.json: dsh.bundle.patch должен быть строкой или списком строк')
        else:
            for p in patches:
                if not os.path.isfile(os.path.join(ROOT, p)):
                    fail(f'package.json: dsh.bundle.patch ссылается на {p}, файла нет')

    main = manifest.get('main')
    if not main or not os.path.isfile(os.path.join(ROOT, main)):
        fail(f'package.json: main "{main}" не указывает на существующий файл')

    files = manifest.get('files')
    if not isinstance(files, list):
        fail('package.json: нет files (npm pack может не положить навыки в пакет)')
    else:
        joined = ' '.join(files)
        if 'skills' not in joined:
            fail('package.json: files не включают skills/ — установленный пакет будет без навыков')
        if 'lib' not in joined:
            fail('package.json: files не включают lib/ — установленный пакет будет без провайдера')
        for sub in ('lib/core.js', 'lib/minecraft.js'):
            if not os.path.isfile(os.path.join(ROOT, sub)):
                fail(f'{sub}: нет файла компонента')

    exports = manifest.get('exports') or {}
    for sub, target in (('./core', './lib/core.js'), ('./minecraft', './lib/minecraft.js')):
        if exports.get(sub) != target:
            fail(f'package.json: exports["{sub}"] должен быть "{target}"')

    engines = (manifest.get('engines') or {}).get('dsh')
    if not engines:
        print('WARN package.json: не объявлен engines.dsh (совместимость с DSH не проверяется)')

    patch_file = patch if isinstance(patch, str) else (patch[0] if patch else None)
    if patch_file and os.path.isfile(os.path.join(ROOT, patch_file)):
        text = open(os.path.join(ROOT, patch_file), encoding='utf-8').read()
        package_name = manifest.get('name')
        if 'insert:' not in text:
            fail(f'{patch_file}: нет секции insert: (слой ничего не монтирует)')
        for component in ('core', 'minecraft'):
            if f'{package_name}/{component}' not in text:
                fail(f'{patch_file}: не монтирует компонент {package_name}/{component}')
    for folder in skill_folders:
        if not os.path.isfile(os.path.join(folder, 'SKILL.md')):
            fail(f'{folder}: нет SKILL.md')


def check_changelog_rule():
    def git(*args, allow_fail=False):
        r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        if r.returncode and not allow_fail:
            print(f'git {args[0]} failed in {ROOT}: git не установлен или это не репозиторий')
            sys.exit(2)
        return r.stdout.splitlines()

    has_head = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=ROOT,
                              capture_output=True).returncode == 0
    # Переезд навыка между компонентами - это rename (R), а не правка: CHANGELOG ему не нужен.
    changed = set()
    if has_head:
        for line in git('diff', '--name-status', 'HEAD'):
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            status = parts[0]
            if status.startswith('R') or status.startswith('C'):
                continue
            changed.add(parts[-1])
    changed |= set(git('ls-files', '--others', '--exclude-standard'))
    # skills/<group>/<name>/файл -> <group>/<name>
    skills = set()
    for p in changed:
        parts = p.split('/')
        if len(parts) >= 4 and parts[0] == 'skills' and parts[1] in GROUPS:
            skills.add(f'{parts[1]}/{parts[2]}')
    missing = sorted(s for s in skills if f'skills/{s}/CHANGELOG.md' not in changed)
    for s in missing:
        fail(f'skills/{s}: изменён, но новой записи в CHANGELOG.md нет')
    print(f'{len(skills)} изменённых навыков, {len(missing)} без записи в CHANGELOG')


def main():
    args = sys.argv[1:]
    if not os.path.isdir(SKILLS):
        print(f'нет папки {SKILLS}')
        return 1
    found = discover()
    if not found:
        print('в skills/<компонент>/ нет ни одного навыка')
        return 1
    for group, name, folder in found:
        check_skill(group, name, folder)
    check_package([folder for _, _, folder in found])
    if '--no-git' not in args:
        check_changelog_rule()
    for p in problems:
        print(f'FAIL {p}')
    print(f'{len(found)} навыков, замечаний: {len(problems)}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())

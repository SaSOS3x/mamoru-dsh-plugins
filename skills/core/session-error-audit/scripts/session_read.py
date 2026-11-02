#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""session_read.py - доступ к журналам сессий DeepSeek Harness.

Раскладка журналов DSH:

    <DSH_HOME>/sessions/--<нормализованный cwd>--/session-<id>/session.vN.jsonl.zstd

Файл - конкатенация независимых Zstandard-кадров (по кадру на пакет событий), поэтому
обычный `zstd -d` и модуль zstandard читают его целиком, а однокадровые API - нет.
В ZIP из `/export` (меню сессии → Download session log) те же строки лежат несжатыми
как `session.vN.jsonl`. Этот модуль умеет все три вида: .jsonl, .jsonl.zstd и .zip.

Зависимости: только стандартная библиотека, плюс один из вариантов для .zstd -
модуль `zstandard` (pip install zstandard) или программа `zstd` в PATH.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

SESSION_FILE_RE = re.compile(r'^session(?:\.v(\d+))?\.jsonl(\.zstd)?$')


class SessionReadError(Exception):
    pass


def dsh_home():
    home = os.environ.get('DSH_HOME')
    if home:
        return home
    return os.path.join(os.path.expanduser('~'), '.dsh')


def sessions_root(explicit=None):
    if explicit:
        return os.path.abspath(explicit)
    return os.path.join(dsh_home(), 'sessions')


def project_slug(path):
    """Как DSH называет папку проекта: --<путь, где каждый не-алфанумерический знак -> ->--."""
    norm = re.sub(r'[^A-Za-z0-9]', '-', os.path.abspath(path).rstrip('\\/'))
    return '--' + norm + '--'


def _zstd_binary():
    for name in ('zstd', 'zstd.exe'):
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'zstd', 'zstd.exe'),
        r'C:\msys64\ucrt64\bin\zstd.exe',
        r'C:\msys64\usr\bin\zstd.exe',
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def zstd_hint():
    return (
        'Журнал сжат Zstandard, а распаковать нечем. Поставь одно из двух:\n'
        '  python -m pip install zstandard\n'
        '  или положи zstd.exe в PATH (https://facebook.github.io/zstd/)\n'
        'Либо распакуй сессию в интерфейсе DSH: меню сессии -> Download session log, '
        'и передай скрипту ZIP или папку из архива ключом --export.'
    )


def _lines_zstd(path):
    try:
        import zstandard  # type: ignore
    except ImportError:
        zstandard = None
    if zstandard is not None:
        dctx = zstandard.ZstdDecompressor()
        with open(path, 'rb') as raw:
            try:
                reader = dctx.stream_reader(raw, read_across_frames=True)
            except TypeError:
                reader = dctx.stream_reader(raw)
            try:
                text = io.TextIOWrapper(reader, encoding='utf-8', errors='replace')
                for line in text:
                    yield line
            finally:
                text.close()
        return
    binary = _zstd_binary()
    if not binary:
        raise SessionReadError(zstd_hint())
    proc = subprocess.run([binary, '-d', '-c', '-q', path], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise SessionReadError('zstd не распаковал %s: %s' % (
            path, proc.stderr.decode('utf-8', 'replace').strip()[:400]))
    for line in proc.stdout.decode('utf-8', 'replace').splitlines():
        yield line


def _lines_plain(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            yield line


class SessionSource(object):
    """Один журнал: открывается заново на каждый проход."""

    def __init__(self, label, origin, opener, cwd=None):
        self.label = label
        self.origin = origin
        self._opener = opener
        self.cwd = cwd
        self.header = None

    def lines(self):
        return self._opener()

    def load_header(self):
        if self.header is not None:
            return self.header
        for line in self.lines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get('type') == 'session':
                self.header = rec
                self.cwd = rec.get('cwd') or self.cwd
                return self.header
        self.header = {}
        return self.header

    def id(self):
        header = self.load_header()
        return header.get('id') or self.label


def _file_session_source(path, project_dir):
    label = os.path.basename(os.path.dirname(path))
    if path.endswith('.zstd'):
        opener = (lambda p=path: _lines_zstd(p))
    else:
        opener = (lambda p=path: _lines_plain(p))
    return SessionSource(label=label, origin=path, opener=opener)


def _zip_session_sources(zip_path):
    sources = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename
            base = name.rsplit('/', 1)[-1]
            if not SESSION_FILE_RE.match(base) or info.is_dir():
                continue
            def opener(z=zip_path, n=name):
                with zipfile.ZipFile(z) as zz:
                    data = zz.read(n).decode('utf-8', 'replace')
                for line in data.splitlines():
                    yield line
            label = os.path.basename(zip_path) + ':' + name
            sources.append(SessionSource(label=label, origin=zip_path + '!' + name, opener=opener))
    return sources


def find_sources(sessions=None, project=None, session_id=None, export=None):
    """Собрать журналы: из корня сессий (с фильтрами) или из ZIP/папки экспорта."""
    if export:
        export = os.path.abspath(export)
        if os.path.isfile(export) and export.lower().endswith('.zip'):
            sources = _zip_session_sources(export)
        elif os.path.isdir(export):
            sources = []
            for root, dirs, files in os.walk(export):
                for f in files:
                    if SESSION_FILE_RE.match(f):
                        sources.append(_file_session_source(os.path.join(root, f), root))
        else:
            raise SessionReadError('не найдено: %s (нужен ZIP из /export или папка)' % export)
        return _filter_sources(sources, project=project, session_id=session_id)

    root = sessions_root(sessions)
    if not os.path.isdir(root):
        raise SessionReadError('нет корня журналов: %s (передай --sessions или --export)' % root)

    project_dirs = []
    if project:
        slug = project_slug(project)
        direct = os.path.join(root, slug)
        if os.path.isdir(direct):
            project_dirs.append(direct)
        else:
            # Нормализация могла не совпасть (редкие символы) - проверим заголовки.
            project_dirs = [os.path.join(root, d) for d in os.listdir(root)
                            if os.path.isdir(os.path.join(root, d))]
    else:
        project_dirs = [os.path.join(root, d) for d in os.listdir(root)
                        if os.path.isdir(os.path.join(root, d))]

    sources = []
    for pdir in project_dirs:
        for sdir in sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []:
            path = _latest_session_file(os.path.join(pdir, sdir))
            if path:
                sources.append(_file_session_source(path, pdir))
    return _filter_sources(sources, project=project, session_id=session_id, slug_checked=True)


def _latest_session_file(sdir):
    if not os.path.isdir(sdir):
        return None
    best = None
    best_ver = -1
    for name in os.listdir(sdir):
        m = SESSION_FILE_RE.match(name)
        if not m:
            continue
        ver = int(m.group(1) or 0)
        if ver > best_ver:
            best_ver = ver
            best = os.path.join(sdir, name)
    return best


def _filter_sources(sources, project=None, session_id=None, slug_checked=False):
    out = []
    for src in sources:
        if session_id and session_id not in src.label and session_id not in os.path.basename(src.origin):
            continue
        if project and not slug_checked:
            header = src.load_header()
            cwd = header.get('cwd')
            if cwd and os.path.normcase(os.path.abspath(cwd)) != os.path.normcase(os.path.abspath(project)):
                continue
        elif project and slug_checked:
            header = src.load_header()
            cwd = header.get('cwd')
            if cwd and os.path.normcase(os.path.abspath(cwd)) != os.path.normcase(os.path.abspath(project)):
                continue
        out.append(src)
    return out


def iter_events(source):
    """События журнала: (seq, type, time, data). Заголовок тоже отдаётся с type='session'."""
    for line in source.lines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        yield rec.get('seq'), rec.get('type'), rec.get('time'), rec.get('data'), rec


def main(argv=None):
    """Небольшая диагностика: перечислить найденные журналы."""
    import argparse
    ap = argparse.ArgumentParser(description='Показать журналы сессий DSH, которые найдёт аудит.')
    ap.add_argument('--sessions', help='корень журналов (по умолчанию $DSH_HOME/sessions)')
    ap.add_argument('--project', help='папка проекта: только её сессии')
    ap.add_argument('--session', help='id сессии')
    ap.add_argument('--export', help='ZIP из /export или папка с session.vN.jsonl')
    a = ap.parse_args(argv)
    try:
        sources = find_sources(sessions=a.sessions, project=a.project, session_id=a.session, export=a.export)
    except SessionReadError as e:
        print('ERROR: %s' % e)
        return 2
    for src in sources:
        header = src.load_header()
        print('%s\t%s\tcwd=%s\tdepth=%s\t%s' % (
            header.get('id', '?'), os.path.basename(header.get('agentPreset', '') or '') or '-',
            header.get('cwd', '-'), header.get('delegationDepth', 0), src.origin))
    print('%d журналов' % len(sources))
    if not sources:
        print('WARNING: ничего не найдено - проверь --sessions/--project/--export')
    return 0


if __name__ == '__main__':
    sys.exit(main())

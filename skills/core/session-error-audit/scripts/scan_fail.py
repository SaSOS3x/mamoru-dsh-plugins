#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_fail.py - первый шаг аудита ошибок сессии DSH: найти упавшие вызовы инструментов.

Читает журналы сессий DeepSeek Harness (основная сессия и все подагенты), сопоставляет
каждый вызов инструмента с его результатом и пишет строку, если вызов упал:

  * жёсткий сбой - результат помечен isError, фоновая команда завершилась не с "completed",
    или в выводе есть маркер `[exit code: N]` с N, отличным от 0;
  * мягкий сбой - isError нет, но в выводе Traceback, "No such file", "is not recognized
    as the name of a cmdlet", NativeCommandError, отказано в доступе и подобное.

Результат: rows.json, scan_meta.json и user_messages.json в папке --out.

Пример:
  python scripts/scan_fail.py --project "C:/work/myproject" --out _project/audit/2026-11-02
  python scripts/scan_fail.py --export dsh-session-<id>.zip --out _project/audit/2026-11-02
  python scripts/scan_fail.py --project . --since 2026-10-12 --until 2026-10-15T11:48Z --out tmp
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session_read  # noqa: E402

EXIT_RE = re.compile(r'\[exit code:\s*(-?\d+)\]', re.I)

SOFT_PATTERNS = [
    r'Traceback \(most recent call last\)',
    r'\bNo such file\b',
    r'\bnot recognized as the name of a cmdlet\b',
    r'\bCommandNotFoundException\b',
    r'\bNativeCommandError\b',
    r'is not recognized as an internal or external command',
    r'\bAccess is denied\b',
    r'\bcannot find path\b',
    r'Could not find a part of the path',
    r'\bUnauthorizedAccessException\b',
    r'\bPermission denied\b',
    r'\bdenied\b',
    r'Exception in thread',
    r'^\s*Caused by:',
    r'\bModuleNotFoundError\b',
    r'\bImportError\b',
    r'\bUnicodeEncodeError\b',
    r'\bUnicodeDecodeError\b',
    r'\bSyntaxError\b',
    r'\bJSONDecodeError\b',
    r'\bERROR:\s',
    r'\bfatal:\s',
    r'\bFAILURE: Build failed\b',
    r'\bFileNotFoundError\b',
    r'\bKeyError\b',
    r'\bTypeError\b',
]
SOFT_RE = [re.compile(p, re.M) for p in SOFT_PATTERNS]

FAILED_JOB_STATUS = {'failed', 'error', 'cancelled', 'canceled', 'timeout', 'timed-out'}


def parse_time(value, name):
    """Время: epoch ms, дата, ...T23:11Z, ...+00:00, полная метка ISO."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r'\d{10,13}', text):
        n = int(text)
        if n > 10 ** 12:
            n //= 1000
        return datetime.datetime.fromtimestamp(n, datetime.timezone.utc)
    candidate = text.replace('Z', '+00:00')
    for fmt in (None, '%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'):
        try:
            dt = datetime.datetime.fromisoformat(candidate) if fmt is None else datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    print('ERROR: не разобрал время %s=%r (нужно 2026-10-12, 2026-10-12T23:11Z или ISO)' % (name, value))
    sys.exit(2)


def iso(ms):
    if ms is None:
        return None
    return datetime.datetime.fromtimestamp(ms / 1000.0, datetime.timezone.utc).isoformat().replace('+00:00', 'Z')


def text_of(message):
    content = (message or {}).get('content')
    if isinstance(content, str):
        return content
    parts = []
    for item in content or []:
        if isinstance(item, dict):
            if item.get('type') == 'text':
                parts.append(item.get('text') or '')
            elif item.get('type') == 'image':
                parts.append('[image]')
    return '\n'.join(p for p in parts if p)


def command_preview(tool, arguments):
    try:
        args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() else (arguments or {})
    except ValueError:
        return (arguments or '')[:300]
    if isinstance(args, dict):
        for key in ('command', 'cmd', 'path', 'file_path', 'pattern', 'description', 'prompt', 'query', 'url'):
            if args.get(key):
                return str(args[key])[:300].replace('\r', ' ')
    return json.dumps(args, ensure_ascii=False)[:300].replace('\r', ' ')


NOISE_LINE_PREFIXES = (
    '+ ', '+', 'At line:', 'строка:', 'CategoryInfo', 'FullyQualifiedErrorId',
    'Операнд', 'операнд', '[stderr]', '----', 'Name', '---',
)
ERROR_HINT_RE = re.compile(
    r'error|exception|traceback|не удается|не найден|not found|no such|denied|failed|fatal|'
    r'cannot|could not|unable|refused|отказано|не распознан|not recognized',
    re.I)


def normalize_signature(text):
    """Короткая подпись ошибки: первая осмысленная строка с ошибкой, числа обезличены."""
    lines = [l.strip() for l in (text or '').splitlines() if l.strip()]
    pick = ''
    for line in lines:
        if line.startswith(NOISE_LINE_PREFIXES):
            continue
        if EXIT_RE.fullmatch(line):
            continue
        if ERROR_HINT_RE.search(line):
            pick = line
            break
    if not pick:
        for line in reversed(lines):
            if line.startswith(NOISE_LINE_PREFIXES) or EXIT_RE.search(line) and len(line) < 40:
                continue
            pick = line
            break
    if not pick and lines:
        pick = lines[0]
    pick = EXIT_RE.sub('[exit code: N]', pick)
    pick = re.sub(r'0x[0-9a-fA-F]+', '0x?', pick)
    pick = re.sub(r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*', '<time>', pick)
    pick = re.sub(r'\b\d+\b', 'N', pick)
    pick = re.sub(r'\s+', ' ', pick).strip()
    return pick[:160]


def exit_code_of(text, detail=None):
    for source in (detail, text):
        if not source:
            continue
        m = EXIT_RE.search(source)
        if m:
            return int(m.group(1))
    return None


def is_soft(text):
    if not text:
        return False
    return any(rx.search(text) for rx in SOFT_RE)


def scan_session(src):
    """Разобрать один журнал. Возвращает (rows, users, calls_count, last_ts)."""
    calls = {}
    rows = []
    users = []
    last_ts = None
    for seq, etype, etime, data, rec in session_read.iter_events(src):
        ts = etime if isinstance(etime, (int, float)) else None
        if ts and (last_ts is None or ts > last_ts):
            last_ts = ts
        if etype == 'tool/call' and data:
            call_id = data.get('callId')
            if call_id:
                calls[call_id] = {
                    'tool': data.get('name') or '?',
                    'cmd': command_preview(data.get('name'), data.get('arguments')),
                    'turn': data.get('turn'),
                    'step': data.get('step'),
                    'time': ts,
                }
        elif etype == 'tool/result' and data:
            message = data.get('message') or {}
            call_id = message.get('toolCallId') or (data.get('source') or {}).get('callId')
            call = calls.get(call_id, {})
            text = text_of(message)
            hard = bool(message.get('isError'))
            code = exit_code_of(text)
            if code not in (None, 0):
                hard = True
            soft = (not hard) and is_soft(text)
            if not (hard or soft):
                continue
            tool = call.get('tool') or '?'
            rows.append({
                'session': src.label,
                'session_id': src.id(),
                'cwd': src.cwd,
                'depth': (src.load_header() or {}).get('delegationDepth', 0),
                'agent_preset': (src.load_header() or {}).get('agentPreset'),
                'call_id': call_id,
                'tool': tool,
                'cmd': call.get('cmd') or '',
                'turn': call.get('turn'),
                'step': call.get('step'),
                'time': iso(ts or call.get('time')),
                'seq': seq,
                'is_error': bool(message.get('isError')),
                'kind': 'hard' if hard else 'soft',
                'exit_code': code,
                'job_status': None,
                'text': text[-4000:],
                'signature': normalize_signature(text),
                'cluster': tool + ' | ' + normalize_signature(text),
            })
        elif etype == 'job/settled' and data:
            status = (data.get('status') or '').lower()
            detail = data.get('detail') or ''
            call = data.get('toolCall') or {}
            call_id = call.get('callId') or call.get('rootCallId')
            code = exit_code_of(detail)
            failed = status in FAILED_JOB_STATUS or code not in (None, 0)
            if not failed:
                continue
            meta = calls.get(call_id, {})
            rows.append({
                'session': src.label,
                'session_id': src.id(),
                'cwd': src.cwd,
                'depth': (src.load_header() or {}).get('delegationDepth', 0),
                'agent_preset': (src.load_header() or {}).get('agentPreset'),
                'call_id': call_id,
                'tool': meta.get('tool') or (data.get('kind') or 'job'),
                'cmd': meta.get('cmd') or (data.get('label') or ''),
                'turn': meta.get('turn'),
                'step': meta.get('step'),
                'time': iso(ts),
                'seq': seq,
                'is_error': True,
                'kind': 'hard',
                'exit_code': code,
                'job_status': status or None,
                'text': ('job %s: status=%s detail=%s' % (data.get('jobId'), status, detail))[:4000],
                'signature': normalize_signature(detail or ('job ' + status)),
                'cluster': (meta.get('tool') or data.get('kind') or 'job') + ' | ' + normalize_signature(detail or status),
            })
        elif etype == 'user/message' and data:
            text = text_of(data)
            if text.strip():
                users.append({'session': src.label, 'session_id': src.id(), 'time': iso(ts), 'text': text[:4000]})

    # Один вызов - одна строка: результат инструмента главнее события фоновой задачи.
    deduped = {}
    for row in rows:
        key = row['call_id'] or ('%s:%s' % (row['session'], row['seq']))
        prev = deduped.get(key)
        if prev is None or (prev.get('job_status') and not row.get('job_status')):
            deduped[key] = row
    rows = sorted(deduped.values(), key=lambda r: (r['session'], r['seq'] or 0))
    return rows, users, len(calls), last_ts


def main(argv=None):
    ap = argparse.ArgumentParser(description='Найти упавшие вызовы инструментов в журналах сессий DSH.')
    ap.add_argument('--project', help='папка проекта: берутся только его сессии')
    ap.add_argument('--sessions', help='корень журналов (по умолчанию $DSH_HOME/sessions)')
    ap.add_argument('--export', help='ZIP из /export или папка с session.vN.jsonl')
    ap.add_argument('--session', help='id одной сессии')
    ap.add_argument('--since', help='начало периода (UTC): дата или ISO')
    ap.add_argument('--until', help='конец периода (UTC)')
    ap.add_argument('--out', required=True, help='рабочая папка аудита')
    a = ap.parse_args(argv)

    since = parse_time(a.since, '--since')
    until = parse_time(a.until, '--until')
    if not a.project and not a.export and not a.sessions:
        print('ERROR: укажи --project или --export (или --sessions)')
        return 2

    try:
        sources = session_read.find_sources(
            sessions=a.sessions, project=a.project, session_id=a.session, export=a.export)
    except session_read.SessionReadError as e:
        print('ERROR: %s' % e)
        return 2

    out_dir = os.path.abspath(a.out)
    os.makedirs(out_dir, exist_ok=True)

    all_rows = []
    all_users = []
    total_calls = 0
    last_ts = None
    files = 0
    for src in sources:
        try:
            rows, users, calls_count, session_last = scan_session(src)
        except session_read.SessionReadError as e:
            print('ERROR: %s' % e)
            return 2
        if calls_count == 0 and not rows:
            continue
        files += 1
        total_calls += calls_count
        for row in rows:
            if since or until:
                if not row.get('time'):
                    continue
                dt = parse_time(row['time'], 'time')
                if since and dt < since:
                    continue
                if until and dt > until:
                    continue
            all_rows.append(row)
        for u in users:
            if since or until:
                if not u.get('time'):
                    continue
                dt = parse_time(u['time'], 'time')
                if since and dt < since:
                    continue
                if until and dt > until:
                    continue
            all_users.append(u)
        if session_last and (last_ts is None or session_last > last_ts):
            last_ts = session_last

    with open(os.path.join(out_dir, 'rows.json'), 'w', encoding='utf-8') as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, 'user_messages.json'), 'w', encoding='utf-8') as f:
        json.dump(all_users, f, ensure_ascii=False, indent=1)

    meta = {
        'tool': 'scan_fail.py',
        'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z'),
        'project': os.path.abspath(a.project) if a.project else None,
        'sessions_root': session_read.sessions_root(a.sessions) if not a.export else None,
        'export': os.path.abspath(a.export) if a.export else None,
        'session': a.session,
        'files': files,
        'calls': total_calls,
        'rows': len(all_rows),
        'hard': sum(1 for r in all_rows if r['kind'] == 'hard'),
        'soft': sum(1 for r in all_rows if r['kind'] == 'soft'),
        'user_messages': len(all_users),
        'since': a.since,
        'until': a.until,
        'last_ts': iso(last_ts),
    }
    with open(os.path.join(out_dir, 'scan_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    print('журналов: %d, вызовов: %d, строк: %d (жёстких %d, мягких %d), реплик пользователя: %d' % (
        files, total_calls, len(all_rows), meta['hard'], meta['soft'], len(all_users)))
    print('папка аудита: %s' % out_dir)
    if not sources:
        print('WARNING: журналов не найдено - это не "сбоев нет", а неверный --project/--export/--since')
        return 2
    if files and not all_rows:
        print('WARNING: ни одного упавшего вызова. Проверь период и что журналы не пустые.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

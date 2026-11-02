#!/usr/bin/env python3
"""journal_compact.py - keeps a project journal short without losing a byte of it.

  check   JOURNAL.md [--max-lines 400]
      Size report. Says COMPACT when the file is longer than --max-lines.
  compact JOURNAL.md [--keep 15] [--archive NAME] [--index-types решение] [--dry-run]
      Moves every entry except the last --keep, verbatim and in order, to the end of the archive (default JOURNAL-архив.md next
      to the journal). Rewrites the index block at the top of the journal (archive range, archived entries of --index-types) and
      adds an empty summary block if there is none. Writes nothing unless the moved text is found in the new archive byte for byte.
  verify  JOURNAL.md [--archive NAME] [--max-summary 30]
      Checks the summary block: every line must end with a reference (-> YYYY-MM-DD | <second field> [| <start of title>])
      that matches exactly one entry of the journal or the archive, and the block may not hold more than --max-summary lines
      (headings and blank lines are not counted).

An entry starts with a heading line '## YYYY-MM-DD | ...'. Text before the first entry (title, summary, index) stays in place.
Exit codes: 0 ok, 1 a check failed (nothing written), 2 bad input.
"""
import argparse, hashlib, os, re, sys

ENTRY = re.compile(r'^## (\d{4}-\d{2}-\d{2}) \|', re.M)
REF = re.compile(r'\((?:→|->) ?(\d{4}-\d{2}-\d{2}) \| ([^|)]+?)(?: \| ([^)]+?))?\)\s*$')
IDX = ('<!-- journal-index:start -->', '<!-- journal-index:end -->')
SUM = ('<!-- journal-summary:start -->', '<!-- journal-summary:end -->')


def read(path):
    with open(path, encoding='utf-8', newline='') as f:
        return f.read()


def write(path, text):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    os.replace(tmp, path)


def split(text):
    starts = [m.start() for m in ENTRY.finditer(text)]
    if not starts:
        return text, []
    return text[:starts[0]], [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]


def fields(entry):
    return [f.strip() for f in entry.split('\n', 1)[0].rstrip('\r')[3:].split('|')]


def block(text, marks):
    a, b = text.find(marks[0]), text.find(marks[1])
    return (a, b + len(marks[1])) if a >= 0 and b > a else None


def archive_path(journal, name):
    return os.path.join(os.path.dirname(os.path.abspath(journal)), name)


def check(a):
    text = read(a.journal)
    head, entries = split(text)
    lines = text.count('\n')
    print(f'{a.journal}: {lines} lines, {len(text)} chars (~{len(text) // 3} tokens), {len(entries)} entries, header {head.count(chr(10))} lines')
    print(f'COMPACT: more than {a.max_lines} lines, run "compact --keep 15"' if lines > a.max_lines else f'OK: not more than {a.max_lines} lines')
    return 0


def compact(a):
    text = read(a.journal)
    nl = '\r\n' if '\r\n' in text and text.count('\r\n') == text.count('\n') else '\n'  # mixed line endings: LF
    head, entries = split(text)
    if len(entries) <= a.keep:
        print(f'nothing to move: {len(entries)} entries, --keep {a.keep}')
        return 0
    move, stay = entries[:-a.keep], entries[-a.keep:]
    moved = ''.join(move)
    if not moved.endswith('\n'):
        print('ERROR: the last moved entry does not end with a newline'); return 1
    apath = archive_path(a.journal, a.archive)
    old = read(apath) if os.path.exists(apath) else (
        f'# Архив дневника{nl}{nl}Записи перенесены из {os.path.basename(a.journal)} дословно и по порядку (journal_compact.py).{nl}{nl}')
    if old and not old.endswith('\n'):
        old += nl
    archive = old + moved
    archived = split(archive)[1]
    listed = [e for e in archived if len(fields(e)) > 1 and fields(e)[1] in a.index_types]
    index = [IDX[0], f'Архив: записей {len(archived)} с {fields(archived[0])[0]} по {fields(archived[-1])[0]} в `{a.archive}` '
             '(найти запись: grep по её заголовку).']
    if listed:
        index.append('Записи типов ' + ', '.join(a.index_types) + ' в архиве:')
        index += ['- ' + ' | '.join(fields(e)) for e in listed]
    index = nl.join(index + [IDX[1]]) + nl
    summary = nl.join([SUM[0], '## Сводка архива', 'Пусто. Напиши по навыку project-journal (раздел "Сжатие дневника", шаг 2): до 30 строк, '
                       'каждая кончается ссылкой (→ ГГГГ-ММ-ДД | поле | начало названия) на запись.', SUM[1]]) + nl
    body = head
    span = block(body, IDX)
    body = body[:span[0]] + index.rstrip('\r\n') + body[span[1]:] if span else body.rstrip('\r\n') + nl + nl + index + nl
    if not block(body, SUM):
        span = block(body, IDX)
        body = body[:span[0]] + summary + nl + body[span[0]:]
    if not body.endswith(nl + nl):
        body = body.rstrip('\r\n') + nl + nl
    journal = body + ''.join(stay)
    ok = (archive.endswith(moved) and split(journal)[1] == stay and archived[-len(move):] == move
          and ''.join(move + stay) == ''.join(entries))
    digest = hashlib.sha256(moved.encode('utf-8')).hexdigest()[:16]
    report = (f'move {len(move)} entries ({fields(move[0])[0]}..{fields(move[-1])[0]}, sha256 {digest}), keep {len(stay)}; '
              f'journal {text.count(chr(10))} -> {journal.count(chr(10))} lines, archive {archive.count(chr(10))} lines')
    if not ok:
        print('ERROR: self-check failed, nothing written: ' + report); return 1
    if a.dry_run:
        print('dry run: ' + report); return 0
    write(apath, archive)
    write(a.journal, journal)
    if not read(apath).endswith(moved) or split(read(a.journal))[1] != stay:
        print('ERROR: files differ after writing: ' + report); return 1
    print('done: ' + report)
    return 0


def verify(a):
    text = read(a.journal)
    span = block(text, SUM)
    if not span:
        print('ERROR: no summary block'); return 1
    known = []
    apath = archive_path(a.journal, a.archive)
    for src in [text] + ([read(apath)] if os.path.exists(apath) else []):
        for e in split(src)[1]:
            f = fields(e)
            if len(f) > 1:
                known.append((f[0], f[1], f[-1]))
    bad = lines = 0
    for line in text[span[0]:span[1]].splitlines()[1:-1]:
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        lines += 1
        m = REF.search(s)
        hits = [k for k in known if m and k[0] == m.group(1) and k[1] == m.group(2).strip()
                and (not m.group(3) or k[2].startswith(m.group(3).strip()))] if m else []
        if len(hits) != 1:
            bad += 1
            print(('AMBIGUOUS (add the start of the title): ' if len(hits) > 1 else 'NO SOURCE: ') + s[:160])
    if lines > a.max_summary:
        print(f'TOO LONG: {lines} summary lines (headings and blank lines not counted), limit {a.max_summary}')
    print(f'summary: {lines} lines, {bad} without exactly one matching entry')
    return 1 if bad or lines > a.max_summary else 0


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('command', choices=['check', 'compact', 'verify'])
    p.add_argument('journal')
    p.add_argument('--max-lines', type=int, default=400)
    p.add_argument('--keep', type=int, default=15)
    p.add_argument('--max-summary', type=int, default=30)
    p.add_argument('--archive', default='JOURNAL-архив.md')
    p.add_argument('--index-types', nargs='+', default=['решение'])
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    if not os.path.isfile(a.journal):
        print(f'ERROR: no file {a.journal}'); return 2
    if a.keep < 1:
        print('ERROR: --keep must be at least 1'); return 2
    return {'check': check, 'compact': compact, 'verify': verify}[a.command](a)


if __name__ == '__main__':
    sys.exit(main())

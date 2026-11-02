#!/usr/bin/env python
"""check_text.py - механическая проверка текста по правилам readable-docs.
Запуск: python check_text.py ФАЙЛ [--max-list 40] [--max-sentence 25]
Читает .docx .md .txt напрямую, остальное (html, odt, pdf) через pandoc или pdftotext.
Коды возврата: 0 - жёсткие правила соблюдены; 1 - найдены длинные тире, стрелки-символы
или доля списков выше предела; 2 - сбой самого скрипта (нет файла, битый docx, нет pandoc).
Текст формул Word (OMML) скрипт не читает: стрелка внутри формулы - часть формулы."""
import re, subprocess, sys, zipfile
import xml.etree.ElementTree as ET

for _s in (sys.stdout, sys.stderr):  # на Windows консоль может быть cp1251
    try:
        _s.reconfigure(encoding='utf-8')
    except Exception:
        pass

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
DASH = {'—': 'длинное тире', '–': 'среднее тире', '‒': 'цифровое тире', '―': 'черта'}
DASH_RE = re.compile('[‒-―]|(?<=\\s)-{2,3}(?=\\s)')
# стрелки-символы: блоки Arrows, Supplemental Arrows-A/B, стрелки Dingbats и Miscellaneous Symbols and Arrows
ARROW_RE = re.compile('[\u2190-\u21ff\u27f0-\u27ff\u2900-\u297f\u2794-\u27af\u2b00-\u2b11\u2b60-\u2b6f\u2b95]')
BULLET = re.compile('^\\s*(?:[-*+•·▪●‣–—]\\s+|\\(?\\d{1,3}[.)]\\s+|[a-zа-яё]\\)\\s+)')
LABEL = re.compile(r'^\s*\*\*[^*\n]{1,60}\*\*\s*[:.\-]|^\s*\*\*[^*\n]{1,60}[:.]\*\*')
SENT = re.compile('(?<=[.!?…])\\s+(?=[A-ZА-ЯЁ«"(\\d])')
HEAVY = [  # канцелярит и тяжёлые обороты: (шаблон, чем заменить)
    (r'\bявля[ею]тся\b', 'это / убрать'),
    (r'\bданн(?:ый|ая|ое|ого|ой|ому|ом|ую)\b', 'этот'),  # без 'данные' и 'данных': это ещё и существительное
    (r'\bосуществля\w+', 'глагол действия'),
    (r'\bв целях\b|\bс целью\b', 'чтобы'),
    (r'\bв случае,? если\b|\bпри наличии\b', 'если / если есть'),
    (r'\bв связи с тем,? что\b|\bввиду того,? что\b', 'потому что'),
    (r'\bпосредством\b', 'через / с помощью'),
    (r'\bпредставля[ею]т собой\b', 'это'),
    (r'\bне представляется возможным\b', 'нельзя / не получится'),
    (r'\bв настоящее время\b|\bна сегодняшний день\b', 'сейчас'),
    (r'\bв рамках\b', 'в / при / убрать'),
    (r'\bимеет место\b', 'есть / бывает'),
    (r'\bпроизвод(?:ит|ят|ить|ится|ятся) \w+(?:ние|цию|ку)\b', 'один глагол'),
    (r'\bвышеуказанн\w+|\bнижеследующ\w+', 'этот / такой'),
]

def md_blocks(text):
    """Делит markdown или простой текст на блоки (тип, текст): p, li, h, code, table."""
    out, buf, kind, fence = [], [], None, False
    def flush():
        nonlocal buf, kind
        if buf:
            out.append((kind, ' '.join(buf)))
        buf, kind = [], None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(('```', '~~~')):
            flush(); fence = not fence
        elif fence:
            out.append(('code', s))
        elif not s or re.fullmatch(r'[\s|:=\-]+', s):  # пустая строка, черта, разделитель таблицы
            flush()
        elif re.match(r'#{1,6}\s', s):
            flush(); out.append(('h', s))
        elif s.startswith('|') or re.match(r'<!--|</?(table|tr|td|th|div|br)', s):
            flush(); out.append(('table', s))
        elif BULLET.match(line):
            flush(); kind, buf = 'li', [s]
        else:
            kind = kind or 'p'; buf.append(s)
    flush()
    return out

def docx_blocks(path):
    """Читает готовый .docx: абзацы, таблицы, колонтитулы, сноски и маркеры списков."""
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    heads, lists = set(), set()
    if 'word/styles.xml' in names:  # стиль узнаём по имени: в русском Word id заголовка может быть просто "1"
        for st in ET.fromstring(z.read('word/styles.xml')).iter(W + 'style'):
            sid, nm = st.get(W + 'styleId', ''), st.find(W + 'name')
            name = (nm.get(W + 'val', '') if nm is not None else '') + ' ' + sid
            if re.search(r'(?i)heading|title|заголов', name):
                heads.add(sid)
            if st.find(f'{W}pPr/{W}numPr') is not None or re.search(r'(?i)list ?(bullet|number)', name):
                lists.add(sid)
    root = ET.fromstring(z.read('word/document.xml'))
    out = []
    for el in root.find(W + 'body'):
        if el.tag == W + 'tbl':
            out.append(('table', ' '.join(t.text or '' for t in el.iter(W + 't'))))
        if el.tag != W + 'p':
            continue
        text = ''.join((n.text or '') if n.tag == W + 't' else ' ' for n in el.iter() if n.tag in (W + 't', W + 'tab', W + 'br'))
        if not text.strip():
            continue
        st = el.find(f'{W}pPr/{W}pStyle')
        style = st.get(W + 'val', '') if st is not None else ''
        runs = [r for r in el.iter(W + 'r') if ''.join(t.text or '' for t in r.iter(W + 't')).strip()]
        lead = ''.join(t.text or '' for t in runs[0].iter(W + 't')).strip() if runs else ''
        if style in heads or el.find(f'{W}pPr/{W}outlineLvl') is not None:
            kind = 'h'
        elif el.find(f'{W}pPr/{W}numPr') is not None or style in lists or BULLET.match(text):
            kind = 'li'
        else:
            kind = 'p'
            bold = bool(runs) and runs[0].find(f'{W}rPr/{W}b') is not None
            if bold and len(lead) <= 60 and lead.endswith((':', '.')) and len(lead) < len(text.strip()):
                text = '**' + lead + '** ' + text.strip()[len(lead):]  # жирная метка в начале абзаца
        out.append((kind, text))
    for n in sorted(names):  # тире ищем и там, где читатель его тоже увидит
        if re.fullmatch(r'word/(header|footer|footnotes|endnotes)\d*\.xml', n):
            out.append(('aux', ' '.join(t.text or '' for t in ET.fromstring(z.read(n)).iter(W + 't'))))
    if 'word/numbering.xml' in names:  # знаки маркеров, которые реально использованы в тексте
        num = ET.fromstring(z.read('word/numbering.xml'))
        lvl = {a.get(W + 'abstractNumId'): {l.get(W + 'ilvl'): t.get(W + 'val', '') for l in a.iter(W + 'lvl') for t in l.findall(W + 'lvlText')}
               for a in num.iter(W + 'abstractNum')}
        ref = {n.get(W + 'numId'): a.get(W + 'val') for n in num.iter(W + 'num') for a in n.findall(W + 'abstractNumId')}
        used = {(p.findtext(W + 'numId') or (p.find(W + 'numId').get(W + 'val') if p.find(W + 'numId') is not None else ''),
                 p.find(W + 'ilvl').get(W + 'val') if p.find(W + 'ilvl') is not None else '0') for p in root.iter(W + 'numPr')}
        marks = ' '.join(lvl.get(ref.get(n), {}).get(i, '') for n, i in sorted(used))
        out.append(('aux', 'маркеры списков: ' + marks))
    return out

def load(path):
    low = path.lower()
    if low.endswith('.docx'):
        return docx_blocks(path)
    if low.endswith(('.md', '.markdown', '.txt')):
        return md_blocks(open(path, encoding='utf-8').read())
    cmd = ['pdftotext', '-layout', path, '-'] if low.endswith('.pdf') else ['pandoc', path, '-t', 'gfm-smart', '--wrap=none']
    return md_blocks(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)

def size(s):
    return len(re.sub(r'\s', '', s))

def words(s):
    return len(re.findall(r'\w+', s))

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    opt = lambda name, default: int(args[args.index(name) + 1]) if name in args else default
    max_list, max_sent = opt('--max-list', 40), opt('--max-sentence', 25)
    blocks = load(args[0])
    run = []  # скрытый список: три и больше абзацев подряд с жирной меткой в начале
    for i, (kind, t) in enumerate(blocks + [('end', '')]):
        if kind == 'p' and LABEL.match(t):
            run.append(i)
            continue
        if len(run) >= 3:
            for j in run:
                blocks[j] = ('li', blocks[j][1])
        run = []
    body = [(k, t) for k, t in blocks if k in ('p', 'li')]
    total = sum(size(t) for _, t in body) or 1
    share = 100 * sum(size(t) for k, t in body if k == 'li') / total
    dashes, arrows = [], []
    for k, t in blocks:
        if k == 'code':
            continue
        t = re.sub(r'`[^`]*`', ' ', t)  # код внутри строки не трогаем
        dashes += [(DASH.get(m.group(), 'двойной дефис'), t[max(0, m.start() - 30):m.end() + 30].strip()) for m in DASH_RE.finditer(t)]
        arrows += [(m.group(), t[max(0, m.start() - 30):m.end() + 30].strip()) for m in ARROW_RE.finditer(t)]
    sents = [s for _, t in body for s in SENT.split(t) if s.strip()]
    longs = sorted((s for s in sents if words(s) > max_sent), key=words, reverse=True)
    text = ' '.join(t for _, t in body)
    heavy = sorted(((len(re.findall(p, text, re.I)), re.search(p, text, re.I).group(), tip)
                    for p, tip in HEAVY if re.search(p, text, re.I)), reverse=True)
    print(f'Объём: {total} знаков без пробелов, абзацев {sum(k == "p" for k, _ in body)}, пунктов списков {sum(k == "li" for k, _ in body)}')
    print(f'Доля списков: {share:.1f}% (цель до 30%, предел {max_list}%)' + ('  <-- ПРЕВЫШЕНИЕ' if share > max_list else ''))
    print(f'Длинные тире и их замены: {len(dashes)}' + ('  <-- УБРАТЬ' if dashes else ''))
    for name, ctx in dashes[:15]:
        print(f'   {name}: ...{ctx}...')
    print(f'Стрелки-символы: {len(arrows)}' + ('  <-- ЗАМЕНИТЬ на ->' if arrows else ''))
    for ch, ctx in arrows[:15]:
        print(f'   {ch} (U+{ord(ch):04X}): ...{ctx}...')
    print(f'Предложений: {len(sents)}, длиннее {max_sent} слов: {len(longs)}')
    for s in longs[:5]:
        print(f'   [{words(s)} слов] {s[:110]}...')
    print(f'Тяжёлые обороты: {sum(n for n, _, _ in heavy)}')
    for n, sample, tip in heavy[:12]:
        print(f'   {n} x "{sample}" -> {tip}')
    bad = bool(dashes) or bool(arrows) or share > max_list
    print('ИТОГ:', 'НУЖНЫ ПРАВКИ' if bad else 'жёсткие правила соблюдены, подсказки выше проверь глазами')
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # сбой скрипта не должен выглядеть как "найдены нарушения" (код 1)
        print(f'СБОЙ ПРОВЕРКИ: {type(e).__name__}: {e}', file=sys.stderr)
        sys.exit(2)

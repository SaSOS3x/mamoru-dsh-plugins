#!/usr/bin/env python
"""fix_proofing.py - разметка языка и noProof в готовом .docx, чтобы Word не подчёркивал верные слова.

Почему Word подчёркивает: язык фрагмента текста (w:lang w:val) выбирает словарь и действует на
кириллицу и латиницу этого фрагмента сразу. Если весь текст помечен ru-RU, слова Windows, VirtualBox
и имена файлов проверяются по русскому словарю. Русских терминов вроде "гипервизор" в словаре нет.

Что делает (тело, таблицы, списки, колонтитулы, сноски, примечания):
  - режет текст фрагментов (w:r) на куски по словам, текст при этом не меняется;
  - слово с латиницей -> язык en-US + w:noProof (не проверять);
  - русское слово с цифрами (ПМу-1-24) или аббревиатура (КГЭУ) -> ru-RU + noProof;
  - русское слово, которого нет в словаре, но есть в списке терминов -> ru-RU + noProof;
  - остальной русский текст -> ru-RU, Word проверяет его как обычно;
  - русские слова, которых нет ни в словаре, ни в списках, выводятся списком на разбор:
    опечатка -> исправить текст, верный термин -> добавить префикс в список терминов;
  - фрагмент, где проверка уже отключена (w:noProof: листинг кода, команда, цитата),
    остаётся как есть, и его слова на разбор не выводятся: цитату не правят.

Запуск:
  python fix_proofing.py fix   in.docx out.docx [--terms проект.txt ...] [--dict ПАПКА]
  python fix_proofing.py check file.docx        [--terms проект.txt ...] [--dict ПАПКА]
Списки терминов: scripts/terms_ru_it.txt читается всегда (отключить: --no-default-terms),
--terms добавляет файлы проекта. Строка файла: префикс слова, после # комментарий.
Словарь hunspell ru_RU: папка --dict, иначе кэш пользователя (%LOCALAPPDATA%/readable-docs/dict или
~/.cache/readable-docs/dict); если там пусто, скачивается с github.com/LibreOffice/dictionaries.
Нужны пакеты: pip install lxml spylls.
Коды возврата: 0 - всё размечено, незнакомых слов нет; 1 - есть незнакомые слова, латиница или
термины без noProof (check), либо русские слова не проверены (нет словаря или spylls); при fix файл
всё равно записан; 2 - сбой (нет файла, битый docx, нет lxml, текст изменился бы)."""
import argparse
import copy
import os
import re
import sys
import tempfile
import urllib.request
import zipfile
from collections import Counter

for _s in (sys.stdout, sys.stderr):  # на Windows консоль может быть cp1251
    try:
        _s.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from lxml import etree
except ImportError:
    print('Нет пакета lxml: pip install lxml')
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML_NS = 'http://www.w3.org/XML/1998/namespace'
DICT_URL = 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ru_RU/'


def q(tag):
    return f'{{{W}}}{tag}'


# Порядок дочерних элементов w:rPr по схеме CT_RPr; неизвестные (rPrChange) идут последними.
RPR_ORDER = ['rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'strike',
             'dstrike', 'outline', 'shadow', 'emboss', 'imprint', 'noProof', 'snapToGrid',
             'vanish', 'webHidden', 'color', 'spacing', 'w', 'kern', 'position', 'sz', 'szCs',
             'highlight', 'u', 'effect', 'bdr', 'shd', 'fitText', 'vertAlign', 'rtl', 'cs',
             'em', 'lang', 'eastAsianLayout', 'specVanish', 'oMath']
RPR_IDX = {n: i for i, n in enumerate(RPR_ORDER)}

PART_RE = re.compile(r'^word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$')
TOKEN = re.compile(r'\s+|\S+')
LAT = re.compile(r'[A-Za-z]')
CYR = re.compile(r'[А-Яа-яЁё]')
CYR_WORD = re.compile(r'[А-Яа-яЁё]+')
DIGIT = re.compile(r'\d')

PROPS = {'ru': ('ru-RU', False), 'term': ('ru-RU', True), 'lat': ('en-US', True)}


def default_dict_dir():
    base = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), '.cache')
    return os.path.join(base, 'readable-docs', 'dict')


def ensure_dict(folder):
    """Путь к ru_RU без расширения или None. Скачивает словарь, если его нет."""
    base = os.path.join(folder, 'ru_RU')
    if os.path.exists(base + '.aff') and os.path.exists(base + '.dic'):
        return base
    try:
        os.makedirs(folder, exist_ok=True)
        for ext in ('.aff', '.dic'):
            with urllib.request.urlopen(DICT_URL + 'ru_RU' + ext, timeout=120) as r:
                data = r.read()
            fd, tmp = tempfile.mkstemp(dir=folder)
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            os.replace(tmp, base + ext)
        print(f'Словарь ru_RU скачан в {folder}')
        return base
    except Exception as e:
        print(f'ВНИМАНИЕ: словарь ru_RU не скачан ({type(e).__name__}: {e}). Положи ru_RU.aff и ru_RU.dic'
              f' из {DICT_URL} в папку и укажи её ключом --dict')
        return None


class Checker:
    def __init__(self, dict_base, terms):
        self.dic = None
        self.note = ''
        if dict_base:
            try:
                from spylls.hunspell import Dictionary
                self.dic = Dictionary.from_files(dict_base)
            except ImportError:
                self.note = 'нет пакета spylls (pip install spylls)'
        else:
            self.note = 'нет словаря ru_RU'
        self.terms = sorted({t.strip().lower().replace('ё', 'е') for t in terms if t.strip()},
                            key=len, reverse=True)
        self.cache = {}
        self.unknown = Counter()
        self.term_hits = Counter()

    def status(self, word):
        """ok | term | unknown для одного русского слова."""
        if word in self.cache:
            return self.cache[word]
        low = word.lower().replace('ё', 'е')
        if len(word) >= 2 and word.isupper():
            res = 'term'  # аббревиатура: КГЭУ, ФГБОУ, ВМ
        elif self.dic is not None and (self.dic.lookup(word) or
                                       self.dic.lookup(word.replace('ё', 'е').replace('Ё', 'Е'))):
            res = 'ok'  # слово есть в словаре: пусть Word его проверяет
        elif any(low.startswith(t) for t in self.terms):
            res = 'term'
        elif self.dic is None:
            res = 'ok'  # проверить нечем
        else:
            res = 'unknown'
        self.cache[word] = res
        return res

    def classify(self, tok):
        if tok.isspace():
            return 'space'
        if LAT.search(tok):
            return 'lat'
        if not CYR.search(tok):
            return 'any'  # числа и знаки
        if DIGIT.search(tok):
            return 'term'  # ПМу-1-24
        cls = 'ru'
        for w in CYR_WORD.findall(tok):
            st = self.status(w)
            if st == 'unknown':
                self.unknown[w] += 1
                return 'ru'  # остаётся на проверке Word и попадает в отчёт
            if st == 'term':
                if not (len(w) >= 2 and w.isupper()):
                    self.term_hits[w] += 1
                cls = 'term'
        return cls

    def segments(self, text):
        segs, lead = [], ''
        for tok in TOKEN.findall(text):
            c = self.classify(tok)
            if c in ('space', 'any'):
                if segs:
                    segs[-1][1] += tok
                else:
                    lead += tok
                continue
            if segs and segs[-1][0] == c:
                segs[-1][1] += tok
            else:
                segs.append([c, lead + tok])
                lead = ''
        return segs or None  # None: только пробелы и знаки, фрагмент не трогаем


def has_noproof(run):
    rpr = run.find(q('rPr'))
    el = rpr.find(q('noProof')) if rpr is not None else None
    return el is not None and el.get(q('val'), 'true') not in ('0', 'false', 'off')


def child(rpr, name):
    el = rpr.find(q(name))
    if el is not None:
        return el
    el = etree.Element(q(name))
    idx = RPR_IDX[name]
    for pos, ch in enumerate(rpr):
        if RPR_IDX.get(etree.QName(ch).localname, 999) > idx:
            rpr.insert(pos, el)
            return el
    rpr.append(el)
    return el


def apply_props(run, cls):
    lang, noproof = PROPS[cls]
    rpr = run.find(q('rPr'))
    if rpr is None:
        rpr = etree.Element(q('rPr'))
        run.insert(0, rpr)
    child(rpr, 'lang').set(q('val'), lang)
    if noproof:
        child(rpr, 'noProof')


def process_part(xml_bytes, chk, stats):
    root = etree.fromstring(xml_bytes)
    for run in list(root.iter(q('r'))):
        content = [c for c in run if c.tag != q('rPr')]
        if len(content) != 1 or content[0].tag != q('t'):
            continue  # поля, рисунки, табуляции не трогаем
        if has_noproof(run):
            if (content[0].text or '').strip():
                stats['kept'] += 1  # код или цитата: проверка отключена заранее, не трогаем
            continue
        segs = chk.segments(content[0].text or '')
        if segs is None:
            continue
        stats['runs_in'] += 1
        parent, pos = run.getparent(), run.getparent().index(run)
        new_runs = []
        for cls, piece in segs:
            nr = copy.deepcopy(run) if len(segs) > 1 else run
            t = nr.find(q('t'))
            t.text = piece
            t.set(f'{{{XML_NS}}}space', 'preserve')
            apply_props(nr, cls)
            stats[cls] += 1
            new_runs.append(nr)
        if len(segs) > 1:
            parent.remove(run)
            for i, nr in enumerate(new_runs):
                parent.insert(pos + i, nr)
        stats['runs_out'] += len(new_runs)
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)


def text_of(xml_bytes):
    return ''.join(t.text or '' for t in etree.fromstring(xml_bytes).iter(q('t')))


def report(chk):
    if chk.term_hits:
        print('Термины из списков:', ', '.join(f'{w} ({c})' for w, c in chk.term_hits.most_common()))
    if chk.dic is None:
        print(f'ВНИМАНИЕ: русские слова не проверены по словарю: {chk.note}')
        return 1
    print(f'Незнакомые словарю слова на проверке Word: {len(chk.unknown)}')
    for w, c in chk.unknown.most_common():
        print(f'    {w} ({c})')
    if chk.unknown:
        print('  Разбери каждое: опечатка -> исправь текст, верный термин -> префикс в список терминов')
    return 1 if chk.unknown else 0


def cmd_fix(src, dst, chk):
    stats = Counter()
    tmp = dst + '.tmp'
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if PART_RE.match(item.filename):
                new = process_part(data, chk, stats)
                if text_of(new) != text_of(data):
                    zout.close()
                    os.remove(tmp)
                    print(f'СБОЙ: изменился бы текст в {item.filename}, файл не записан')
                    return 2
                data = new
            zout.writestr(item, data)
    os.replace(tmp, dst)
    print(f'Записан {dst}')
    print(f'Фрагментов с текстом: {stats["runs_in"]} -> {stats["runs_out"]}')
    print(f'Латиница без проверки (en-US, noProof): {stats["lat"]}')
    print(f'Русские термины, аббревиатуры и коды без проверки: {stats["term"]}')
    print(f'Русский текст на проверке Word (ru-RU): {stats["ru"]}')
    print(f'Фрагменты, где проверка уже отключена (код, цитаты), оставлены как есть: {stats["kept"]}')
    return report(chk)


def cmd_check(src, chk):
    bad_lat, bad_term = [], []
    with zipfile.ZipFile(src) as z:
        for name in z.namelist():
            if not PART_RE.match(name):
                continue
            for run in etree.fromstring(z.read(name)).iter(q('r')):
                text = ''.join(t.text or '' for t in run.iter(q('t')))
                if not text.strip():
                    continue
                if has_noproof(run):
                    continue
                if LAT.search(text):
                    bad_lat.append(text)
                for tok in TOKEN.findall(text):
                    if not CYR.search(tok) or LAT.search(tok) or chk.classify(tok) != 'term':
                        continue
                    sure = DIGIT.search(tok) or any(len(w) >= 2 and w.isupper() for w in CYR_WORD.findall(tok))
                    if chk.dic is not None or sure:  # без словаря префикс ловит и обычные слова
                        bad_term.append(tok)
    print(f'Латиница без noProof: {len(bad_lat)}')
    for t in bad_lat[:10]:
        print('   ', t[:70])
    print(f'Термины, коды и аббревиатуры без noProof: {len(bad_term)}'
          + (f' ({", ".join(bad_term[:10])})' if bad_term else ''))
    code = report(chk)
    return 1 if (bad_lat or bad_term or code) else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['fix', 'check'])
    ap.add_argument('src')
    ap.add_argument('dst', nargs='?')
    ap.add_argument('--terms', action='append', default=[], help='файл терминов проекта, можно несколько')
    ap.add_argument('--no-default-terms', action='store_true', help='не читать scripts/terms_ru_it.txt')
    ap.add_argument('--dict', help='папка с ru_RU.aff и ru_RU.dic')
    args = ap.parse_args()
    if args.cmd == 'fix' and not args.dst:
        ap.error('fix: нужен путь для результата')
    if not os.path.isfile(args.src):
        print(f'СБОЙ: нет файла {args.src}')
        sys.exit(2)
    files = ([] if args.no_default_terms else [os.path.join(HERE, 'terms_ru_it.txt')]) + args.terms
    terms = []
    for path in files:
        with open(path, encoding='utf-8') as f:
            terms += [ln.split('#')[0] for ln in f]
    chk = Checker(ensure_dict(args.dict or default_dict_dir()), terms)
    try:
        code = cmd_fix(args.src, args.dst, chk) if args.cmd == 'fix' else cmd_check(args.src, chk)
    except (zipfile.BadZipFile, etree.XMLSyntaxError, KeyError) as e:
        print(f'СБОЙ: битый docx ({type(e).__name__}: {e})')
        code = 2
    sys.exit(code)


if __name__ == '__main__':
    main()

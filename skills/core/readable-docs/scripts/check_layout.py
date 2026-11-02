#!/usr/bin/env python3
"""Проверка оформления учебного отчёта в docx (правила по умолчанию из раздела «Оформление учебного отчёта в docx» навыка readable-docs).

  python check_layout.py отчёт.docx [--indent 709] [--line 360]

Что проверяется в основной части (от первого заголовка первого уровня до конца):
  - пункты списков: отступ первой строки 1,25 см (709 twips), левый отступ 0, без выступа;
  - рисунок с подписью, листинг и таблица отделены пустой строкой сверху и снизу;
  - перед заголовком первого уровня пустая строка (кроме заголовка с новой страницы);
  - пустые строки одиночные, с интервалом как у текста (1,5) и без интервалов перед и после;
  - у абзацев основной части интервалы перед и после равны 0: отбивки делаются пустыми строками;
  - обозначения с индексами, равенства и расчёты набраны формулами Word (OMML), а не текстом:
    нет фрагментов с подстрочным или надстрочным начертанием вне формул, символов-индексов (₁, ²)
    и текста вида «R(6) = 37», «t(i, j)» (это проверяется и в ячейках таблиц).
Титульный лист (всё до первого заголовка) не проверяется. Отступы и пустые строки в ячейках таблиц не проверяются.
Код возврата: 0 - нарушений нет, 1 - есть нарушения, 2 - сбой (нет файла, битый docx, нет lxml).
"""
import argparse
import re
import sys
import zipfile

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
try:
    from lxml import etree
except ImportError:
    print('Нужен пакет lxml: pip install lxml')
    sys.exit(2)

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
INDEX_CHARS = re.compile('[\u2070-\u209f\u00b9\u00b2\u00b3]')       # ⁰¹²³…₀₁₂… вместо индекса формулы
TEXT_FORMULA = [
    # переменная (латинская или греческая буква, может быть с индексом и аргументом), затем знак равенства,
    # сравнения или действия и число либо другая переменная. Стрелки «->» и «<-» знаками не считаются,
    # плюс считается только с пробелами вокруг (иначе «C++20»), косая черта не считается (иначе «TCP/IP»)
    re.compile(r'(?<![\w.])[A-Za-zΑ-Ωα-ω][A-Za-z0-9]{0,2}(?:\([^()]{1,15}\))?\s*'
               r'(?:=|≈|≠|≤|≥|<(?!-)|(?<!-)>|−|×|·|\s\+\s)\s*[-−+]?\s*(?:\d|[A-Za-zΑ-Ωα-ω](?![A-Za-z]{2}))'),
    # обозначение вида R(i), t(i, j), f(x), R(6)
    re.compile(r'(?<![\w])[A-Za-z]\((?:[a-z]|\d{1,3})(?:,\s?(?:[a-z]|\d{1,3}))?\)'),
    # латинская буква с русским индексом в одну строку: Rп, tрн, tкр
    re.compile(r'(?<![\w])[A-Za-z][а-яё]{1,2}(?![\w])'),
]
MONO = {'courier new', 'courier', 'consolas', 'lucida console', 'liberation mono', 'dejavu sans mono',
        'menlo', 'monaco', 'source code pro', 'jetbrains mono', 'cascadia mono', 'cascadia code'}


def q(tag):
    return f'{{{W}}}{tag}'


def wv(el, attr='val'):
    return None if el is None else el.get(q(attr))


class Doc:
    def __init__(self, path):
        z = zipfile.ZipFile(path)
        self.body = etree.fromstring(z.read('word/document.xml')).find(q('body'))
        names = set(z.namelist())
        self.styles = etree.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in names else None
        self.numbering = etree.fromstring(z.read('word/numbering.xml')) if 'word/numbering.xml' in names else None
        self.style_by_id = {}
        if self.styles is not None:
            for s in self.styles.iter(q('style')):
                self.style_by_id[s.get(q('styleId'))] = s
        self.num_lvl = {}
        if self.numbering is not None:
            abstract = {a.get(q('abstractNumId')): a for a in self.numbering.iter(q('abstractNum'))}
            for n in self.numbering.iter(q('num')):
                a = abstract.get(wv(n.find(q('abstractNumId'))))
                if a is None:
                    continue
                for lvl in a.iter(q('lvl')):
                    self.num_lvl[(n.get(q('numId')), lvl.get(q('ilvl')))] = lvl

    def style_chain(self, sid):
        chain, seen = [], set()
        while sid and sid in self.style_by_id and sid not in seen:
            seen.add(sid)
            s = self.style_by_id[sid]
            chain.append(s)
            sid = wv(s.find(q('basedOn')))
        return list(reversed(chain))  # от базового к конкретному

    def normal_style(self):
        for s in self.style_by_id.values():  # стиль абзаца по умолчанию (Normal)
            if s.get(q('type')) == 'paragraph' and s.get(q('default')) in ('1', 'true'):
                return s.get(q('styleId'))
        return None

    def doc_defaults(self, kind):
        """pPr или rPr из docDefaults (kind: 'pPr' или 'rPr')."""
        if self.styles is None:
            return None
        return self.styles.find(f'{q("docDefaults")}/{q(kind + "Default")}/{q(kind)}')

    def normal_size(self):
        size = None
        layers = [self.doc_defaults('rPr')] + [s.find(q('rPr')) for s in self.style_chain(self.normal_style())]
        for r in layers:
            if r is not None and r.find(q('sz')) is not None:
                size = wv(r.find(q('sz')))
        return size or '20'

    def ppr_layers(self, p):
        """Слои свойств абзаца от слабого к сильному: умолчания, стиль, нумерация, прямое форматирование."""
        ppr = p.find(q('pPr'))
        sid = wv(ppr.find(q('pStyle'))) if ppr is not None else None
        sid = sid or self.normal_style()
        layers = [self.doc_defaults('pPr')] if self.doc_defaults('pPr') is not None else []
        chain = self.style_chain(sid) if sid else []
        layers += [s.find(q('pPr')) for s in chain if s.find(q('pPr')) is not None]
        num = None
        for layer in [ppr] + list(reversed(layers)):
            if layer is not None and layer.find(q('numPr')) is not None:
                num = layer.find(q('numPr'))
                break
        lvl = None
        if num is not None:
            num_id, ilvl = wv(num.find(q('numId'))), wv(num.find(q('ilvl'))) or '0'
            if num_id not in (None, '0'):
                lvl = self.num_lvl.get((num_id, ilvl))
                if lvl is not None and lvl.find(q('pPr')) is not None:
                    layers.append(lvl.find(q('pPr')))
        if ppr is not None:
            layers.append(ppr)
        return layers, lvl, chain

    def prop(self, layers, tag, attrs):
        res = {}
        for layer in layers:
            el = layer.find(q(tag))
            if el is None:
                continue
            for a in attrs:
                v = el.get(q(a))
                if v is not None:
                    res[a] = v
                    if tag == 'ind' and a in ('firstLine', 'hanging'):  # это одно свойство: верхний слой заменяет нижний
                        res.pop('hanging' if a == 'firstLine' else 'firstLine', None)
        return res


def text_of(el):
    return ''.join(t.text or '' for t in el.iter(q('t')))


def has_page_break(p):
    return any(wv(br, 'type') == 'page' for br in p.iter(q('br')))


def is_blank(p):
    """Пустая строка: нет текста, разрыва страницы, рисунка и формулы Word (текст формулы лежит в m:t, а не в w:t)."""
    return (not text_of(p).strip() and not has_page_break(p)
            and next(p.iter(q('drawing'), q('pict'), q('object'), f'{{{M}}}oMath'), None) is None)


def run_font(r):
    f = r.find(f'{q("rPr")}/{q("rFonts")}')
    return (wv(f, 'ascii') or wv(f, 'hAnsi') or '').lower() if f is not None else ''


def is_code(p, chain):
    """Строка листинга: стиль кода или моноширинный шрифт у всех фрагментов (пустая строка кода тоже)."""
    names = ' '.join((wv(s.find(q('name'))) or '').lower() for s in chain)
    if 'code' in names or 'код' in names or 'preformatted' in names:
        return True
    runs = [r for r in p.iter(q('r')) if text_of(r)]
    if runs:
        return all(run_font(r) in MONO for r in runs)
    mark = p.find(f'{q("pPr")}/{q("rPr")}')  # пустой абзац: шрифт знака абзаца
    return mark is not None and run_font(mark) in MONO


def in_math(el):
    return any(a.tag.startswith('{%s}' % M) for a in el.iterancestors())


def plain_text(p):
    """Текст абзаца без формул Word; неразрывный дефис считается дефисом, мягкий перенос пропускается."""
    out = []
    for n in p.iter(q('t'), q('noBreakHyphen'), q('tab')):
        if in_math(n):
            continue
        out.append(n.text or '' if n.tag == q('t') else '-' if n.tag == q('noBreakHyphen') else ' ')
    return ''.join(out)


def main():
    ap = argparse.ArgumentParser(description='Проверка оформления учебного отчёта в docx')
    ap.add_argument('docx')
    ap.add_argument('--indent', type=int, default=709, help='отступ первой строки, twips (709 = 1,25 см)')
    ap.add_argument('--line', type=int, default=360, help='межстрочный интервал текста, 240 = 1,0, 360 = 1,5')
    args = ap.parse_args()
    try:
        doc = Doc(args.docx)
    except (OSError, KeyError, zipfile.BadZipFile, etree.XMLSyntaxError) as e:
        print(f'Не удалось прочитать {args.docx}: {e}')
        sys.exit(2)

    # Элементы основной части с их свойствами
    normal_size = doc.normal_size()
    items = []
    for el in doc.body:
        if el.tag == q('tbl'):
            items.append({'kind': 'tbl', 'text': '[таблица]'})
        elif el.tag == q('p'):
            layers, lvl, chain = doc.ppr_layers(el)
            ind = doc.prop(layers, 'ind', ['left', 'start', 'firstLine', 'hanging'])
            sp = doc.prop(layers, 'spacing', ['before', 'after', 'line', 'lineRule', 'beforeLines', 'afterLines'])
            outline = doc.prop(layers, 'outlineLvl', ['val']).get('val')
            pbb = doc.prop(layers, 'pageBreakBefore', ['val'])
            page_before = any(x.find(q('pageBreakBefore')) is not None for x in layers) and \
                pbb.get('val', 'true') not in ('0', 'false', 'off')
            text = text_of(el).strip()
            items.append({
                'kind': 'p', 'el': el, 'text': text, 'blank': is_blank(el), 'list': lvl is not None,
                'ilvl': wv(lvl, 'ilvl') if lvl is not None else None, 'ind': ind, 'sp': sp,
                'h1': outline == '0', 'page_before': page_before, 'page_break': has_page_break(el),
                'sect': el.find(f'{q("pPr")}/{q("sectPr")}') is not None,
                'drawing': next(el.iter(q('drawing'), q('pict')), None) is not None,
                'code': is_code(el, chain),
            })
            if items[-1]['code']:
                items[-1]['blank'] = False
    start = next((i for i, it in enumerate(items) if it['kind'] == 'p' and it['h1']), 0)
    items = items[start:]
    for i in range(1, len(items) - 1):  # пустая строка внутри листинга - строка кода
        if items[i].get('blank') and items[i - 1].get('code') and items[i + 1].get('code'):
            items[i]['blank'], items[i]['code'] = False, True

    def new_page_at(i):
        """Элемент i начинается с новой страницы."""
        if i == 0:
            return True
        prev = items[i - 1]
        return bool(items[i].get('page_before') or prev.get('page_break') or prev.get('sect'))

    problems = {}

    def bad(key, it):
        k = items.index(it) if it in items else 0
        while k > 0 and not items[k].get('text'):  # у пустой строки пример - текст перед ней
            k -= 1
        problems.setdefault(key, []).append((items[k].get('text') or '')[:60])

    # Блоки: рисунок с подписью, таблица с подписью, листинг с подписью
    blocks = []
    i = 0
    while i < len(items):
        it = items[i]
        if it['kind'] == 'p' and it['drawing']:
            end = i + 1 if i + 1 < len(items) and re.match(r'Рисунок\s', items[i + 1].get('text', '')) else i
            blocks.append((i, end, 'рисунок'))
            i = end + 1
            continue
        if it['kind'] == 'tbl' or (it['kind'] == 'p' and re.match(r'(Таблица|Листинг)\s', it['text']) and i + 1 < len(items)
                                   and items[i + 1]['kind'] == 'tbl'):
            s = i
            while items[i]['kind'] != 'tbl':
                i += 1
            blocks.append((s, i, 'листинг' if re.match(r'Листинг\s', items[s].get('text', '')) else 'таблица'))
            i += 1
            continue
        if it['kind'] == 'p' and (it['code'] or (re.match(r'Листинг\s', it['text']) and i + 1 < len(items)
                                                 and items[i + 1].get('code'))):
            s = i
            i += 1
            while i < len(items) and items[i].get('code'):
                i += 1
            blocks.append((s, i - 1, 'листинг'))
            continue
        i += 1

    for s, e, name in blocks:
        label = items[e] if name == 'рисунок' else items[s]  # подпись блока для примера (у таблицы без подписи - пусто)
        if s > 0 and not new_page_at(s) and not items[s - 1].get('blank'):
            bad(f'нет пустой строки перед блоком ({name})', label)
        if e + 1 < len(items) and not new_page_at(e + 1) and not items[e + 1].get('blank'):
            bad(f'нет пустой строки после блока ({name})', label)

    for i, it in enumerate(items):
        if it['kind'] != 'p':
            continue
        if it['h1'] and not new_page_at(i) and not items[i - 1].get('blank'):
            bad('нет пустой строки перед заголовком первого уровня', it)
        if it['h1'] and it['page_before'] and i > 0 and items[i - 1].get('blank'):
            bad('пустая строка перед заголовком с новой страницы (останется внизу прошлой страницы)', it)
        if it['blank']:
            if i > 0 and items[i - 1].get('blank'):
                bad('две пустые строки подряд', items[i - 1] if items[i - 1]['text'] else it)
            if new_page_at(i):
                bad('пустая строка в начале страницы', it)
            mark = it['el'].find(f'{q("pPr")}/{q("rPr")}/{q("sz")}')
            if mark is not None and wv(mark) != normal_size:
                bad(f'пустая строка шрифтом {int(wv(mark)) / 2:g} пт, у текста {int(normal_size) / 2:g} пт',
                    items[i - 1] if i else it)
            line, rule = it['sp'].get('line'), it['sp'].get('lineRule', 'auto')
            if line is not None and (int(line) != args.line or rule != 'auto'):
                bad(f'пустая строка с интервалом {line}/{rule}, нужен {args.line}/auto', items[i - 1] if i else it)
        if it['list'] and it['ilvl'] == '0':
            ind = it['ind']
            left = int(ind.get('left', ind.get('start', 0)))
            first = int(ind.get('firstLine', 0))
            hanging = int(ind.get('hanging', 0))
            if left != 0 or hanging != 0 or abs(first - args.indent) > 10:
                bad(f'пункт списка: отступ слева {left}, первая строка {first}, выступ {hanging} '
                    f'(нужно 0, {args.indent}, 0)', it)
        sp = it['sp']
        if int(sp.get('before', 0)) or int(sp.get('after', 0)) or int(sp.get('beforeLines', 0)) or int(sp.get('afterLines', 0)):
            bad('интервал перед или после абзаца не 0', it)

    # Формулы: индексы и расчёты только формулами Word (в абзацах и в ячейках таблиц)
    main_els = [el for el in doc.body if el.tag in (q('p'), q('tbl'))][start:]
    n_math = sum(1 for el in main_els for _ in el.iter(f'{{{M}}}oMath'))
    for el in main_els:
        for p in el.iter(q('p')):
            if in_math(p) or doc.ppr_layers(p)[2] is not None and is_code(p, doc.ppr_layers(p)[2]):
                continue
            text = plain_text(p).strip()
            flagged = False
            for r in p.iter(q('r')):
                if in_math(r) or r.find(q('footnoteReference')) is not None or r.find(q('endnoteReference')) is not None:
                    continue
                rs = wv(r.find(f'{q("rPr")}/{q("rStyle")}')) or ''
                va = wv(r.find(f'{q("rPr")}/{q("vertAlign")}'))
                if va in ('subscript', 'superscript') and text_of(r).strip() and not re.search(r'(?i)footnote|endnote|сноск', rs):
                    problems.setdefault('индекс набран текстом (подстрочный или надстрочный знак), а не формулой Word', []).append(text[:60])
                    flagged = True
                    break
            if INDEX_CHARS.search(text):
                problems.setdefault('символы-индексы (₁, ²) вместо формулы Word', []).append(text[:60])
                flagged = True
            for rx in ([] if flagged else TEXT_FORMULA):   # одно место - одно нарушение
                m = rx.search(text)
                if m:
                    problems.setdefault('формула или обозначение набраны текстом, а не формулой Word', []).append(
                        text[max(0, m.start() - 20):m.end() + 25])
                    break

    total = sum(len(v) for v in problems.values())
    print(f'Проверено элементов основной части: {len(items)}, блоков: {len(blocks)} '
          f'(рисунков {sum(b[2] == "рисунок" for b in blocks)}, таблиц {sum(b[2] == "таблица" for b in blocks)}, '
          f'листингов {sum(b[2] == "листинг" for b in blocks)}), пунктов списков: {sum(1 for x in items if x.get("list"))}, '
          f'формул Word: {n_math}')
    if not total:
        print('Нарушений оформления нет')
        return 0
    print(f'Нарушений: {total}')
    for key, examples in problems.items():
        print(f'  {key}: {len(examples)}')
        for ex in examples[:3]:
            print(f'      «{ex}»')
    return 1


if __name__ == '__main__':
    sys.exit(main())

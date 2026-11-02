#!/usr/bin/env python
"""omml.py - формула Word (OMML, элемент m:oMath) из короткой линейной записи, для docx без docx-js.

  python omml.py "t_{рн}(i, j) = max_{i}[t_{р}(i) + t(i, j)]" [--size 28]   -> печатает XML
  python omml.py "D = (x_{i} - m)^{2} / (n - 1)"                             -> степень у скобки
  from omml import math_xml; xml = math_xml('R_{п} = 79 − 31 − 11 = 37', size=28)

Запись: X_{индекс} - буква с нижним индексом, X^{2} - степень (основание - буквы и цифры подряд, например
мс^{2}), X_{i}^{2} - индекс и степень сразу, (...)^{2} - степень у скобки, max_{i} и min_{j} - функция
с пределом снизу. Дробь с чертой, сумма со знаком Σ, корень и черта над буквой в запись не входят:
для них в docx-js есть MathFraction, MathSum, MathRadical, а в OMML элементы m:f, m:nary, m:rad, m:bar.
В строке формулы деление можно писать косой чертой «/»,
дефис-минус становится знаком минус (U+2212), пробел после запятой и точки с запятой сохраняется.
Переменные (латинские буквы) курсивом, русские индексы-сокращения (р - ранний, кр - критический)
и имена функций прямо, как принято в русской технической литературе. size - кегль в полупунктах
(28 = 14 пт), ставится в каждый фрагмент формулы: Word берёт размер формулы оттуда.
Результат вставляется в абзац (w:p) рядом с фрагментами w:r; у корня document.xml должно быть
объявлено пространство имён xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
(Word и docx-js объявляют его сами). Код возврата CLI: 0 - напечатано, 2 - нет записи."""
import re
import sys
from xml.sax.saxutils import escape

TOKEN = re.compile(r'(?P<fn>max|min)(?:_\{(?P<lim>[^}]*)\})?'      # max, min и предел снизу
                   r'|(?P<base>[A-Za-z])_\{(?P<sub>[^}]*)\}(?:\^\{(?P<sup2>[^}]*)\})?'  # индекс (и степень)
                   r'|\((?P<grp>[^()]*)\)\^\{(?P<gsup>[^}]*)\}'   # степень у скобки
                   r'|(?P<pbase>[A-Za-zА-Яа-яЁё0-9]+)\^\{(?P<sup>[^}]*)\}'  # степень
                   r'|(?P<lat>[A-Za-z])'                              # переменная
                   r'|(?P<cyr>[А-Яа-яЁё]+)'                           # русское слово или индекс (прямо)
                   r'|(?P<num>\d+(?:,\d+)?)'
                   r'|(?P<sp>\s+)'
                   r'|(?P<op>.)')


def _rpr(upright, size):
    m = '<m:rPr><m:sty m:val="p"/></m:rPr>' if upright else ''
    sz = f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else ''
    return m + f'<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/>{sz}</w:rPr>'


def _r(text, upright=False, size=None):
    return f'<m:r>{_rpr(upright, size)}<m:t xml:space="preserve">{escape(text)}</m:t></m:r>'


def _seq(expr, size):
    out = []
    for m in TOKEN.finditer(expr):
        g = m.lastgroup
        if m.group('fn'):
            name = _r(m.group('fn'), True, size)
            if m.group('lim') is not None:
                out.append(f'<m:limLow><m:e>{name}</m:e><m:lim>{_seq(m.group("lim"), size)}</m:lim></m:limLow>')
            else:
                out.append(name)
        elif m.group('base') and m.group('sup2') is not None:
            out.append(f'<m:sSubSup><m:e>{_r(m.group("base"), False, size)}</m:e>'
                       f'<m:sub>{_seq(m.group("sub"), size)}</m:sub><m:sup>{_seq(m.group("sup2"), size)}</m:sup></m:sSubSup>')
        elif m.group('base'):
            out.append(f'<m:sSub><m:e>{_r(m.group("base"), False, size)}</m:e>'
                       f'<m:sub>{_seq(m.group("sub"), size)}</m:sub></m:sSub>')
        elif g == 'gsup' or m.group('grp') is not None:
            inner = _r('(', True, size) + _seq(m.group('grp'), size) + _r(')', True, size)
            out.append(f'<m:sSup><m:e>{inner}</m:e><m:sup>{_seq(m.group("gsup"), size)}</m:sup></m:sSup>')
        elif m.group('pbase'):
            out.append(f'<m:sSup><m:e>{_seq(m.group("pbase"), size)}</m:e>'
                       f'<m:sup>{_seq(m.group("sup"), size)}</m:sup></m:sSup>')
        elif g == 'lat':
            out.append(_r(m.group(), False, size))
        elif g == 'sp':
            continue                                   # пробелы вокруг знаков Word расставляет сам
        elif g == 'op':
            ch = '−' if m.group() == '-' else m.group()
            keep_space = ch in ',;' and expr[m.end():m.end() + 1] == ' '
            out.append(_r(ch + (' ' if keep_space else ''), True, size))
        else:                                          # число или русский индекс
            out.append(_r(m.group(), True, size))
    return ''.join(out)


def math_xml(expr, size=None):
    """Встроенная формула Word: m:oMath для вставки в абзац рядом с w:r."""
    return f'<m:oMath>{_seq(expr, size)}</m:oMath>'


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0 if args else 2)
    size = int(args[args.index('--size') + 1]) if '--size' in args else None
    print(math_xml(args[0], size))

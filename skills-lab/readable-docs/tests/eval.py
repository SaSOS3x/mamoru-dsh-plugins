#!/usr/bin/env python3
"""Оценка результата теста: какие слова Word подчеркнёт (приближение настроек Word по умолчанию).
python eval.py original.docx result.docx --typos слово1,слово2 [--ru-dict ПУТЬ/ru_RU] [--en-dict ПУТЬ/en_US] [--validate validate.py]
Нужны lxml и spylls. Словари hunspell: ru_RU из кэша fix_proofing.py, en_US из github.com/LibreOffice/dictionaries (en/).
Слово не подчёркивается, если фрагмент noProof, или включён hideSpellingErrors (тогда скрыто всё),
или слово из прописных, или в токене есть цифры, / или \\ (адрес файла), или словарь языка фрагмента его знает."""
import argparse, re, subprocess, sys, zipfile
from lxml import etree
from spylls.hunspell import Dictionary

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q = lambda t: f'{{{W}}}{t}'
PART = re.compile(r'^word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$')
import os
RU = EN = None


def known(word, lang):
    d = RU if lang.startswith('ru') else EN if lang.startswith('en') else None
    if d is None:
        return False
    return d.lookup(word) or d.lookup(word.replace('ё', 'е').replace('Ё', 'Е'))


def runs(path):
    out, hide, paras = [], False, []
    with zipfile.ZipFile(path) as z:
        if 'word/settings.xml' in z.namelist():
            s = etree.fromstring(z.read('word/settings.xml'))
            el = s.find(q('hideSpellingErrors'))
            hide = el is not None and el.get(q('val'), 'true') not in ('0', 'false')
        styles = etree.fromstring(z.read('word/styles.xml'))
        dl = styles.find(f'.//{q("docDefaults")}//{q("lang")}')
        default_lang = dl.get(q('val')) if dl is not None else 'en-US'
        for n in z.namelist():
            if PART.match(n):
                root = etree.fromstring(z.read(n))
                paras += [''.join(t.text or '' for t in p_.iter(q('t'))) for p_ in root.iter(q('p'))]
                for r in root.iter(q('r')):
                    text = ''.join(t.text or '' for t in r.iter(q('t')))
                    if not text:
                        continue
                    rpr = r.find(q('rPr'))
                    lang, nop = default_lang, False
                    if rpr is not None:
                        l = rpr.find(q('lang'))
                        if l is not None and l.get(q('val')):
                            lang = l.get(q('val'))
                        np_ = rpr.find(q('noProof'))
                        nop = np_ is not None and np_.get(q('val'), 'true') not in ('0', 'false')
                    out.append((text, lang, nop))
    return out, hide, '\n'.join(paras)


def flagged_words(path):
    rs, hide, full = runs(path)
    flagged = []
    for text, lang, nop in rs:
        for tok in text.split():
            if re.search(r'\d|/|\\', tok):
                continue
            for w in re.findall(r'[A-Za-zА-Яа-яЁё]+', tok):
                if len(w) >= 2 and w.isupper():
                    continue
                if nop or known(w, lang):
                    continue
                flagged.append(w)
    return flagged, hide, full  # текст по абзацам, без лишних пробелов между фрагментами


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('orig'); ap.add_argument('res'); ap.add_argument('--typos', default='')
    base = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), '.cache')
    ap.add_argument('--ru-dict', default=os.path.join(base, 'readable-docs', 'dict', 'ru_RU'))
    ap.add_argument('--en-dict', default='/usr/share/hunspell/en_US')
    ap.add_argument('--validate', help='путь к validate.py навыка docx; без него проверка схемы пропускается')
    a = ap.parse_args()
    global RU, EN
    RU, EN = Dictionary.from_files(a.ru_dict), Dictionary.from_files(a.en_dict)
    typos = [t for t in a.typos.split(',') if t]
    f0, _, t0 = flagged_words(a.orig)
    f1, hide, t1 = flagged_words(a.res)
    vis = [] if hide else f1
    fp = sorted({w for w in vis if w.lower() not in {t.lower() for t in typos}})
    print(f'исходно подчёркнуто слов: {len(f0)}; hideSpellingErrors: {hide}')
    print(f'ложные подчёркивания (верные слова красные): {len(fp)} {fp}')
    words1 = re.findall(r'[A-Za-zА-Яа-яЁё]+', t1)
    for t in typos:
        if t not in words1:
            st = 'исправлена'
        elif t in vis:
            st = 'видна (подчёркнута)'
        else:
            st = 'СПРЯТАНА'
        print(f'опечатка {t}: {st}')
    w0 = re.findall(r'\S+', t0); w1 = re.findall(r'\S+', t1)
    import difflib
    sm = difflib.SequenceMatcher(a=w0, b=w1, autojunk=False)
    ch = [(w0[i1:i2], w1[j1:j2]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != 'equal']
    print(f'изменения текста: {len(ch)} {ch[:8]}')
    if a.validate:
        r = subprocess.run([sys.executable, a.validate, a.res], capture_output=True, text=True)
        print('validate:', (r.stdout.strip().splitlines() or ['?'])[-1])


if __name__ == '__main__':
    main()

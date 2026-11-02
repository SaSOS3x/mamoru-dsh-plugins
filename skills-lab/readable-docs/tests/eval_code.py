#!/usr/bin/env python3
"""Тест C: совпадает ли листинг кода (абзацы с шрифтом Courier New) с исходным, и все ли его фрагменты без проверки.
python eval_code.py original.docx result.docx"""
import sys, zipfile
from lxml import etree

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def code_paras(path):
    root = etree.fromstring(zipfile.ZipFile(path).read('word/document.xml'))
    out = []
    for p in root.iter(W + 'p'):
        runs = list(p.iter(W + 'r'))
        fonts = [r.find(f'{W}rPr/{W}rFonts') for r in runs]
        if runs and any(f is not None and f.get(W + 'ascii') == 'Courier New' for f in fonts):
            text = ''.join(t.text or '' for t in p.iter(W + 't'))
            noproof = all(r.find(f'{W}rPr/{W}noProof') is not None for r in runs if ''.join(t.text or '' for t in r.iter(W + 't')).strip())
            out.append((text, noproof))
    return out


a, b = code_paras(sys.argv[1]), code_paras(sys.argv[2])
same = [x[0] for x in a] == [x[0] for x in b]
print(f'строк кода: {len(a)} -> {len(b)}; текст кода совпадает: {same}; все фрагменты кода без проверки: {all(x[1] for x in b)}')
if not same:
    for (x, _), (y, _) in zip(a, b):
        if x != y:
            print('  было: ', x.strip()); print('  стало:', y.strip())

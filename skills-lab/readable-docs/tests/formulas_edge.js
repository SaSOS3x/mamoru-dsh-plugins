// Пограничные случаи для правил о формулах (check_layout.py) и стрелках (check_text.py): formulas_good.docx и formulas_bad.docx
const fs = require('fs');
const docx = require('docx');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, LineRuleType, Table, TableRow, TableCell, WidthType,
  MathRun, MathSubScript, NoBreakHyphen, FootnoteReferenceRun } = docx;
const OMath = docx.Math; // не деструктурировать как Math: в node -e это перекрывает глобальный Math
const AUTO = LineRuleType.AUTO;
const styles = { default: { document: { run: { font: 'Times New Roman', size: 28 }, paragraph: { spacing: { line: 360, lineRule: AUTO, before: 0, after: 0 } } } },
  paragraphStyles: [{ id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', run: { bold: true, size: 28 },
    paragraph: { spacing: { before: 0, after: 0 }, outlineLevel: 0 } }] };
const p = (...c) => new Paragraph({ indent: { firstLine: 709 }, children: c.map((x) => (typeof x === 'string' ? new TextRun(x) : x)) });
const t = (s) => new TextRun(s);
const sub = (b, s) => new MathSubScript({ children: [new MathRun(b)], subScript: [new MathRun(s)] });
const m = (...c) => new OMath({ children: c.map((x) => (typeof x === 'string' ? new MathRun(x) : x)) });
const arrow = () => new TextRun({ children: [new NoBreakHyphen(), '>'] });
const code = (s) => new Paragraph({ spacing: { line: 240, lineRule: AUTO }, children: [new TextRun({ text: s, font: 'Courier New', size: 20 })] });
const blank = () => new Paragraph({ children: [] });
const cell = (c) => new TableCell({ width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: c })] });
const table = (c1, c2) => new Table({ width: { size: 6000, type: WidthType.DXA }, columnWidths: [3000, 3000],
  rows: [new TableRow({ children: [cell(c1), cell(c2)] }), new TableRow({ children: [cell([t('1')]), cell([t('2')])] })] });
const write = (name, children) => Packer.toBuffer(new Document({ styles,
  footnotes: { 1: { children: [new Paragraph('Сноска.')] } }, sections: [{ children }] })).then((b) => fs.writeFileSync(name, b));
const head = [new Paragraph({ children: [t('Титульный лист')] }),
  new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [t('1 Раздел')] })];

write('formulas_good.docx', [...head,
  p('Ранний срок ', m(sub('t', 'р'), '(j)'), ' считается так: ', m(sub('t', 'р'), '(7)=max(31+11;61+18)=79'), ' дней.'),
  p('Путь A ', arrow(), ' B ', arrow(), ' C, обратная ссылка B <- A.'),          // стрелка «->» с неразрывным дефисом и «<-»
  p('Работа G (3, 7), версия Vulkan 1.3, ЛР4 (часть 1), 273 дня.'),             // коды и числа текстом - не формулы
  p('Текст со сноской', new FootnoteReferenceRun(1), '.'),                        // знак сноски надстрочный - не формула
  blank(), new Paragraph({ children: [t('Листинг 1 - Код')] }), code('x = 1'), code('y = f(x)'), blank(),   // код не трогаем
  p('Шапка таблицы с формулой.'),
  blank(), new Paragraph({ children: [t('Таблица 1 - Параметры')] }), table([t('ранний '), m(sub('t', 'р'), '(i)')], [m('R(i)'), t(', дней')]), blank(),
  p('Конец.'),
]);
write('formulas_bad.docx', [...head,
  p('Ранний срок t', new TextRun({ text: 'р', subScript: true }), '(j) считается слева направо.'), // индекс текстом
  p('Сумма x₁ + x² без формулы.'),                                                // символы-индексы
  p('Резерв R(6) = 78 − 41 = 37 дней.'),                                          // расчёт текстом
  p('Сверху записан резерв R(i).'),                                                // обозначение текстом
  p('Путь A → B ⇒ C.'),                                                           // стрелки-символы (check_text)
  blank(), new Paragraph({ children: [t('Таблица 1 - Параметры')] }),
  table([t('ранний t'), new TextRun({ text: 'р', subScript: true }), t('(i)')], [t('Rп')]), blank(),  // индекс текстом в шапке
  p('Конец.'),
]);

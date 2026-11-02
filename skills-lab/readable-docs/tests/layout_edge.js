// Пограничные случаи для check_layout.py: good.docx без нарушений, bad.docx с известным набором нарушений
const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, LineRuleType, Table, TableRow, TableCell, WidthType, PageBreak } = require('docx');
const AUTO = LineRuleType.AUTO;
const p = (t) => new Paragraph({ indent: { firstLine: 709 }, children: [new TextRun(t)] });
const blank = (o = {}) => new Paragraph({ children: [], ...o });
const h1 = (t, o = {}) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], ...o });
const code = (t) => new Paragraph({ spacing: { line: 240, lineRule: AUTO }, children: [new TextRun({ text: t, font: 'Courier New', size: 20 })] });
const codeTable = () => new Table({ width: { size: 9000, type: WidthType.DXA }, columnWidths: [9000],
  rows: [new TableRow({ children: [new TableCell({ width: { size: 9000, type: WidthType.DXA }, children: [code('echo 1'), code('echo 2')] })] })] });
const styles = { default: { document: { run: { font: 'Times New Roman', size: 28 }, paragraph: { spacing: { line: 360, lineRule: AUTO, before: 0, after: 0 } } } },
  paragraphStyles: [{ id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', run: { bold: true, size: 28 },
    paragraph: { spacing: { before: 0, after: 0 }, outlineLevel: 0 } }] };
const numbering = (ind) => ({ config: [{ reference: 'num', levels: [{ level: 0, format: 'decimal', text: '%1)', alignment: AlignmentType.LEFT,
  style: { paragraph: { indent: ind } } }] }] });
const li = (t) => new Paragraph({ numbering: { reference: 'num', level: 0 }, children: [new TextRun(t)] });
const write = (name, ind, children) => Packer.toBuffer(new Document({ styles, numbering: numbering(ind), sections: [{ children }] }))
  .then((b) => fs.writeFileSync(name, b));
write('good.docx', { left: 0, firstLine: 709 }, [
  new Paragraph({ children: [new TextRun('Титульный лист')] }), blank(), blank(),            // титул не проверяется
  h1('1 Раздел', { pageBreakBefore: true }), p('Текст.'), li('первый пункт;'), li('второй пункт.'),
  blank(), new Paragraph({ children: [new TextRun('Листинг 1 - Скрипт')] }), codeTable(), blank(),
  p('Текст после листинга.'), blank(), h1('2 Раздел'), p('Текст.'),
  blank(), new Paragraph({ children: [new TextRun('Листинг 2 - Команды')] }), code('ls -l'), code(''), code('pwd'), blank(), p('Конец.'),
]);
write('bad.docx', { left: 720, hanging: 360 }, [
  new Paragraph({ children: [new TextRun('Титульный лист')] }),
  blank(), h1('1 Раздел', { pageBreakBefore: true }),                                        // пустая перед заголовком с новой страницы
  p('Текст.'), li('пункт с выступом.'),                                                     // отступ списка
  blank(), blank(), new Paragraph({ children: [new TextRun('Листинг 1 - Скрипт')] }), codeTable(), p('Без пустой строки после.'), // две пустые, нет после
  new Paragraph({ children: [new PageBreak()] }), blank(), p('Пустая строка в начале страницы выше.'),
  new Paragraph({ children: [], run: { size: 20 } }), h1('2 Раздел'),                       // пустая строка шрифтом 10 пт
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun('Абзац с интервалом после.')] }),
]);

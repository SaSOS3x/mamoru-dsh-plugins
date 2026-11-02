// Генератор тестового docx из JSON: весь текст ru-RU, как в типичном конвейере
const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel, Header, Table, TableRow, TableCell,
  WidthType, BorderStyle, LevelFormat, LineRuleType } = require('docx');
const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const L = { value: 'ru-RU' }, AUTO = LineRuleType.AUTO;
const run = (t, o = {}) => new TextRun({ text: t, language: L, ...o });
const b = { style: BorderStyle.SINGLE, size: 4, color: '000000' };
const B = { top: b, bottom: b, left: b, right: b };
const C = [3400, 5955];
const cell = (t, i) => new TableCell({ borders: B, width: { size: C[i], type: WidthType.DXA }, children: [new Paragraph({ children: [run(t)] })] });
const ch = [new Paragraph({ heading: HeadingLevel.HEADING_1, children: [run(spec.title)] })];
for (const blk of spec.blocks) {
  if (blk.p) ch.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: { firstLine: 709 }, children: [run(blk.p)] }));
  if (blk.ul) blk.ul.forEach((t) => ch.push(new Paragraph({ numbering: { reference: 'ul', level: 0 }, children: [run(t)] })));
  if (blk.ol) blk.ol.forEach((t) => ch.push(new Paragraph({ numbering: { reference: 'ol', level: 0 }, children: [run(t)] })));
  if (blk.table) ch.push(new Table({ width: { size: 9355, type: WidthType.DXA }, columnWidths: C,
    rows: blk.table.map((r) => new TableRow({ children: [cell(r[0], 0), cell(r[1], 1)] })) }));
}
const doc = new Document({
  styles: { default: { document: { run: { font: 'Times New Roman', size: 28, language: L }, paragraph: { spacing: { line: 360, lineRule: AUTO } } } } },
  numbering: { config: [
    { reference: 'ul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '-', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1069, hanging: 360 } } } }] },
    { reference: 'ol', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1069, hanging: 360 } } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 850, bottom: 1134, left: 1701 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [run(spec.header, { size: 22 })] })] }) },
    children: ch }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(process.argv[3], buf); console.log('ok', process.argv[3]); });

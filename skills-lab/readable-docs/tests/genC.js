// Тест C: текст с опечаткой и листинг кода с noProof и опечаткой в комментарии
const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel, Header, ShadingType, LineRuleType } = require('docx');
const L = { value: 'ru-RU' }, AUTO = LineRuleType.AUTO;
const run = (t, o = {}) => new TextRun({ text: t, language: L, ...o });
const p = (t) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: { firstLine: 709 }, children: [run(t)] });
const code = (ln) => new Paragraph({ spacing: { line: 240, lineRule: AUTO }, shading: { type: ShadingType.CLEAR, fill: 'F2F2F2', color: 'auto' },
  children: [new TextRun({ text: ln || ' ', font: 'Courier New', size: 20, noProof: true, language: { value: 'en-US' } })] });
const listing = `static int counter = 0;              // общий счётчик
static object locker = new object();
static void Work()
{
    for (int i = 0; i < 100000; i++)
    {
        lock (locker)                    // инициализацыя защиты
            counter++;
    }
}`;
const ch = [
  new Paragraph({ heading: HeadingLevel.HEADING_1, children: [run('Лабораторная работа 4. Синхронизация потоков')] }),
  p('Программа на C# запускает два потока через класс Thread и защищает общий счётчик оператором lock. Без синхронизации потоки мешают друг другу, и итог получается меньше ожидаемого. Эта праграмма показывает гонку данных наглядно.'),
  new Paragraph({ spacing: { before: 120, after: 60 }, children: [run('Листинг 1 - Защита счётчика (Program.cs, строки 10-19)')] }),
  ...listing.split('\n').map(code),
  p('Многопоточность ускоряет работу, но общий кэш процессора и общие данные требуют защиты. Для этого служат мьютекс, семафор и оператор lock в C#, а в Windows ещё критическая секция.'),
];
const doc = new Document({
  styles: { default: { document: { run: { font: 'Times New Roman', size: 28, language: L }, paragraph: { spacing: { line: 360, lineRule: AUTO } } } } },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 850, bottom: 1134, left: 1701 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [run('Синхронизация: Thread, lock', { size: 22 })] })] }) },
    children: ch }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(process.argv[2], b); console.log('ok'); });

# mamoru-dsh-plugins

[English version](README.en.md)

Порт моих навыков из [mamoru-claude-plugins](https://github.com/SaSOS3x/mamoru-claude-plugins)
(маркетплейс плагинов Claude Code) в **DeepSeek Harness**. Семнадцать навыков, собранных на реальной
работе: порт сборки DeceasedCraft на NeoForge 1.21.1, мод Space Journey, большие .bat-скрипты для
Windows, длинные проекты с подагентами и поиск товаров на маркетплейсах.

Навыки лежат плоско в `skills/<имя>/SKILL.md`: DSH видит только такой корень и вложенные деревья не
сканирует. Три исходных плагина (`agent-workflow`, `minecraft-modding`, `writing-and-scripts`)
остались смысловыми группами в таблице ниже.

## Установка

1. Скопируйте репозиторий на компьютер.
2. В папке репозитория:

   ```powershell
   powershell -NoProfile -File install.ps1
   ```

   Скрипт создаёт ссылки (junction) на каждый навык в `%USERPROFILE%\.dsh\skills`, поэтому правки в
   репозитории видны без переустановки. Другие режимы:

   ```powershell
   powershell -NoProfile -File install.ps1 -List     # что установлено и куда смотрит
   powershell -NoProfile -File install.ps1 -Copy     # копиями, без ссылок
   powershell -NoProfile -File install.ps1 -Remove   # убрать ссылки
   ```

   Если политика выполнения блокирует неподписанный скрипт, добавьте в строку
   `-ExecutionPolicy Bypass`: файл текстовый, его можно прочитать перед запуском.
3. Откройте сессию DSH. Навыки появятся в каталоге сессии (список `available_skills`); открытая
   сессия обновляет каталог сама. Загрузить навык вручную можно командой `skill <имя>`, а вызвать
   как команду — `/имя`.

Другой корень задаётся ключом `-SkillsRoot`, например `<проект>\.dsh\skills`, чтобы навыки
действовали только в одном проекте. Тот же корень можно прописать в профиле DSH через
`customSkillDirs` (см. `docs/PORTING.md`).

Обновление: `git pull` в папке репозитория. При установке ссылками этого достаточно; при установке
копиями повторите `install.ps1 -Copy -Force`.

## Навыки

| Группа | Навык | Когда включается |
|---|---|---|
| agent-workflow | `project-journal` | любой многошаговый проект: задачи, проверка плана, дневник после каждого шага, сжатие дневника |
| | `agent-delegation` | перед вызовом `subagent`, `subagent_fork`, `send_message`, `workflow`: модель, промпт, проверка отчёта |
| | `session-error-audit` | раз в этап: аудит упавших вызовов по журналам DSH, поиск незаписанных уроков |
| | `skill-forge` | из проверенного опыта сделать новый навык или улучшить существующий |
| | `test-mutations` | доказать мутациями, что проверка ловит то, что обещает |
| | `windows-shell-dsh` | Windows в DSH: PowerShell 5.1, python.exe, JDK, кодировки, коды выхода |
| | `browse-like-user` | живые цены и доставка на сайтах через браузерный MCP, без капчи |
| minecraft-modding | `kubejs-neoforge-2101` | KubeJS 2101: скрипты, перенос с 1.20.1, ошибки Rhino |
| | `neoforge-mod-configs` | конфиги модов 1.21.1: какой файл, когда читается, почему не применился |
| | `modpack-port-neoforge` | порт сборки 1.20.1 Forge -> 1.21.1 NeoForge конвертерами |
| | `port-from-1182-pack` | перенос контента из сборки 1.18.2 |
| | `lostcities-biome-zones-mixin` | зоны биомов по правилу, миксин, полоса без городов |
| | `minecraft-worldgen-density-1-21` | рельеф: density-функции, TerraBlender, замер без запуска игры |
| | `tps-optimization-neoforge` | лаги: spark, поиск причины, отчёт до/после |
| | `neoforge-dev-experiments` | автотесты своего мода в Gradle dev-прогонах |
| writing-and-scripts | `readable-docs` | тексты для людей и оформление отчёта в docx |
| | `windows-shell-dev` | большие .bat/.cmd со встроенным PowerShell |

У каждого навыка рядом с `SKILL.md` лежит `CHANGELOG.md` (что менялось, когда и почему) и, если
нужно, `scripts/`, `references/`, `tests/`. Историю разработки навыков (журналы с исследованиями и
тестами) репозиторий хранит в `skills-lab/`.

## Чем порт отличается от исходного репозитория

Полная спецификация — в [docs/PORTING.md](docs/PORTING.md). Коротко:

- **Раскладка.** `plugins/<плагин>/skills/<навык>/` заменено на плоское `skills/<навык>/`: DSH
  сканирует только `<корень>/<навык>/SKILL.md`.
- **Метаданные.** У навыка только `name` (kebab-case, совпадает с папкой) и `description` до
  500 знаков: каталог DSH показывает описание урезанным, поэтому триггеры стоят в начале.
- **Инструменты.** `Bash` → `pwsh` (Windows PowerShell 5.1 на Windows), `Read/Write/Edit` →
  `read/write/edit`, `Agent` → `subagent`/`subagent_fork`, `SendMessage` → `send_message`,
  `Workflow` → `workflow`, `TodoWrite` → `todo_write`, `AskUserQuestion` → `ask_user_question`.
- **Модели.** Вместо Opus/Sonnet/Haiku — `deepseek-flash` и `deepseek-v4-pro` с усилиями
  `off`/`low`/`high`/`max`; таблица выбора в `agent-delegation` переписана по принципу, цифры
  старых замеров оставлены как история и подписаны.
- **Скрипты.** Переменной `CLAUDE_SKILL_DIR` в DSH нет: вызовы идут относительными путями от папки
  навыка, которую DSH печатает при загрузке.
- **Журналы сессий.** `session-error-audit` читает журналы DSH
  (`%USERPROFILE%\.dsh\sessions\...\session.v4.jsonl.zstd`, сжатие Zstandard) или ZIP из
  `/export`; скрипты аудита переписаны под события DSH.
- **Оболочка Windows.** Исходный `windows-shell-claude-code` (Git Bash) стал
  `windows-shell-dsh` (Windows PowerShell 5.1): ловушки Git Bash убраны в историю, добавлены
  проверенные ловушки PowerShell, python и JDK.
- **Браузер.** Встроенного браузера в DSH нет, он подключается как MCP-сервер; `browse-like-user`
  описывает действия, а не имена чужих инструментов.

## Разработка

- Правка навыка: `skills/<имя>/SKILL.md` и запись в `skills/<имя>/CHANGELOG.md` (что, когда,
  почему). Решение с записанной причиной не отменяется без нового довода.
- Перед коммитом: `python check_skills.py`. Проверяет фронтматтер (имя, длина описания), остатки
  путей Claude Code, ссылки на файлы навыка и правило CHANGELOG (у изменённого навыка должна быть
  новая запись).
- Коммит, затем обновление установки (`git pull` или `install.ps1 -Copy -Force`).

## Известные ограничения

- `windows-shell-dsh`, `session-error-audit` и `agent-delegation` проверены на одной машине
  (Windows 11, DSH 0.2.1-rc.5) и в тексте честно помечено, что в DSH не перемерялось.
- Навыки про Minecraft проверялись на реальных проектах в Claude Code; команды переведены на
  PowerShell 5.1, но сами прогоны в DSH не повторялись.
- Браузерному навыку нужен браузерный MCP-сервер; без него навык только скажет, чего не хватает.
- Аудит сессий для сжатых журналов требует `python -m pip install zstandard` или `zstd.exe` в PATH.

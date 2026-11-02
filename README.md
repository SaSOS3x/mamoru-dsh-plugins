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

Репозиторий — это npm-пакет `mamoru-dsh-plugins`, который объявляет bundle для DSH
(`"dsh": { "bundle": { "patch": "./cordis.patch.yml" } }`). Поэтому работают два способа, и
достаточно одного из них.

### Способ 1: менеджер плагинов DSH (основной)

1. Репозиторий должен быть доступен по HTTPS (GitHub). Публиковать пакет в npm-реестр не нужно:
   установка идёт прямо из Git.
2. Откройте DSH → **Plugins** (или **Settings → Plugins**) → установка плагина из Git-репозитория →
   укажите `https://github.com/SaSOS3x/mamoru-dsh-plugins`.
3. После установки плагин `mamoru-dsh-plugins` появится в списке и включится; его строки
   `mamoru-core` и `mamoru-minecraft` регистрируют навыки в каталоге сессии. Загрузить навык
   можно командой `skill <имя>` или вызвать как `/имя`.

Обновление: кнопка **Update** у плагина (переустанавливает последний коммит ветки) или установка
того же адреса заново. Изменения в `skills/` подхватываются после обновления пакета.

Проверить установку можно и из терминала (тот же профиль, что у приложения):

```powershell
dsh plugin --profile <профиль> add https://github.com/SaSOS3x/mamoru-dsh-plugins
```

### Способ 2: без менеджера плагинов

Ссылки (junction) на каждый навык в `%USERPROFILE%\.dsh\skills` — DSH сканирует этот корень и
следит за ним, поэтому правки в репозитории видны без переустановки:

```powershell
powershell -NoProfile -File install.ps1
```

Другие режимы:

```powershell
powershell -NoProfile -File install.ps1 -List     # что установлено и куда смотрит
powershell -NoProfile -File install.ps1 -Copy     # копиями, без ссылок
powershell -NoProfile -File install.ps1 -Remove   # убрать ссылки
```

Если политика выполнения блокирует неподписанный скрипт, добавьте в строку
`-ExecutionPolicy Bypass`: файл текстовый, его можно прочитать перед запуском. Другой корень
задаётся ключом `-SkillsRoot`, например `<проект>\.dsh\skills`, чтобы навыки действовали только в
одном проекте.

Не ставьте оба способа сразу: навыки будут видны дважды (файловый провайдер выигрывает у
пакетного, но путаницы это не отменяет).

### Как устроен пакет

| Файл | Роль |
|---|---|
| `package.json` | имя, версия, `exports`, `files` и объявление bundle: `dsh.bundle.patch` |
| `cordis.patch.yml` | слой bundle: вставляет два плагина, `mamoru-core` и `mamoru-minecraft` |
| `lib/core.js`, `lib/minecraft.js` | провайдеры компонентов: читают `skills/<компонент>/<навык>/SKILL.md` |
| `lib/provider.js` | общий код провайдера (фронтматтер, каталог, выдача текста по контракту `@deepseek-ai/dsh-skill`) |
| `lib/index.js` | агрегатный плагин `mamoru-skills` для старых профилей: регистрирует оба компонента |
| `skills/core/`, `skills/minecraft/` | сами навыки, разложенные по компонентам; попадают в пакет целиком |

Зависимостей у пакета нет: провайдер использует только встроенные модули Node, поэтому установка
из Git не тянет ничего из реестра.

## Компоненты

Пакет остаётся один, но внутри он монтирует **два отдельных плагина**:

| Компонент | id в профиле | Что внутри |
|---|---|---|
| `core` | `mamoru-core` | рабочий процесс и Windows: журнал, делегирование, skill-forge, аудит, мутации, оболочка, тексты, браузер |
| `minecraft` | `mamoru-minecraft` | NeoForge 1.21.1, порты сборок, worldgen, KubeJS, TPS |

Отключить компонент можно своим слоем в `cordis.patch.yml` профиля:

```yaml
- id: mamoru-minecraft
  disabled: true
```

Ставится всё равно весь пакет, но `minecraft`-навыки не попадут в каталог сессии. Оба компонента
независимы: провайдеры разные, имена навыков не пересекаются. Старые профили с id `mamoru-skills`
продолжают работать через агрегатный `lib/index.js`.

## Навыки

| Группа | Навык | Когда включается |
|---|---|---|
| core | `project-journal` | любой многошаговый проект: задачи, проверка плана, дневник после каждого шага, сжатие дневника |
| | `agent-delegation` | перед вызовом `subagent`, `subagent_fork`, `send_message`, `workflow`: модель, промпт, проверка отчёта |
| | `session-error-audit` | раз в этап: аудит упавших вызовов по журналам DSH, поиск незаписанных уроков |
| | `skill-forge` | из проверенного опыта сделать новый навык или улучшить существующий |
| | `test-mutations` | доказать мутациями, что проверка ловит то, что обещает |
| | `windows-shell-dsh` | Windows в DSH: PowerShell 5.1, python.exe, JDK, кодировки, коды выхода |
| | `browse-like-user` | живые цены и доставка на сайтах через браузерный MCP, без капчи |
| minecraft | `kubejs-neoforge-2101` | KubeJS 2101: скрипты, перенос с 1.20.1, ошибки Rhino |
| | `neoforge-mod-configs` | конфиги модов 1.21.1: какой файл, когда читается, почему не применился |
| | `modpack-port-neoforge` | порт сборки 1.20.1 Forge -> 1.21.1 NeoForge конвертерами |
| | `port-from-1182-pack` | перенос контента из сборки 1.18.2 |
| | `lostcities-biome-zones-mixin` | зоны биомов по правилу, миксин, полоса без городов |
| | `minecraft-worldgen-density-1-21` | рельеф: density-функции, TerraBlender, замер без запуска игры |
| | `tps-optimization-neoforge` | лаги: spark, поиск причины, отчёт до/после |
| | `neoforge-dev-experiments` | автотесты своего мода в Gradle dev-прогонах |
| core | `readable-docs` | тексты для людей и оформление отчёта в docx |
| | `windows-shell-dev` | большие .bat/.cmd со встроенным PowerShell |

У каждого навыка рядом с `SKILL.md` лежит `CHANGELOG.md` (что менялось, когда и почему) и, если
нужно, `scripts/`, `references/`, `tests/`. Историю разработки навыков (журналы с исследованиями и
тестами) репозиторий хранит в `skills-lab/`.

## Чем порт отличается от исходного репозитория

Полная спецификация — в [docs/PORTING.md](docs/PORTING.md). Коротко:

- **Раскладка.** `plugins/<плагин>/skills/<навык>/` заменено на `skills/<компонент>/<навык>/`:
  компоненты (`core`, `minecraft`) монтируются отдельными плагинами, а каждый навык остаётся
  папкой с `SKILL.md` и `CHANGELOG.md`.
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

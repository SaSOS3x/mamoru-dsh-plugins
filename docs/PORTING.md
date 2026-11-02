# Как устроен этот порт

Этот репозиторий — порт навыков из [mamoru-claude-plugins](https://github.com/SaSOS3x/mamoru-claude-plugins)
(маркетплейс плагинов Claude Code) в **DeepSeek Harness (DSH)**. Порт нужен, чтобы те же навыки
работали в DSH: находились в каталоге сессии, загружались инструментом `skill` и вызывали свои скрипты.

Исходный репозиторий остаётся главным источником знаний. Здесь меняется только то, чем DSH
отличается от Claude Code: раскладка файлов, метаданные навыка, имена инструментов, выбор модели,
формат журналов сессий и оболочка Windows.

## Раскладка

| Было (Claude Code) | Стало (DSH) |
|---|---|
| `plugins/<плагин>/skills/<навык>/SKILL.md` | `skills/<навык>/SKILL.md` |
| Плагин как единица установки (`.claude-plugin/plugin.json`, `marketplace.json`) | npm-пакет с bundle-слоем (`dsh.bundle.patch`): один пакет на весь набор, строка `mamoru-skills` монтирует провайдер |
| Установка через `claude plugin install` | Менеджер плагинов DSH ставит пакет из Git; альтернатива без него - ссылки в `%USERPROFILE%\.dsh\skills` (`install.ps1`) |

Три исходных плагина (`agent-workflow`, `minecraft-modding`, `writing-and-scripts`) остаются
смысловыми группами только в README и в истории: в DSH группа не влияет на установку.

## npm-пакет и bundle

Менеджер плагинов DSH принимает из Git только npm-пакет, который объявляет bundle-слой. Иначе он
отвечает «This package declares no bundle, so it cannot be managed as a plugin». Поэтому корень
репозитория — пакет:

```json
{
  "name": "mamoru-dsh-plugins",
  "version": "1.0.0",
  "type": "module",
  "main": "lib/index.js",
  "exports": { ".": "./lib/index.js", "./cordis.patch.yml": "./cordis.patch.yml" },
  "files": ["lib/index.js", "cordis.patch.yml", "skills", "..."],
  "engines": { "dsh": ">=0.2.0" },
  "dsh": { "manifestVersion": 1, "bundle": { "patch": "./cordis.patch.yml" } }
}
```

`cordis.patch.yml` — слой bundle, который применяется к дереву профиля:

```yaml
- insert:
    - id: mamoru-skills
      name: mamoru-dsh-plugins
```

Строка монтирует сам пакет как плагин Cordis: `name` совпадает с именем пакета, поэтому лаунчер
разрешает его из `node_modules` профиля (по правилу app-boot: имя bundle ищется сначала в
установке DSH, затем в папке профиля; пакеты из `node_modules` профиля — первыми).

`lib/index.js` — провайдер навыков. Он повторяет контракт `@deepseek-ai/dsh-skill` версии
0.2.1-rc.5:

- `list()` возвращает кандидатов: `name`, `description`, `invocation` (`modelInvocable` и
  `userInvocable`), `provider`, `source: 'bundled'`, `rank: 600` (BUNDLED_SKILL_RANK), `locator`
  (путь к `SKILL.md`) и `resourceBase: { kind: 'directory', path }`;
- `get(candidate, options)` отдаёт сводку без `rank`/`locator` плюс `content` — тело навыка без
  фронтматтера;
- `apply(ctx)` вызывает `ctx.skills.registerProvider(() => provider)`; экспорт — `name`, `inject:
  ['skills']`, `apply`.

Зависимостей у пакета нет: разбор фронтматтера — это несколько строк на встроенных модулях Node,
а не YAML-библиотека, и установка из Git ничего не тянет из реестра. Фронтматтер разбирается
построчно (`key: value` с необязательными кавычками), потому что навыки всё равно проверяет
`check_skills.py`; полноценный YAML здесь стоил бы загрузки на каждый старт.

Проверено 2026-11-02: `dsh --profile <тестовый> --dump-config` с этим пакетом в
`dsh.profile.bundles` печатает ровно строку `id: mamoru-skills, name: mamoru-dsh-plugins`;
настоящий реестр `@deepseek-ai/dsh-skill` из установки DSH после монтирования отдаёт все 17
навыков и грузит `project-journal` с `resourceBase` в папку навыка; `npm pack` кладёт в архив
96 файлов (пакет 382 кБ), установка архива в чистую папку и `import('mamoru-dsh-plugins')`
проходят.

## Метаданные навыка

DSH требует YAML-фронтматтер с полями `name` и `description`:

```yaml
---
name: project-journal
description: "..."
---
```

Правила, которые проверяет [check_skills.py](../check_skills.py):

- `name` в kebab-case и совпадает с именем папки;
- `description` одной строкой, не длиннее 500 знаков: каталог сессии показывает её в урезанном
  виде (`catalogDescriptionMaxLength` = 500), поэтому главное и фразы-триггеры стоят в начале;
- других полей нет. `whenToUse` DSH принимает, но в каталог не выводит, поэтому триггеры
  живут в `description`.

Каталог получает только имя и описание. Полный текст грузится по вызову `skill <имя>`.

## Скрипты и пути

Claude Code подставлял в текст навыка переменную `CLAUDE_SKILL_DIR`. В DSH такой переменной нет:
при загрузке навыка модель получает строку `Base directory for this skill: <путь>` и указание
решать относительные пути от неё. Поэтому в тексте навыка скрипты вызываются относительно:

```
python scripts/scan_fail.py --project "<папка>"
```

Абсолютных путей к папке навыка в тексте нет: они зависят от машины.

## Соответствие инструментов

| Claude Code | DSH | Замечание |
|---|---|---|
| `Bash` | `pwsh` | На Windows DSH даёт Windows PowerShell 5.1, не Git Bash и не PowerShell 7 |
| `Read` / `Write` / `Edit` | `read` / `write` / `edit` | `write`/`edit` требуют, чтобы файл был прочитан в этой сессии |
| `Grep` / `Glob` | `grep` / `glob` | |
| `Agent` (свой контекст) | `subagent` | Чистый контекст, есть `model` и `reasoning_effort` |
| `Agent` (наследует беседу) | `subagent_fork` | Видит завершённые ходы родителя, модель родителя |
| `SendMessage` | `send_message` | Продолжение того же ребёнка |
| `Workflow` | `workflow` | JS-скрипт: `agent()`, `pipeline()`, `parallel()`, `phase()`, `log()` |
| `TodoWrite` / `TaskCreate` | `todo_write` | |
| `AskUserQuestion` | `ask_user_question` | |
| `WebSearch` / `WebFetch` | `web_search` / `web_fetch` | |
| `CLAUDE.md` | `AGENTS.md` | DSH читает и `CLAUDE.md`, но импорты `@путь` не разбирает |
| `claude -p "<задача>"` | `dsh headless "<задача>"` | Чистый исполнитель для тестов навыка |
| `~/.claude/projects/<...>/*.jsonl` | `$DSH_HOME/sessions/--<путь>--/session-*/session.v4.jsonl.zstd` | Другая раскладка и другой формат записей |

## Модели и усилие

В DSH две модели (`deepseek-flash`, `deepseek-v4-pro`) и четыре уровня усилия
(`off`, `low`, `high`, `max`). Таблица выбора модели в навыке `agent-delegation` переписана
по принципу, а не по именам: готовый путь — дешёвая модель, нет пути и ошибку трудно заметить —
сильная. Цифры исходных замеров (Claude 5, октябрь 2026) сохранены как история и подписаны:
в DSH они не перемерялись.

## Оболочка Windows

Исходный навык `windows-shell-claude-code` описывал стык Git Bash с родными Windows-программами.
В DSH оболочка — Windows PowerShell 5.1, поэтому навык переименован в `windows-shell-dsh`:
ловушки Git Bash ушли в историю, ловушки PowerShell, `python.exe`, JDK и лимита командной строки
остались, проверенные факты подписаны датой и машиной.

## Журналы сессий

`session-error-audit` читает не `~/.claude/projects`, а журналы DSH:

```
$DSH_HOME/sessions/--<нормализованный cwd>--/session-<id>/session.v4.jsonl.zstd
```

Файл — конкатенация независимых Zstandard-кадров, по кадру на пакет событий (в архиве `/export`
внутри ZIP те же строки лежат несжатыми, `session.vN.jsonl`). События, которые нужны аудиту:
`tool/call` (`data.callId`, `data.name`, `data.arguments`) и `tool/result`
(`data.message.isError`, `data.message.content[].text`, `data.toolCallId`).
Кроме них учитываются `job/settled` (фоновые задания) и `user/message`.

## Что не переносится

- Маркетплейс плагинов Claude и команды `claude plugin ...` — в DSH установка это npm-пакет с
  bundle-слоем: менеджер плагинов ставит его из Git, а `install.ps1` остаётся запасным путём.
- `propose_skills` (карточка сохранения навыка в приложении Claude) — в DSH навык сохраняется
  коммитом в этот репозиторий и обновлением пакета (или переустановкой ссылок).
- Встроенный браузер Claude (`computer`, `tabs_select`, `get_page_text`, `javascript_tool`):
  в DSH браузера нет, он подключается как MCP-сервер, и имена инструментов зависят от сервера.
  Навык `browse-like-user` описывает поведение на сайте, а не имена инструментов.
- Правила Claude Code про подагентов и `CLAUDE.md` (снимок инструкций на старте сессии,
  Explore/Plan без инструкций): в DSH это устроено иначе и помечено как непроверенное там,
  где поведение DSH не проверялось.

## Как поддерживать порт

1. Правка навыка делается здесь, в `skills/<имя>/`, и сопровождается записью в
   `skills/<имя>/CHANGELOG.md` (что, когда и почему).
2. `python check_skills.py` — проверка фронтматтера, ссылок на файлы, правила CHANGELOG и обвязки
   пакета (`package.json`, `dsh.bundle.patch`, `lib/index.js`).
3. `git commit`; установка обновляется кнопкой **Update** в менеджере плагинов (или
   `powershell -NoProfile -File install.ps1`, если навыки подключены ссылками).
4. Если менялась обвязка пакета (`package.json`, `cordis.patch.yml`, `lib/index.js`), поднимите
   `version` в `package.json` и переустановите пакет: менеджер плагинов сравнивает версии, а
   загруженный модуль не перезагружается на лету.
5. Знания, которые меняются в исходном репозитории, переносятся сюда вручную; расхождения
   между копиями фиксируются в CHANGELOG навыка.

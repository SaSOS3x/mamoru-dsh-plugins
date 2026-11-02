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
| Плагин как единица установки (`.claude-plugin/plugin.json`, `marketplace.json`) | Плоский корень навыков: DSH видит только `<корень>/<навык>/SKILL.md`, вложенность не сканирует |
| Установка через `claude plugin install` | Папки навыков в `%USERPROFILE%\.dsh\skills` (или `customSkillDirs`) |

Три исходных плагина (`agent-workflow`, `minecraft-modding`, `writing-and-scripts`) остаются
смысловыми группами только в README и в истории: в DSH группа не влияет на установку.

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

- Маркетплейс плагинов и команды `claude plugin ...` — в DSH установка это файлы навыков.
- `propose_skills` (карточка сохранения навыка в приложении Claude) — в DSH навык сохраняется
  коммитом в этот репозиторий и установкой через `install.ps1`.
- Встроенный браузер Claude (`computer`, `tabs_select`, `get_page_text`, `javascript_tool`):
  в DSH браузера нет, он подключается как MCP-сервер, и имена инструментов зависят от сервера.
  Навык `browse-like-user` описывает поведение на сайте, а не имена инструментов.
- Правила Claude Code про подагентов и `CLAUDE.md` (снимок инструкций на старте сессии,
  Explore/Plan без инструкций): в DSH это устроено иначе и помечено как непроверенное там,
  где поведение DSH не проверялось.

## Как поддерживать порт

1. Правка навыка делается здесь, в `skills/<имя>/`, и сопровождается записью в
   `skills/<имя>/CHANGELOG.md` (что, когда и почему).
2. `python check_skills.py` — проверка фронтматтера, ссылок на файлы и правила CHANGELOG.
3. `git commit`, затем `powershell -NoProfile -File install.ps1` (или `-Copy`), чтобы обновить установку.
4. Знания, которые меняются в исходном репозитории, переносятся сюда вручную; расхождения
   между копиями фиксируются в CHANGELOG навыка.

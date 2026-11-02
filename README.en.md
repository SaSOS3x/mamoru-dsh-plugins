# mamoru-dsh-plugins

[Русская версия](README.md)

A port of my [mamoru-claude-plugins](https://github.com/SaSOS3x/mamoru-claude-plugins) skills
(a Claude Code plugin marketplace) to **DeepSeek Harness**. Seventeen skills grown out of real
work: porting the DeceasedCraft modpack to Minecraft 1.21.1 NeoForge, the Space Journey mod, large
Windows batch scripts, long projects with subagents, and looking up prices on marketplaces.

Skills live flat in `skills/<name>/SKILL.md` because DSH scans only `<root>/<name>/SKILL.md` and
ignores nested trees. The three original plugins (`agent-workflow`, `minecraft-modding`,
`writing-and-scripts`) survive only as groups in the table below.

## Install

This repository is the npm package `mamoru-dsh-plugins`, which declares a DSH bundle
(`"dsh": { "bundle": { "patch": "./cordis.patch.yml" } }`). Two ways work; one is enough.

### Option 1: the DSH plugin manager (primary)

1. The repository must be reachable over HTTPS (GitHub). Publishing to the npm registry is not
   needed: installation goes straight from Git.
2. Open DSH -> **Plugins** (or **Settings -> Plugins**) -> install a plugin from a Git repository ->
   enter `https://github.com/SaSOS3x/mamoru-dsh-plugins`.
3. After installation the plugin `mamoru-dsh-plugins` appears in the list and is enabled; its
   `mamoru-core` and `mamoru-minecraft` rows register the skills in the session catalog. Load one with `skill <name>` or
   invoke it as `/name`.

Update with the **Update** button (reinstalls the latest commit of the branch) or by installing the
same address again. Changes under `skills/` arrive with the package update.

The same can be done from a terminal (the same profile the app uses):

```powershell
dsh plugin --profile <profile> add https://github.com/SaSOS3x/mamoru-dsh-plugins
```

### Option 2: without the plugin manager

Junctions per skill under `%USERPROFILE%\.dsh\skills`: DSH scans that root and watches it, so edits
in the repository are live without reinstalling.

```powershell
powershell -NoProfile -File install.ps1
```

Other modes:

```powershell
powershell -NoProfile -File install.ps1 -List     # what is installed and where it points
powershell -NoProfile -File install.ps1 -Copy     # copies instead of links
powershell -NoProfile -File install.ps1 -Remove   # remove the links
```

If the execution policy blocks an unsigned script, add `-ExecutionPolicy Bypass` to the command
line; the file is plain text and can be read first. `-SkillsRoot` installs into another root, for
example `<project>\.dsh\skills`, so the skills apply to one project only.

Do not use both options at once: the skills would be listed twice (the filesystem provider wins over
the package provider, but the duplication is still confusing).

### Package layout

| File | Role |
|---|---|
| `package.json` | name, version, `exports`, `files`, and the bundle declaration `dsh.bundle.patch` |
| `cordis.patch.yml` | the bundle layer: inserts two plugins, `mamoru-core` and `mamoru-minecraft` |
| `lib/core.js`, `lib/minecraft.js` | component providers: read `skills/<component>/<skill>/SKILL.md` |
| `lib/provider.js` | shared provider code (frontmatter, catalog, body loading per the `@deepseek-ai/dsh-skill` contract) |
| `lib/index.js` | aggregate `mamoru-skills` plugin for old profiles: registers both components |
| `skills/core/`, `skills/minecraft/` | the skills themselves, split by component and packed whole |

The package has no dependencies: the provider uses Node built-ins only, so a Git install pulls
nothing from the registry.

## Components

One package, but inside it mounts **two separate plugins**:

| Component | Profile id | What is inside |
|---|---|---|
| `core` | `mamoru-core` | workflow and Windows: journal, delegation, skill-forge, audit, mutations, shell, docs, browsing |
| `minecraft` | `mamoru-minecraft` | NeoForge 1.21.1, pack ports, worldgen, KubeJS, TPS |

Turn a component off in your profile `cordis.patch.yml`:

```yaml
- id: mamoru-minecraft
  disabled: true
```

The whole package is still installed, but the `minecraft` skills never reach the session catalog.
The components are independent: separate providers, non-overlapping skill names. Old profiles with
the `mamoru-skills` id keep working through the aggregate `lib/index.js`.

## Skills

| Group | Skill | Turns on for |
|---|---|---|
| core | `project-journal` | any multi-step project: tasks, plan check, a journal entry after every step, journal compaction |
| | `agent-delegation` | before `subagent`, `subagent_fork`, `send_message`, `workflow`: model, prompt, review of a report |
| | `session-error-audit` | once per stage: failed tool calls from the DSH session logs, lessons that were never written down |
| | `skill-forge` | turning verified experience into a skill or improving an existing one |
| | `test-mutations` | proving with mutations that a check catches what it promises |
| | `windows-shell-dsh` | Windows in DSH: PowerShell 5.1, python.exe, JDK, encodings, exit codes |
| | `browse-like-user` | live prices and delivery on websites through a browser MCP, without captchas |
| minecraft | `kubejs-neoforge-2101` | KubeJS 2101 scripts, porting from 1.20.1, Rhino errors |
| | `neoforge-mod-configs` | 1.21.1 mod configs: which file, when it is read, why it did not apply |
| | `modpack-port-neoforge` | porting a pack 1.20.1 Forge -> 1.21.1 NeoForge with converters |
| | `port-from-1182-pack` | porting content that exists only in a 1.18.2 pack |
| | `lostcities-biome-zones-mixin` | biome zones by rule, mixin, a city-free strip at the border |
| | `minecraft-worldgen-density-1-21` | terrain: density functions, TerraBlender, measuring without starting the game |
| | `tps-optimization-neoforge` | lag: spark profiles, cause, before/after report |
| | `neoforge-dev-experiments` | autotests of your own mod in Gradle dev runs |
| core | `readable-docs` | texts for people and the layout of a student report in docx |
| | `windows-shell-dev` | large .bat/.cmd scripts with embedded PowerShell |

Every skill ships a `CHANGELOG.md` (what changed, when, why) and, where needed, `scripts/`,
`references/`, `tests/`. Skill development journals live in `skills-lab/`.

## What changed in the port

The full specification is in [docs/PORTING.md](docs/PORTING.md). In short:

- **Layout.** `plugins/<plugin>/skills/<skill>/` became flat `skills/<skill>/`.
- **Metadata.** Only `name` (kebab-case, equal to the folder) and `description` up to 500
  characters, because the DSH catalog truncates descriptions there; triggers come first.
- **Tools.** `Bash` -> `pwsh` (Windows PowerShell 5.1 on Windows), `Read/Write/Edit` ->
  `read/write/edit`, `Agent` -> `subagent`/`subagent_fork`, `SendMessage` -> `send_message`,
  `Workflow` -> `workflow`, `TodoWrite` -> `todo_write`, `AskUserQuestion` -> `ask_user_question`.
- **Models.** `deepseek-flash` and `deepseek-v4-pro` with `off`/`low`/`high`/`max` effort instead of
  Opus/Sonnet/Haiku; the choice table is rewritten by principle, older measurements stay labelled
  as history.
- **Scripts.** DSH has no `CLAUDE_SKILL_DIR`: calls use paths relative to the skill folder that DSH
  prints as `Base directory for this skill`.
- **Session logs.** `session-error-audit` reads DSH logs
  (`%USERPROFILE%\.dsh\sessions\...\session.v4.jsonl.zstd`, Zstandard frames) or a `/export` ZIP;
  the audit scripts were rewritten for DSH events.
- **Windows shell.** The original `windows-shell-claude-code` (Git Bash) became
  `windows-shell-dsh` (Windows PowerShell 5.1): Git Bash traps moved to history, PowerShell, python
  and JDK traps added.
- **Browser.** DSH has no built-in browser; it is an MCP server. `browse-like-user` describes
  actions rather than another product's tool names.

## Development

- Edit `skills/<name>/SKILL.md` and add an entry to `skills/<name>/CHANGELOG.md` (what, when, why).
  A decision with a recorded reason is not reverted without a new argument.
- Before a commit run `python check_skills.py`: frontmatter (name and description length), leftover
  Claude Code paths, references to skill files, and the CHANGELOG rule for changed skills.
- Commit, then refresh the installation (`git pull`, or `install.ps1 -Copy -Force`).

## Known limitations

- `windows-shell-dsh`, `session-error-audit` and `agent-delegation` were checked on one machine
  (Windows 11, DSH 0.2.1-rc.5); the text marks what was not re-measured in DSH.
- The Minecraft skills were verified on real projects under Claude Code; commands are translated to
  PowerShell 5.1, but the runs themselves were not repeated in DSH.
- The browser skill needs a browser MCP server; without one it only reports what is missing.
- Session audit over compressed logs needs `python -m pip install zstandard`, or `zstd.exe` on PATH.

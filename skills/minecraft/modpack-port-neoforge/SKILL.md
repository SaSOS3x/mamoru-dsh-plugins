---
name: "modpack-port-neoforge"
description: "Порт модпака 1.20.1 Forge → 1.21.1 NeoForge: данные в data-мод jar, постройки и палитры Lost Cities, лут, теги, главы FTB Quests 2101, замена мода без версии 1.21.1, перенос конфигов, чтение latest.log и краша. Триггеры: «переносим главу», «собери jar», «пересобери дата-джар», «мир крашится», «краш при старте», «что с лутом», «квесты не грузятся», «нет блока в палитре», «мод обновился», port a chapter, rebuild data jar, missing block, loot table error, Invalid formatting in quest."
---

# Porting a modpack 1.20.1 Forge → 1.21.1 NeoForge

Port data, not by hand: every change goes into a converter rule and the output is rebuilt, so the next mod update or
catalog refresh reproduces it. Verify against **catalogs of the real 1.21.1 instance** and mod sources; the in-game log
is the final judge. Related skills (same repository): `kubejs-neoforge-2101` (scripts), `neoforge-mod-configs` (configs),
`lostcities-biome-zones-mixin` (city / biome borders).

Facts below were verified on Minecraft 1.21.1, NeoForge 21.1.250, Lost Cities 1.21-8.4.x, FTB Quests 2101, in Oct 2026.
Passages starting "In the DeceasedCraft port:" are project examples (a 1.20.1 Forge pack ported with its own scripts); outside
that project take the method and the mod facts, and write your own scripts for the same steps.

## Folders (roles)
- **Target instance**: the 1.21.1 game folder (`mods`, `config`, `defaultconfigs`, `kubejs`, `saves`, `logs`, `libraries`).
- **Original instance**: the old 1.20.1 pack, read-only reference (its mods, `config`, `defaultconfigs`, `kubejs`, and exports
  of its data jar).
- **Work folder** inside the target instance (backups of every replaced file by date, reports, scripts, the project journal).
- In the DeceasedCraft port: target = the TLauncher "legacy" instance (`game/`), original = CurseForge instance "DeceasedCraft -
  Urban Zombie Apocalypse" (Beta 5.10.17; its data jar is `DCTweaks_*.jar`, plus `dc_export.zip`, `dc_assets_part1/2.zip`,
  `config_A_defaultConfigs.zip`), work folder = `game/_port/` (`config_port.py`, `reports/`, `backup_<date>/`, `tools/`,
  `HANDOFF.md`). Absolute paths of the user's PC are in the project's `CLAUDE.md`/`AGENTS.md`, not here.

## Safe replacement of files
- Before replacing configs / scripts / jars, `logs/latest.log` must end with "Stopping!" (the game is closed). Copy every
  file you overwrite to `backup_<date>/<same path>` first.
- Mod jars of your own keep their FILE NAME when replaced (two jars with one mod id would not load); the real version is in
  `META-INF/neoforge.mods.toml` and is independent of the file name (`deceasedcraft-terrain-0.1.0.jar` held mod version 0.2.0).
- Before adding a jar, list the `modId` of every `[[mods]]` entry in `META-INF/neoforge.mods.toml` of every jar in `mods/` and
  look for duplicates: one jar can declare a second mod with copied classes at the top level, not jar-in-jar (Cosmonautics
  26.08.307 declares `dimensional_sable` 1.0.5). The standalone jar of that mod next to it stops FML with
  `Found duplicate mods`, and the mod list in latest.log names only the first mod of each file (the resource pack line shows
  `mod/rocketnautics,dimensional_sable`).
- Inspect jars with `unzip` + `javap` to confirm class / field names.
- Sandboxed sessions (a cloud sandbox without network) could not reach Modrinth / CurseForge APIs or CDNs (HTTP 403, checked Oct 2026): when a
  session cannot download, propose exact file names / versions (found with web search, CurseForge file lists) and let the user
  download.

## Toolchain
In the DeceasedCraft port the scripts live in `game/_port/tools/` (checked 2026-10-12; they are NOT shipped with this skill - the
table says what each step needs, rebuild an equivalent for another pack).
| Script | Does | Run |
|---|---|---|
| `dc_collect.py` | catalog of blocks (blockstate props) + items + jar data/ of an instance → `dc_export.zip` | in an instance root, `--offline` |
| `dc_assets.py` | assets of DCTweaks + kubejs/assets of the original | in the original instance |
| `dc_download.py` | resolves/downloads 1.21.1 mods (Modrinth by SHA-1, CurseForge via cfwidget); `--core` = what buildings/quests need | anywhere |
| `roads.py` | Refueled road markings → Saro asphalt texture variants (pre-pass on DCTweaks data) | before convert |
| `convert.py` | DCTweaks data → `deceasedcraft-data-<ver>.jar` (lowcodefml data mod) | see Build pipeline |
| `apoc_replace.py` | Apocalypse Now → replacements, tiered gear pools | used by convert/quests |
| `quests.py` | FTB Quests 1.20.1 → 2101 + per-chapter report | see Build pipeline |
| `validate.py` | checks the jar: unknown block ids, bad vanilla props, leftovers | after convert |
| `build_stats.py` | original armor/weapon stats → xlsx with fill-in sheets | once |
| `config_port.py` | values of an old mod config → structure of the file the 1.21.1 mod generated; reports moved/new/dropped keys; `--set k=v` for keys whose meaning changed | per config file |

### Build pipeline (DeceasedCraft example; version numbers are examples)
Inputs in one work folder: `ex/` = `dc_export.zip` of the ORIGINAL instance (blocks_1.20.1.json, jar_data/DCTweaks_*/data,
jar_index.json); `exN/` = latest export of the 1.21.1 instance (blocks_1.21.1.json, items_1.21.1.json); `items_kjs.json` =
exN items + ids from `kubejs/startup_scripts/items/*.js`; `van120.json`, `van121.json`, `items121.json` = PrismarineJS
minecraft-data (pc/1.20, pc/1.21.1); Lost Cities 1.21 `palettes/default.json` (jar or GitHub `1.21_neo`); IE 1.21.1 multiblock
templates; `building_tiers.csv`; `assets_in/{dctweaks,kubejs}`; community lang; `lang_port/`; `extra_data/`; `overrides.json`.
```powershell
python roads.py ex/jar_data/DCTweaks_5.10.14/data dct_roads
python convert.py --src dct_roads --old-cat ex/blocks_1.20.1.json --new-cat exN/blocks_1.21.1.json `
  --new-items exN/items_kjs.json --van120 van120.json --van121 van121.json --vitems items121.json `
  --kubejs-tags <orig>/kubejs/server_scripts/tags --lc-default lc121/.../palettes/default.json `
  --ie-templates ie/data/immersiveengineering/structure/multiblocks --overrides overrides.json `
  --building-tiers building_tiers.csv --assets assets_in/dctweaks assets_in/kubejs `
  --lang-extra <community lang> lang_port --extra-data extra_data --out out --version 0.2.2
python validate.py            # edit the jar name inside first
python quests.py --quests <orig>/config/ftbquests/quests --out qout/config/ftbquests/quests --report qout/quests_report.md `
  --old-cat ... --new-cat ... --new-items exN/items_kjs.json --van120 ... --van121 ... --vitems ... `
  --building-tiers building_tiers.csv --overrides overrides.json
python config_port.py --old <orig>/defaultconfigs/x-server.toml --live game/config/x-server.toml `
  --out game/defaultconfigs/x-server.toml --report game/_port/reports/x-server.md [--set section.key=value]
```
(A backtick at the end of a line is the PowerShell 5.1 line continuation; the scripts are the port's own and are not shipped here,
so this block was not run in DSH - в DSH не проверено.)
Outputs: `out/deceasedcraft-data-<ver>.jar` + `block_remap.csv`, `prop_fixes.csv`, `loot_dropped_items.csv`,
`apocalypsenow_loot_replacements.csv`, `summary.json`; `qout/` quests + report.

## Working loop
1. Refresh catalogs (`dc_collect.py --offline` in `game/`) when mods change.
2. Change a rule in a script (never patch output by hand), rebuild, run `validate.py`.
3. Install into the target instance (backup first), start the game, create a fresh world named after the build
   (example: "Test 0.2.2").
4. Read `logs/latest.log`: your own log lines (DeceasedCraft: `[DeceasedCraft] ...`), crash causes, `Couldn't parse`,
   `Unknown registry key`, `ambiguous`; `logs/debug.log` for config loading (`Loaded TOML config file`).
   Uncaught exceptions of mod threads (a worker that stops logging, a feature that silently does not start) are not in
   latest.log or debug.log: read the launcher's console log before reading code (TLauncher: the newest
   `%TEMP%/tl-logger*.txt`; a Gradle dev run: the task's console output). Example, Space Journey 2026-10-14 (NeoForge
   21.1.250, TLauncher): DH's dead thread (`Exception in thread ... DH-PostClientInit`, a mixin error) was only there, found
   after 6 requests of static code reading.
5. Report what was verified and what is an assumption; keep the project journal current (DeceasedCraft: `game/_port/HANDOFF.md`).
6. Shell on Windows: DSH gives Windows PowerShell 5.1, not Git Bash (checked on one PC, 2026-10-12; in the DeceasedCraft port the
   same traps are in `CLAUDE.md` "Shell traps"): scripts longer than a few lines or with backslashes / apostrophes go into a
   file written with the `write` tool, not into `python -c` (5.1 has no heredoc); Windows python / java get `C:/Users/...`
   paths, never `/c/Users/...`; stdout of python is cp1251 there, so use `python -X utf8` (or `$env:PYTHONIOENCODING='utf-8'`);
   `&&`, `||` and the ternary `? :` are parse errors in 5.1, `2>&1` on a native command throws NativeCommandError, and the
   exit code of a chain with `;`, a pipe or a loop lies, so search the output for `Traceback|Error|No such file|not found`.
7. Pipeline details are in "Build pipeline" above; what convert.py does is in "Conversion rules" below.

## Configs
- `defaultconfigs/` is the single place for pack settings. In the DeceasedCraft port `kubejs/startup_scripts/defaultconfigs_sync.js`
  deletes the managed `config/<file>` at game start so NeoForge re-copies it (details: `neoforge-mod-configs`). To add a file
  there: start the game once so the 1.21.1 mod writes `config/<file>`, run `config_port.py` with the original's value file,
  review the report (dropped keys, changed meanings), put the result into `defaultconfigs/`, add the name to `DC_MANAGED_CONFIGS`
  (startup script) and, in `server_scripts/config/defaultconfigs_loader.js`, to `DC_SERVER_MANAGED` (*-server only) and `DC_CHECK`.

## Quests: chapter by chapter
For each chapter: analyse (items, task types, advancements, entities, images, KubeJS items, recipes) → list missing
mods/items → add mods to the download list (DeceasedCraft: `dc_download.py` CORE), port KubeJS items/recipes, add mappings in the
quest converter (DeceasedCraft: `quests.py` `EXTRA_MAP`, unique assignment for collection chapters) → reconvert → check in game.
Reinstall quests after the mods they reference exist (FTB Quests turns unknown items into missing items).

### FTB Quests text and file rules (check them in every quest generator)
- FTB Library parses every text (chapter / quest titles, subtitles, descriptions, and also the text a `{lang.key}`
  substitute resolves to, e.g. a KubeJS lang entry) with `&` and `§` as formatting prefixes (`&0-9a-fk-or`, `&#RRGGBB`).
  An ampersand followed by whitespace ("Grenades & C4") or a text ending in `&` or `{` is NOT shown: the quest book shows
  "Invalid formatting! You must escape whitespace after & with \&!" (or "Can't end string with &/{!") in red instead.
  Write a literal ampersand as `\&` (in SNBT/JSON source `\\&`) or just use "and"; `{` starts a substitute, a literal one
  is `\{`. Generators should reject `(?<!\\)[&§](\s|$)` in every text they write. A red "Invalid formatting!" line as a
  quest/chapter title is this rule, not a broken file.
- Object ids are signed longs written as 16 hex digits: an id >= 8000000000000000 is replaced by a RANDOM id when the file
  loads, so `chapter.<id>.title` etc. point nowhere ("Unnamed" chapter). Keep the top bit 0 when hashing ids.
- FTB rewrites chapter files when it loads/saves them (e.g. icons expanded to multi-line, `count: 1` dropped). Before
  overwriting a quest file on the PC, diff the PC copy against what was installed with whitespace/format normalised -
  only overwrite when the difference is formatting. Quest files on Windows are CRLF; keep CRLF.
- Quest hover texts of images live in the lang file (`image.<id>.title`), not inline.

## Conversion rules 1.20.1 → 1.21.1 (and why)
- Datapack folders singular: `loot_tables`→`loot_table`, `recipes`→`recipe`, `advancements`→`advancement`, `structures`→`structure`,
  `tags/blocks|items|entity_types`→`tags/block|item|entity_type`. Tags `forge:`→`c:`; optional mods' entries as
  `{"id": "...", "required": false}` (one missing id kills a tag).
- Data mod jar: `META-INF/neoforge.mods.toml` `modLoader="lowcodefml"`, `pack.mcmeta` pack_format 48, `ordering="AFTER"` on mods
  whose data/assets we override (examples: lostcities, zombie_extreme, tacz). NeoForge orders mod resource packs by load order,
  so AFTER is what makes our file win for the same path.
- Items/NBT → components: containers `{Slot,id,count,components:{"minecraft:custom_data":tag}}`; loot `set_nbt`→`set_custom_data`
  (TaCZ GunId/AmmoId), `StoredEnchantments`→`set_enchantments` (`sweeping`→`sweeping_edge`, modded dropped), `Potion`→`set_potion`,
  books → `set_components` `minecraft:written_book_content` with pages as JSON strings, title ≤ 32 chars; `looting_enchant` removed;
  unknown item ids → entry removed. Item models don't prove an item exists; an old block item counts only if its block exists.
- Lost Cities 7.x → 8.4 codecs identical. Unknown block without props → silently air; with props → palette dropped. Map every id
  (catalog diff, rename tables for MOA namespaces + abbreviations / RS2 / Farmer's Delight, keyword rules for missing mods,
  explicit table). Props: keep if in the new blockstate, drop if gone, drop unverifiable `false` flags and all unverifiable props
  of rewritten mods (RS2). Block-entity `tag` only if the block did not change (containers keep `Items`; LC overwrites `id`).
  Loot positions on non-openable blocks → openable container by the old block's kind. Street parts
  need style chars from `lostcities:default` (`b` = structure_void). Formed IE multiblocks → unformed blocks from the IE template
  at `posInMB` (master offset from the IE source), rotated NORTH→facing, mirrored FRONT_BACK. Road markings
  were overlays on street `H` → Saro asphalt texture (`straight`) in the block below, intersections plain.
- Quests (FTB Quests 2101) read legacy `Count`; convert `tag`→`components` (custom_data / potion_contents / stored_enchantments /
  patchouli:book); Item Filters → FTB Filter System `item_tag(<tag>)`
  (needs FTB XMod Compat); `kubejs:x` → `<pack namespace>:x` (DeceasedCraft: `deceasedcraft:x`); collection chapters: unique
  replacement per quest.
- A mod without a 1.21.1 version (DeceasedCraft: Apocalypse Now) can be recreated under its OLD ids by your own code, so
  the old buildings, loot and quests keep working. In the DeceasedCraft port: `apocalypsenow:*` melee = KubeJS items, armor =
  `deceasedcraft-armor` (Java), blocks / food / supplies = `deceasedcraft-an` (Java, read from the MCreator jar with javap, SRG
  names) + `an_world.py` (`_port/tools/an_blocks/`) restoring palettes and loot. Weapon / armor loot stays in the tiered gear pools `deceasedcraft:gear/t1..t4`
  (by building tier). The stages of that replacement are in the project journal.

## Lessons that cost hours
- A mod jar is not a registry: Quark 4.1 (1.21.1) still ships blockstates / models / lang of `quark:polished_tuff*` and
  `tuff_pillar` but no longer registers them (its datagen loot tables are the reliable list). Lost Cities throws on such a
  block with properties ("There was an error generating a chunk") and makes it air without. Ground truth = the running
  game: dump the registries on server load (DeceasedCraft: `kubejs/server_scripts/config/registry_dump.js` writes
  `local/deceasedcraft/registries.json` with blocks + state properties, items, fluids, entities) and check palettes / recipes /
  quests against it.
- Lost Cities builds cities in `raw_generation` with its ChunkDriver, which updates MOTION_BLOCKING / OCEAN_FLOOR /
  WORLD_SURFACE but NOT `*_WG` heightmaps: other mods' features placed at `OCEAN_FLOOR_WG` / `WORLD_SURFACE_WG` float at
  the pre-city terrain height (example: Horror Element corpses). Fix = override the placed feature (non-WG heightmap + a
  `block_predicate_filter`) in a jar that loads AFTER that mod; simple_block features check `canSurvive` themselves.
- Legendary Survival Overhaul 2.4.7 keeps a data json (`data/<ns>/legendarysurvivaloverhaul/...`) only if a MOD with id
  `<ns>` is loaded: items registered under another mod's namespace (`apocalypsenow:*` registered by `deceasedcraft_an`) get no
  thirst / temperature data. In the DeceasedCraft port this is fixed by a mixin in deceasedcraft-fixes 0.5.0; check
  "Loaded N thirst consumables" in the log.
- "Has a 1.21.1 version" ≠ same ids/props/config keys: diff block catalogs AND config files (MOA renamed namespaces, RS2 rewrote
  blocks, Hordes infection moved from config to data). Read the jar's code, not an old config comment.
- Lost Cities drops a whole palette for ONE block string with an invalid property → holes, not crashes.
- Loot tables: one bad item id or function invalidates the whole table → validate ids against the catalog.
- "defaultconfigs don't apply" was never a launcher bug: NeoForge 21.1 copies `defaultconfigs/<f>` only when `config/<f>` is
  missing, and SERVER configs live in `config/` (not per world). A KubeJS loader that calls `FileConfig.of` with a JS string
  fails silently: that is an ambiguous overload.
- Lost Cities rotates a block state only for blocks in the tag `lostcities:rotatable` (default: stairs + doors). Road markings
  (Saro `saros_road_blocks_mod:asphalt`) must be in it or the markings of N-S roads stay unrotated: `kubejs/data/lostcities/tags/
  block/rotatable.json` (`replace:false`, `required:false`; KubeJS data loads above mod packs, so it merges); the converter
  should write the asphalt id into the data jar's own tag. Generated roads need a NEW world.
- Lost Cities picks the STYLE of a city from the biome at its CENTRE but decides per chunk whether it is a city chunk (city radius
  up to 240): cities cross biome borders (hospital inside a wasteland). Biome zones need a city-free strip around the border -
  see the skill `lostcities-biome-zones-mixin` (zones every N blocks, Lipschitz strip, worldgen mixin, offline verification, C2ME).
- Zombie Extreme 1.21.1 registers `scorched_earth` with a catch-all climate box (24.75% of the surface samples; 1.20.1: 0.02%) -
  the world spawned in a scorched wasteland. Narrow the entry to the 1.20.1 box and return plains for it near the origin
  (DeceasedCraft: deceasedcraft-fixes `ScorchedEarth`); biomes only change in a NEW world.
- Legendary Survival Overhaul 2.4.7.2 applies limb malus effects as INFINITE effects and removes them through a `malus` map
  that is not saved: after a reload the broken-arm effect stays forever (DeceasedCraft: deceasedcraft-fixes `LsoMalus`). Test
  save / reload of infinite effects whenever a mod uses them.
- Before installing a worldgen-heavy mod (C2ME and the like), and before installing or UPDATING a mod that another mod
  patches (compat mixins, shader injections), read the jars first (`tar -xf` or `Expand-Archive` for nested jars, `javap -v` the mixin targets in the
  target jar of that exact version, search the patched shader variables in its shaders): the mixin targets and the required
  mods decide the risk, and a patch built for an older target version is a risk. A failed required injection logs
  `Critical injection failure ... Scanned 0 target(s)` (on a mod thread only in the launcher console, see Working loop
  step 4), the target class never loads and NPEs appear far from the cause; pin the last target version that passes.
  Alpha builds: never claim it works with the pack until the log shows it. Example, Space Journey 2026-10-14: Chunks Fade
  In 3.0.26, built against DH 3.2.0b, broke on DH 3.3.3 (`GL33.glClearDepth` became `LWJGL.glClearDepth`) and broke DH
  3.3.2's SSAO shader (`TexCoord` vs `texCoord`; config fix in `neoforge-mod-configs`).

## Passport
Created: 2026-10-12 (v34 second pass) from the DeceasedCraft port (journal: the project's `_port/HANDOFF.md`; method-only rework of
the v33 text). Verified: facts above on MC 1.21.1 / NeoForge 21.1.250 in Oct 2026 in that port; the passages marked "Space
Journey" in that project, 2026-10-14..23; the reworked text itself has not been run by a clean-context agent. Tested 2026-10-25 (skill-forge step 5, Opus executors, Sonnet
judges): only the S-13 passage (updating a mod that other mods patch), one task (JEI 19.44 -> 19.64 with Swift Copy and Polymorph),
previous text : this text 6:8 and 6:8, this text better; S-15 (launcher console) and S-38 (duplicate modId) were not tested. Limits:
scripts named in the Toolchain are not shipped; the converter rules are specific to
packs built on DCTweaks-style data, Lost Cities and FTB Quests.

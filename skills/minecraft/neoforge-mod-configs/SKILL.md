---
name: "neoforge-mod-configs"
description: "Конфиги модов NeoForge 1.21.1: COMMON/CLIENT/SERVER/STARTUP *.toml, когда и где читаются, сидинг defaultconfigs, типы ModConfigSpec, значения из KubeJS, file watcher; проверенные факты Lost Cities, Lost Souls, The Hordes, BOP, TerraBlender, Distant Horizons. Триггеры: «конфиги не встали», «профиль не применился», «настройка не работает», «конфиг сбрасывается», «изменил toml, ничего не поменялось», «defaultconfigs не работает», config did not apply."
---

# NeoForge 1.21.1 mod configs

A config change can fail at four points: the file is not the one the mod reads, it is read at another time, the value
has the wrong Java type, or another source overrides it. Find which one before changing anything: **read the real files
and `logs/debug.log` first**. Facts below are verified in FancyModLoader 4.0.44 / NeoForge 21.1 (branch `1.21.1`) and
the mods' 1.21.1 sources (Oct 2026); re-check the source when a version changes.

## Where configs live (NeoForge 21.1, FML 4.0.x)
| Type | File read | Loaded | Notes |
|---|---|---|---|
| STARTUP | `config/<file>` | when the mod registers it (constructor) | before KubeJS startup scripts may run |
| CLIENT | `config/<file>` | "Config loading" phase, after mod construction + RegisterEvent | client only |
| COMMON | `config/<file>` | same phase as CLIENT | global |
| SERVER | `config/<file>` - **global for all worlds** | `ServerLifecycleHooks.handleServerAboutToStart`, right before `loadLevel()` (after the world's datapacks/recipes loaded) | override per world: `saves/<world>/serverconfig/<same relative path>`; unloaded when the server stops |

- SERVER configs moved from per-world `serverconfig/` to `config/` in NeoForge 20.4 (PR #376, "Make server configs used
  across saves by default"). The world's `serverconfig/` folder now holds `readme.txt`, optional overrides and files some mods
  write there themselves (e.g. `taczarmor-balancing.json`); no `*-server.toml` in it is normal, not a bug.
  The `ModConfig.Type.SERVER` javadoc still describes the old behaviour.
- File name: `<modid>-<type>.toml` unless the mod passes its own (`lostcities/common.toml`). Find the type in the mod source:
  `container.registerConfig(ModConfig.Type.X, SPEC[, "name"])`.
- Some mods run their own config systems (Framework, SpectreLib, Zeta/Quark load early, FTB uses .snbt) - check per mod.

## defaultconfigs/ (what it really does)
`fml.toml` `defaultConfigPath = "defaultconfigs"`. FML `ConfigTracker.setupConfigFile` copies `defaultconfigs/<file>` to the
target path **only when the target file does not exist** (or failed to parse and was deleted). It applies to all four types.
It is **never** an override: once `config/<file>` exists, editing `defaultconfigs/<file>` changes nothing.
Log line when it happens: `Loading default config file from path ...` (ConfigTracker, CONFIG marker).
So "defaultconfigs don't work" almost always means: `config/<file>` was created before the defaultconfigs file was there.

## Making defaultconfigs/ the one place to edit (a reusable pattern)
Idea: let NeoForge do the parsing; a KubeJS script only removes the stale copy of `config/<file>` so that NeoForge seeds it
again from `defaultconfigs/<file>`. Two scripts, both part of one pack (not shipped with this skill; write them again from this
description):
- a startup script (game start, before COMMON loading): for each managed file, parse `defaultconfigs/<file>` with NightConfig
  and refuse (WARN, keep `config/`) if it is missing, invalid, empty or has a key the current `config/<file>` lacks (= old
  format); else `JsonIO.write('config/<file>', null)` (= delete). NeoForge copies the defaultconfigs file and loads it with
  correct types and timing.
- a server script: when no server is running (scripts load before a world starts) re-delete the managed SERVER files, so edits
  reach the next world without restarting; on `ServerEvents.loaded` compare every key of the file with `ConfigValue.get()` and log
  `defaultconfigs/<file>: N/M values live ...`. Keep three lists in sync: files managed at startup, SERVER-only files, and a
  check table (file → config class + field).
- Limits: in-game config screens' edits to managed files are lost on the next start; a COMMON file only works if the mod
  loads it in the normal phase (compare the `Loaded TOML config file` time in debug.log with `[KubeJS Startup/] Loaded script`);
  STARTUP files can't be managed this way.
- In the DeceasedCraft port: the files are `kubejs/startup_scripts/defaultconfigs_sync.js` and
  `kubejs/server_scripts/config/defaultconfigs_loader.js`; the three lists are `DC_MANAGED_CONFIGS` (startup),
  `DC_SERVER_MANAGED` (*-server only) and `DC_CHECK` (file → config class + field).
- Never copy a config file from another Minecraft version as-is (e.g. 1.20.1 → 1.21.1): port the values into the file the new
  mod version generated, then copy that into `defaultconfigs/`. NeoForge drops unknown keys with only a generic WARN
  (`Configuration file ... is not correct. Correcting`) and a `.bak` - no per-key detail. (In the DeceasedCraft port a script
  `config_port.py` does the porting; see the `modpack-port-neoforge` skill.)

## Setting values from scripts (only when a file can't do it)
- `ConfigValue.set(v)` does **not** write to disk (call `spec.save()`), fires no event, runs no validation, and updates the
  cached value only for values without `worldRestart()`/`gameRestart()`. Before the config is loaded it throws
  `Cannot set config value without assigned Config object present`. `get()` is cached; caches reset on load/reload.
- Types: `IntValue`→`Integer`, `LongValue`→`Long`, `DoubleValue`→`Double`, `BooleanValue`→`Boolean`, `ConfigValue<String>`→`String`,
  lists→`java.util.List<String>`. `set()` on an `IntValue` reached from JS gets a **Double** for a JS number (generic `T`
  unresolved); the cached Double makes `getAsInt()` throw `ClassCastException` (after `save()` + reload the file value reads
  back as int). Box with `Integer.valueOf`.
- Reach values through the public spec: `Java.loadClass(cls)[field].getValues()`, walk `valueMap()` to `section.key → ConfigValue`.

## File watcher and correction
- `fml.toml disableConfigWatcher = false` (default): a changed config file is reloaded at runtime (`ModConfigEvent.Reloading`),
  for every file-based type; the watched path is the resolved one (override if present). Mods that cached values may ignore it.
- A file that does not match the spec is backed up as `<name>-1.toml.bak` (up to 5), corrected (unknown keys removed,
  missing keys added with defaults) and rewritten. Many `.bak` files = someone keeps writing an outdated file.

## Debugging "config did not apply"
1. `logs/debug.log`: `Config file <f> for <mod> tracking` (registered), `Loaded TOML config file <full path>` (which file, when),
   `Found config file override in path`, `Loading default config file from path`. `latest.log` does not show the DEBUG lines.
2. Which file won: `saves/<world>/serverconfig/<f>` > `config/<f>`; `defaultconfigs/<f>` only seeds a missing file.
3. Timing: is the value needed before the file loads (e.g. worldgen during the first datapack load needs COMMON, not SERVER)?
4. Overrides at runtime: GUI choices (Lost Cities "Cities" button), data saved in the world, a mod's own cache.
5. Scripts: the script's own summary / check line in latest.log; `[KubeJS Server/]` errors such as "ambiguous" overloads (see `kubejs-neoforge-2101`).
6. Confirm on disk: `config/`, `defaultconfigs/`, `saves/<world>/serverconfig/`, `.bak` files.

## Mod specifics (1.21.1, checked in mod sources/jars)
**Lost Cities 1.21-8.4.x** (`mcjty.lostcities.setup.Config`: `COMMON_CONFIG`, `SERVER_CONFIG`, `resetProfileCache()`)
- Profiles: JSON in `config/lostcities/profiles/` (custom ones join `ProfileSetup.STANDARD_PROFILES`).
- `getProfileForDimension(level, dim)`: COMMON `profiles.dimensionsWithProfiles` (`"<dim>=<profile>"`, mod default
  `lostcities:lostcity=biosphere`, `lostworlds:abyss=biosphere_caves`) fills the cache first; for the overworld the cache entry
  is then OVERWRITTEN by the first non-empty of: profile picked in the Create World "Cities" screen (`profileFromClient`, saved
  into the world) > profile saved in the world (`LostData`) > SERVER `profiles.selectedProfile` (+`selectedCustomJson`). So a
  `minecraft:overworld=<profile>` line in `dimensionsWithProfiles` is only a fallback that works when all three are empty;
  `selectedProfile` in `config/lostcities-server.toml` is the working default. (Verified 2026-10-12 by decompiling
  `mcjty.lostcities.setup.Config` of lostcities-1.21-8.4.4.jar; this settles an older note that said the COMMON list overrides
  the GUI choice - it does not.) Cache reset on `ServerAboutToStartEvent`, `Config.reset()` on server stopping.
- `lostcity.forceSpawnBuildings`: if none is found within `spawnCheckAttempts` chunks, world creation **crashes**.
- `/lostcities map` (41x41 map to the log), `/lostcities locate <building>` (30 chunks).

**Lost Souls 1.21-5.0.1** (`mcjty.lostsouls.setup.Config.SERVER_CONFIG`, section `general`)
- Building hordes: datapack registry `data/<ns>/lostsouls/buildings/*.json` (buildings, multibuildings, mobs, weapons/armour,
  effects, healthbonus, damagebonus, mobamounts{min,max}, hauntedchance). Global lists are fallbacks; `getDefaultSettings()` caches.
- Global fallback lists (mobs, randomWeapons..., randomEffects e.g. `1.0=minecraft:glowing,0`) are **private** fields: reach them
  through the public spec `Config.SERVER_CONFIG`, path `general.<key>`.
- Messages are translation keys (`Component.translatable`).
- **`useChunkCheck` has the same meaning in 1.20.1 (Lost Souls 4.1.6) and 1.21.1 (5.0.1)** (bytecode of both jars: same
  `spawnMob`, same jar comment; only the old config-file comment of 4.1.6 reads differently; checked 2026-10-08). `true` = Lost Souls mobs alive in the
  building box (footprint, multibuildings + 1 chunk on +X/+Z) <= `totalMobs - killed` (+1, the test is `<=`): the horde stops
  growing when it is not cleared; `spawnMaxNearby` / radius are ignored. `false` = only `spawnMaxNearby` (+1) per
  (2r+1)^3 box around each spawn spot, NO building cap - an uncleared horde keeps growing. (The DeceasedCraft beta pack 5.10.17 on 1.20.1 uses `true`.)
- Ints: serverTickTimeout, spawnMaxNearby, spawnMaxNearbyRadius, minMobs, maxMobs, sphereMinMobs, sphereMaxMobs; Long: messageInterval.

**The Hordes 1.21.1-1.6.3f** (COMMON, `net.smileycorp.hordes.config.CommonConfigHandler.config`)
- 1.20.1 keys gone: `Infection.infectVillagers`, `villagerInfectChance`, `playerInfectChance`; `Misc."Zombie Players"` → top-level
  `"Zombie Players"`. Infection is data now: per hit `chance = infectivity × (1 − infection_resistance)`; infectivity base =
  `chance` per entity in `config/hordes/data/hordes/infection/infection_entities.json` (only listed mobs infect), players'
  resistance base = `Infection.playerInfectionResistance` (+ `wearables_protection.json`), conversions in
  `infection_conversions.json`. The 1.20.1 pack used an entity TAG (`tags/entity_types/infection_entities.json`) + one global
  `playerInfectChance` - when porting such a 1.20.1 setup, move both into the new files; the mod defaults are very different
  (zombie 0.75 × 0.75 = 56%/hit). (That 1.20.1 setup is the DeceasedCraft beta pack 5.10.17.)
- Wave data: datapack in `config/hordes/` (`data/hordes/horde_data/tables|scripts`); set `config/hordes/hordes-info.json`
  `"data_version": -1` or the mod regenerates it. `hordes:player_day` = `day > value`; day 0 → default table.
- `hordeEventByPlayerTime = true` counts player time (`/time` does not move it). `/hordes start <player> <ticks>`.

**Distant Horizons 3.3.2** (`config/DistantHorizons.toml`, client; checked in Space Journey 2026-10-14..23 against the jar and
the game's logs; re-check on other versions)
- DH does not watch the file (no file watcher in its config code): edit it with the game closed. In-game toggles reach the
  file incompletely ('rendering off' was written as `rendererMode = "DISABLED"` under `[client.advanced.debugging]`,
  'distant generation off' not at all): copy the file before an experiment and restore it after.
- LODs are built in every dimension. In a flat / void custom dimension DH's rough surface generator fills every empty column
  with water from `min_y` up to the flat generator's sea level (-63): dark blue slabs in an empty sky (Space Journey: a space
  dimension with `min_y` -2032). List such dimensions in `[client.advanced.graphics.experimental] ignoredDimensionCsv`
  (comma-separated ids): it stops rendering and chunk intake there, NOT LOD generation (about 10 MB of LODs were still written
  in one test flight), and forces vanilla fog there. Check: the log line `DH set to ignore dimensions: [...]`.
- With Chunks Fade In 3.0.26 keep `[client.advanced.graphics] enableSsao = false`: CFI injects `TexCoord` into DH's SSAO
  shader, DH 3.3.2 names it `texCoord` (log: `error C1503: undefined variable TexCoord`; DH disables its renderer and prints
  the shader into chat). With the setting off: no C1503 in the 6 later launches with DH shaders loaded.

**Biomes O' Plenty / TerraBlender**: `config/biomesoplenty/biome_toggles.json` (`<biome>_enabled`) - new worlds only.
TerraBlender injects BOP regions into any overworld `multi_noise` source, also a datapack-defined one.

## Passport
Created: 2026-10 from the DeceasedCraft 1.21.1 port (configs of ~40 mods, defaultconfigs seeding, Lost Cities / Lost Souls /
Hordes tuning).
Checked: Oct 2026 against FancyModLoader 4.0.44, NeoForge 21.1 and the sources / bytecode of the mod versions named in each
block; the Lost Cities profile order re-checked 2026-10-12 on lostcities-1.21-8.4.4; the Distant Horizons block 2026-10-23
(DH 3.3.2 jar and the logs of the Space Journey test game). Tested 2026-10-25 (skill-forge step 5, Opus executors, Sonnet
judges): one task (DH draws dark blue slabs in an empty dimension, game running), previous text : this text 6:9 and 7:10 by two blind
judges, this text better; the other blocks were not run by a test executor.
Limits: NeoForge 21.1 / Minecraft 1.21.1 only (older Forge keeps SERVER configs per world; Forge-era `serverconfig` rules
differ). The per-mod blocks are valid for the named versions only.
History: CHANGELOG.md next to this file (what changed, when and why).
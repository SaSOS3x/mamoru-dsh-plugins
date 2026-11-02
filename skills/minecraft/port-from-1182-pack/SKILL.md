---
name: "port-from-1182-pack"
description: "Порт контента из старого модпака 1.18.2 Forge в 1.21.1 NeoForge данными (пример: DeceasedCraft 5.5.5): постройки, палитры и стили Lost Cities 1.18, KubeJS 1802 (onEvent) → 2101, In Control / FX Control, armorsets, биомы BOP 1.18, измерения, noise settings, лут, порталы (Custom Portal API). Триггеры: «перенеси из старой сборки», «из 1.18.2», «пустоши», «измерение», «портал», «старый скрипт 1.18», «onEvent не работает», port from 1.18.2, old pack, wasteland, custom dimension json."
---

# Porting from a 1.18.2 Forge pack to a 1.21.1 NeoForge pack

Content that exists only in an older pack (1.18.2 Forge) can be ported as DATA with a script: verify against 1.21.1
sources / jars and record decisions in the project journal. Always compare with the newer pack (1.20.1) first: it may keep a
half-finished copy. Related skills (same repository): `modpack-port-neoforge` (1.20.1 → 1.21.1 data), `kubejs-neoforge-2101`
(renames of the 2101 API), `neoforge-mod-configs`.

Facts verified on Minecraft 1.21.1, NeoForge 21.1.250, Lost Cities 1.21-8.4.x, Oct 2026. Passages starting "In the DeceasedCraft
port:" are project examples; the rest is method or mod facts.

In the DeceasedCraft port: the 1.21.1 port is built from DeceasedCraft 1.20.1 (beta 5.10.17); the wastelands and the Abyss exist
only in DeceasedCraft 5.5.5 (Forge 1.18.2). The beta keeps a half-finished Abyss (dimension + quests, portal registration
commented out), which is why the beta is compared first.

## Where things are (typical layout of a 1.18.2 KubeJS pack)
- Lost Cities data usually sits in `kubejs/data/<ns>/lostcities/{buildings,multibuildings,parts,palettes,citystyles,styles,worldstyles,scattered}`,
  loot in a `chestloot` condition (`.../lostcities/conditions/chestloot.json`) and loot tables, custom dimensions in
  `kubejs/data/<ns>/{dimension,worldgen}/`, scripts in `kubejs/server_scripts` + `startup_scripts` (KubeJS 1802), portal assets in
  `kubejs/assets/customportalapi/`, configs in `config/incontrol/*.json`, `config/fxcontrol/effects.json`, `config/armorsets/*.json`,
  `config/lostcities/profiles/*.json`, mod jars in `mods/` (`META-INF/mods.toml`).
- In the DeceasedCraft 5.5.5 instance: namespace `c70cities`, `kubejs/data/deceasedcraft/loot_tables/chests/<category>/<kind>.json`
  for loot, `kubejs/data/deceasedcraft/{dimension,worldgen}/` for the Abyss, `abyss_portal.js` = Custom Portal API,
  `config/armorsets/*.json` = set bonuses of DeceasedCraftFixes. The instance folder is `...\DeceasedCraft 5.5.5` next to the
  port (TLauncher); the absolute path is in the project's `CLAUDE.md`/`AGENTS.md`.
- If no 1.18.2 Minecraft jar is at hand (none was on the DeceasedCraft PC), reason about 1.18.2 code from memory and PROVE the
  conversion against Mojang's own 1.21.1 files (below).
- Directory listings of `parts`/`palettes` exceed the tool output limit: the result is saved to a file - parse it with Python
  (`json.load`) instead of printing.
- Worked examples (method reference, not a status): wastelands = `game/_port/tools/wasteland/` (`wl_inventory.py` -> `mapper.py` ->
  `loot_gen.py` -> `wl_convert.py`), report `_port/reports/wasteland.md`; the Abyss = `game/_port/tools/abyss/`, report
  `_port/reports/abyss.md`. What is already ported and in which jar is in the project journal ("Status"), not here.

## KubeJS 1802 -> 2101
| 1802 | 2101 |
|---|---|
| `onEvent('player.tick', e)` | `PlayerEvents.tick(e)` (runs per player per tick; throttle with `player.tickCount % 20`) |
| `onEvent('player.logged_in')` | `PlayerEvents.loggedIn` |
| `onEvent('entity.death')` | `EntityEvents.death` |
| `onEvent('entity.hurt')` + `event.cancel()` | `EntityEvents.beforeHurt` (`event.source.actual`, `setDamage`) |
| `onEvent('item.right_click')` | `ItemEvents.rightClicked` |
| `onEvent('player.inventory.changed')` | `PlayerEvents.inventoryChanged` |
| `onEvent('recipes')` / `onEvent('item.tags')` | `ServerEvents.recipes` / `ServerEvents.tags('item')` |
| `onEvent('command.registry')` | `ServerEvents.commandRegistry` |
| `onEvent('item.registry')` / `onEvent('block.registry')` | `StartupEvents.registry('item'/'block')` |
| `onForgeEvent('net.minecraftforge....Event', cb)` | `NativeEvents.onEvent('net.neoforged.neoforge....Event', cb)` + try/catch |
| `Utils.server` | `event.server` / `ServerLifecycleHooks.getCurrentServer()` |
| `player.headArmorItem` | `player.getItemBySlot(EquipmentSlot.HEAD)` |
| `entity.block.biomeId` | `String(player.level.getBiome(player.blockPosition()).getRegisteredName())` |
| `player.damageEquipment(slot, n)` | `stack.hurtAndBreak(n, player, EquipmentSlot.X)` |
| `item.nbt.Damage = 0` | `stack.setDamageValue(0)` |
| `server.scheduleInTicks(...)` + `callback.reschedule()` loops | a throttled `PlayerEvents.tick` handler (simpler, no leaked schedules) |
Then apply the 2101 renames (`getStringUuid`, `entity.level`, `entity.damage`, `source.actual` ...) from `kubejs-neoforge-2101`.

## Lost Cities 1.18 (5.3.x) -> 1.21 (8.4.x)
- Same folders `data/<ns>/lostcities/<kind>/`; JSON keys are compatible (checked against LC 1.21-8.4.5 codecs): building
  `filler`, `allowDoors`, `allowFillers`, `min/maxfloors`, `min/maxcellars`, `preferslonely` (float), `parts` (`part`, `top`,
  `ground`, `cellar`, `floor` int, `range` string); part `xsize`, `zsize`, `slices` (`slices[y][z].charAt(x)`; multibuilding
  `buildings[x][z]`), `refpalette`, `palette`, `meta`; palette entries `char`, `block`, `blocks`, `variant`, `frompalette`,
  `damaged`, `loot`, `mob`, `tag`, `torch`; multibuilding `dimx`, `dimz`, `buildings`; condition `values[{factor, value, inpart,
  inbuilding, ...}]`; citystyle `style`, `inherit`, `streetblocks`, `parkblocks` (`elevation`, `grass`), `selectors{buildings,
  multibuildings, bridges, fronts, stairs, fountains, parks, raildungeons}`. `rubber` is unknown (ignored). Unknown keys are ignored; a
  wrong TYPE breaks the registry load. `' '` = air (`lostcities:common`).
- Ids: put converted things in your own namespace and in a sub-folder, keep the multibuilding names other configs refer to.
  In the DeceasedCraft port: namespace `deceasedcraft`, sub-folder `deceasedcraft:wasteland/<name>`, and the multibuilding names the
  In Control rules use (`deceasedcraft:multi_laboratory1`) stay. Style chars (`v z = H ! G _ ~`) come from the base style
  (`deceasedcraft:common` in the port) - every slice char must be in the part palette or there.
- Blocks: map every state with the catalog of the target pack's jars (blockstate jsons + minecraft-data 1.21.1 for vanilla
  states) and reuse the 1.20.1 converter rules (DeceasedCraft: `convert.py` rules - Apocalypse Now -> Zombie Extreme, cfm/pfm ->
  Refurbished / Another Furniture, keyword rules). Multipart blockstates list only values that add a model part: a boolean seen
  only as `true` also allows `false`, wall sides seen as `low/tall` also allow `none`. Drop block-entity `tag` NBT (1.18 format);
  command blocks -> air.
- Loot: `"loot": "chestloot"` + one big filtered condition -> one condition per part (DeceasedCraft:
  `deceasedcraft:wasteland/<part>`), and new loot tables built from existing target tables
  (`{"type":"minecraft:loot_table","value":"deceasedcraft:chests/..."}`) + gear pools (DeceasedCraft: `deceasedcraft:gear/t1..t4`).
  Do not convert 1.18 item lists (TaC guns, Apocalypse Now items do not exist in 1.21.1) - but check them for QUEST items first
  (example: the 5.5.5 laboratory `last_survivor` table carried the Abyss keycard; it was lost and came back as a NeoForge global
  loot modifier `neoforge:add_table` with condition `neoforge:loot_table_id`, which also works for Lootr chests).
- Package as a small lowcodefml data mod (own modId, `ordering="AFTER"` on the mods whose data it overrides) so it can
  override a worldstyle and stays committable. In the DeceasedCraft port: `ordering="AFTER"` on `deceasedcraft` and `lostcities`,
  overriding `data/deceasedcraft/lostcities/worldstyles/modern.json` (the worldstyle of profile `deceasedcraft_largecities`); the
  main data jar is too big to commit.

## Dimensions and worldgen 1.18.2 -> 1.21.1 (rules proven 2026-10-07; DeceasedCraft generator `_port/tools/abyss/abyss_data.py`)
- Dimension: inline `type` -> `dimension_type/<name>.json` + `monster_spawn_light_level` / `monster_spawn_block_light_limit` (required since
  1.19); generator `seed` is gone (the world seed is used).
- Noise settings: `noise.sampling / top_slide / bottom_slide / terrain_shaper` are gone; `spawn_target: []` is required.
  - `noise.sampling` -> `minecraft:old_blended_noise` with `xz_scale / cell width`, `y_scale / cell height`, factors unchanged,
    `smear_scale_multiplier = cell height` (cell width = 4 x size_horizontal, height = 4 x size_vertical): 1.18.2 sampled at cell coordinates.
  - `minecraft:slide` -> `target + y_clamped_gradient * (x - target)`, top first then bottom, from NoiseSlider `t = (cell index - offset) / size`
    (top: cells to the top). These two rules give EXACTLY Mojang's 1.21.1 nether final density and nether / end `base_3d_noise` from the
    1.18.2 settings - keep that as the self test (DeceasedCraft: `verify/slide_rule_check.py`).
  - 1.18.2 `overworld/offset|factor|jaggedness` read the dimension's `terrain_shaper`; in 1.21.1 the same names are real overworld splines.
    Resolve them: a constant-0 shaper makes `overworld/sloped_cheese` = base 3D noise and `initial_density_without_jaggedness` = 0.
  - Aquifers with a zero router see no surface (preliminary surface = Integer.MAX_VALUE, +8 overflows) -> global fluid only, as in 1.18.2.
- Biome: drop `category`, `precipitation` -> `has_precipitation`; features / carvers / effects keep the 1.21.1 shape (carvers map
  `{"air": ...}`, music a single object). Check the climate against Legendary Survival Overhaul (temperature 0.0 = cold).
- Features: int / float providers lost the nested `"value"` (`{"type":"minecraft:uniform","min_inclusive":..,"max_inclusive":..}`).
- Verify offline with the game's own loader: vanilla data from `libraries/net/minecraft/client/*/client-*-extra.jar` + the new pack through
  `RegistryDataLoader.load(rm, layered.getAccessForLoading(WORLDGEN), WORLDGEN_REGISTRIES)`, then `DIMENSION_REGISTRIES`; `RandomState.create`
  -> `router().finalDensity()` at cell corners (= what interpolation samples) to compare with the 1.18.2 maths and measure solid share
  (DeceasedCraft: `verify/AbyssDataTest.java`).

## Portals (Custom Portal API in 5.5.5)
- 5.5.5 `CustomPortalBuilder.beginPortal().frameBlock(..).destDimID(..).lightWithItem(..).flatPortal().tintColor(..)` (+ the frame made
  unbreakable with `BlockEvents.modification`). Custom Portal API Reforged exists for NeoForge 1.21.1, but the sandboxed session
  could not download it (Modrinth / Maven blocked, Oct 2026) - a small own mod is enough: block implementing
  `net.minecraft.world.level.block.Portal`
  (`entityInside` -> `setAsInsidePortal`, nether timing, `getPortalDestination` -> `DimensionTransition`), POI type for the search
  (NeoForge maps the states), ring detection as a pure function (unit test on the real Lost Cities part), portal cells set with flags 18,
  unbreakable frame via `@Mutable @Accessor` on `BlockStateBase.destroySpeed` / `BlockBehaviour.explosionResistance` (pistons and
  contraptions refuse destroy speed -1). Use item / block TAGS for key and frame (data-driven, `required: false`).

## Other 1.18 configs
- In Control 1.18 JSON ~ 1.21 keys; run everything through a converter script (DeceasedCraft: `incontrol_port.py`; an unknown mob
  id -> pig!). Renamed mobs: `zombie_extreme:devastated` -> `devestated`, `zombie_extreme:bomber` -> `explosive_infected`,
  `zombie_extreme:patient_zero` -> `zero_patient`; Mutationcraft and Alex's Mobs had no 1.21.1 version in the DeceasedCraft port as
  of v25 (2026-10-08) - recheck. Spawner `maxlight` = block light only. In the DeceasedCraft port new rules are APPENDED to the
  installed files (In Control tags mobs per rule index); when not every mod jar is staged, pass `--extra-entities` /
  `--extra-namespaces` from the installed files and prove output = installed + appended. Check every key against the In Control
  jar (`RuleKeys` strings): a rule with an unknown key loses its conditions.
- FX Control has no 1.21.1 build in the DeceasedCraft port: its effects are done in KubeJS (example:
  `kubejs/server_scripts/wasteland/wasteland_air.js`).
- `config/armorsets/*.json`: `head/chest/legs/boots.itemKey` + `mixAndMatch`, `fullSetBonuses`/`partialSetBonuses`
  (`partialBonusRequiredAmount`), `type` attribute (`attributeOperation` 0 add, 1 multiply base, 2 multiply total) or effect
  (`interactionType` self / attack / immunity), optional `mainHand` weapon condition. In the DeceasedCraft port the set engine is
  `_port/tools/armor_gen.py`: compare values and change them only with the user's approval (balance rule of that project).
- BOP 1.18 -> 1.21: `wooded_wasteland` removed (use `wasteland_steppe`), BOP cherry -> vanilla cherry, tag `c:is_wasteland` also
  holds crag / volcanic biomes (use the pack's own tag; DeceasedCraft: `deceasedcraft:wasteland`).

## Passport
Created: 2026-10-12 (v34 second pass) from the DeceasedCraft port (wastelands 2026-10-02, Abyss 2026-10-07; journal: the project's
`_port/HANDOFF.md`). Verified: rules above on MC 1.21.1 / NeoForge 21.1.250 / Lost Cities 8.4.x in Oct 2026; the reworked text has
not been run by a clean-context agent. Limits: not for ports from 1.19-1.20 packs (use `modpack-port-neoforge`); no 1.18.2 jar was
available, 1.18.2 behaviour comes from the old pack's files and memory.

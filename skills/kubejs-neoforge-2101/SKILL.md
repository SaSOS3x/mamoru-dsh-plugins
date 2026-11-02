---
name: "kubejs-neoforge-2101"
description: "Скрипты KubeJS 2101 (NeoForge 1.21.1): ошибки JS→Java, перегрузки Rhino, Java.loadClass, переименованные методы, тайминг событий, рецепты (вкл. Create 6), JsonIO, офлайн-тесты Rhino. KubeJS 2101 scripts: number/overload crashes, renames, events. Триггеры: «скрипт не работает», «ошибка в скрипте», «кубик», CubeJS, «крафт через скрипт», «рецепт», Cannot find function, ambiguous, «после /reload», «перенеси скрипт», [KubeJS Server] errors, kubejs/startup_scripts, server_scripts, client_scripts."
---

# KubeJS 2101 (NeoForge 1.21.1)

KubeJS on 1.21.1 looks like 1.20.1 on the surface, but things that worked silently on Forge now fail or, worse,
succeed and crash a mod later. Most mistakes come from five places: how JS values become Java values, which Java
overload Rhino picks, which classes are reachable, which vanilla members KubeJS renamed or hid, and *when* an event fires.
Verified against KubeJS branch `2101` (2101.7.2), KubeJS Rhino 2101.2.8 and real runs with the jars
kubejs-neoforge-2101.7.2-build.377 and rhino-2101.2.8-build.91 in Oct 2026 (a newer build may differ: re-check the
source). The wiki at kubejs.com lags behind the source - trust the source. Examples marked "in the DeceasedCraft port"
come from one modpack (a 1.21.1 NeoForge port); the rules around them are general.

## Workflow
1. **Truth from sources.** KubeJS: github.com/KubeJS-Mods/KubeJS branch `2101` (renames live in
   `src/main/java/dev/latvian/mods/kubejs/core/mixin/*Mixin.java`: `@RemapForJS`, `@HideFromJS`, `@RemapPrefixForJS("kjs$")`);
   Rhino: KubeJS-Mods/Rhino `main`; mods: their 1.21.1 source or `javap` on the jar from the instance's `mods/` folder. Never guess a name.
2. **Defensive scripts.** Java calls that may differ go in `try/catch`; each script logs one summary line
   `console.info('[Pack] <feature>: N done, M skipped, K errors, first error: ...')`.
3. **Check before the game.** `node --check file.js` (syntax only). For Java interop, run the script outside the game with
   the real Rhino jar (see "Offline test" below) - it reproduces overload/number problems exactly.
4. **Verify in game.** `logs/latest.log` has all `[KubeJS Startup/]`/`[KubeJS Server/]` lines (`logs/kubejs/*.log` can be
   incomplete). Search for the summary line and for `Error`/`ambiguous`.

## JS → Java values (crash source #1)
| JS | Java receives | Rule |
|---|---|---|
| number literal | `Double` | A param typed `Object` or an unresolved generic `T` gets no conversion. Rhino resolves `T` from the class that *declares* the method: `IntValue.set(5)` runs `ConfigValue<T>.set(T)` → stores a **Double** → mod crashes on read. `Integer.valueOf(5)`/`Long.valueOf(5)` stay boxed (verified). Arithmetic turns them back into Double. |
| string | `String`, or `Path`/`File` | KubeJS type wrappers turn a string into `Path` or `File`, resolved against the game folder; a path outside it is refused. |
| JS array | a `java.util.List` (Rhino `NativeArray`) | but its elements stay JS values (numbers = Double) - for typed Java lists (config values) build `new ArrayList()` and add `String(x)` / boxed numbers |
| boolean / `{}` | `Boolean` / map-like (JSON for `event.custom`) | fine |
| Java value read from a Java Map | wrapped object, `typeof` is `'object'` even for strings/numbers/booleans | compare via `String(x)` / `Number(String(x))` |

Boxing probe: `let l = new ArrayList(); l.add(Integer.valueOf(5)); String(l) == '[5]'` (`[5.0]` = became Double).
Don't probe with `String.valueOf(x)` (Rhino picks `valueOf(char)` and returns a control character).

## Overloads Rhino can't pick (crash source #2)
- Because a JS string converts to both `Path` and `File`, any method overloaded on `(Path, …)`/`(File, …)` fails with
  `The choice of Java method X matching JavaScript argument types (string, …) is ambiguous` - e.g. NightConfig
  `FileConfig.of`, `FileConfig.builder`, `ConfigParser.parse`, `ConfigWriter.write`.
- Fix: select the overload by signature, `obj['name(fully.qualified.Type1,fully.qualified.Type2)'](args)`:
  ```js
  const $Toml = Java.loadClass('com.electronwill.nightconfig.toml.TomlFormat')
  const $NotFound = Java.loadClass('com.electronwill.nightconfig.core.file.FileNotFoundAction')
  const PARSE = 'parse(java.nio.file.Path,com.electronwill.nightconfig.core.file.FileNotFoundAction)'
  let cfg = $Toml.instance().createParser()[PARSE]('defaultconfigs/x-server.toml', $NotFound.THROW_ERROR) // throws if missing
  ```
  (`FileConfig.of(...)` + `load()` would CREATE an empty file when it is missing - default `CREATE_EMPTY`.)
- Same trick for registries: `BuiltInRegistries.MOB_EFFECT['getHolder(net.minecraft.resources.ResourceLocation)'](rl)`
  (`getHolder` is overloaded on int / ResourceKey / ResourceLocation), `DamageSource['is(net.minecraft.tags.TagKey)'](tag)`.
- NightConfig `cfg.get('a.b')` from JS returns **null** (Rhino prefers `get(List)` and wraps the string as a one-element list).
  Use `cfg['get(java.lang.String)']('a.b')` or walk `cfg.valueMap()` (nested sections have `valueMap`).
- `getClass()` is hidden from scripts; use `x instanceof $LoadedClass` (works for Java classes, e.g. a container menu).

## Renamed / hidden vanilla members (crash source #3, from core/mixin of 2101)
A renamed method keeps working only under its new name; a hidden one is `undefined` ("Cannot find function").
A getter exposed as a PROPERTY shadows a Java method of the same name: the call then fails with `Cannot call property X in
object Y. It is not a function, it is "object"` - read the property instead (its type is the KubeJS one, e.g. a ResourceLocation).
| Vanilla | In KubeJS scripts |
|---|---|
| `Entity.getStringUUID()` / `getUUID()` | `getStringUuid()` / `getUuid()` |
| `Entity.level()` | hidden → property `entity.level` |
| `Entity.hurt(source, hp)` | hidden → `entity.damage(hp, source)` |
| `Entity.getType()` | `getEntityType()`; the property `entity.type` is the String id (`'minecraft:zombie'`, from source `kjs$getType`, used by `String(e.type)` - unverified in game: offline-tested only, Oct 2026) |
| `Entity.getPersistentData()` | `getForgePersistentData()`; `entity.persistentData` is KubeJS's OWN data (use one of them consistently) |
| `Entity.getYRot/getXRot/getDirection` | `getYaw/getPitch/getHorizontalFacing` |
| `Entity.teleportTo(..)`, `spawnAtLocation(..)`, `getPassengers()` | hidden (use KubeJS helpers) |
| `DamageSource.getEntity()` / `getDirectEntity()` / `getMsgId()` | `source.actual` / `source.immediate` / `getType()` |
| `Level.getGameTime()` | `getTime()` |
| `Level.dimension()` | **`level.dimension` is a property (ResourceLocation, `kjs$getDimension`)**: calling `level.dimension()` threw `Cannot call property dimension in object ServerLevel[...]` (a /command script died with this error). Use `String(level.dimension)`; `getDimensionKey()` is the ResourceKey variant per source |
| `Holder.is(TagKey)`, `is(ResourceKey)`, `is(Holder)` | hidden → `holder.is(ResourceLocation)`, `holder.isTag(rl)`, `holder.test(pred)`, `getRegisteredName()` |
| `ItemStack.enchant`, `getEnchantments`, `getTags` | hidden |
Not renamed (verified): `player.getItemBySlot(EquipmentSlot)`, `stack.hurtAndBreak(n, entity, slot)`, `get/setDamageValue`,
`player.isCreative()/isSpectator()`, `hasEffect/addEffect/removeEffect` with `MobEffects.X` holders, `level.getBiome(pos)`,
`player.blockPosition()`, `player.setStatusMessage(component)`, `player.containerMenu`, `player.give(stack)`.

## Reachable Java (`Java.loadClass`)
`kubejs.classfilter.txt` (build.377): exact deny > exact allow > deny prefix > **everything else allowed**.
- Denied: `java.lang` except boxed numbers, `String`, `StringBuilder`, `Character`, `Boolean`, `Object`, `Iterable`, `Comparable`,
  `Runnable`, … (so no `Class`, reflection, `System`); `java.io` (except `Closeable`, `Serializable`); `java.nio` (no `Files`,
  `Paths`); `java.net`; `java.util.jar|zip`; `net.neoforged.fml` (no `FMLPaths`, `ModList`, `ModConfig`, `ConfigTracker`);
  `net.minecraft.Util`; `dev.latvian.mods.kubejs.script|plugin|core`; `sun`, `com.sun`, `io.netty`, asm, mixin.
- Allowed: `java.util.*`, `java.math.*`, `net.minecraft.*`, `net.neoforged.neoforge.*` (e.g. `ModConfigSpec`,
  `server.ServerLifecycleHooks`), NightConfig (`com.electronwill.nightconfig.*`), mod classes, fastutil.
- The filter checks class lookups and arguments, not members of objects you already hold. Private fields/methods are
  invisible ("has no public instance field") - find a public route (e.g. a mod's public `ModConfigSpec`).
- A Java object that is also a JS function (e.g. `recipe.type`) hides its fields and can't be turned into a string.

## Files
- `JsonIO`: `readJson(path)` (null if missing), `read(path)` (map), `readString(path)` = **parses JSON** and re-serialises (not a
  text reader), `write(path, json)`, and **`write(path, null)` deletes the file** (`Files.deleteIfExists`; `NBTIO.write(path, null)`
  does the same). `NBTIO.read/write` for NBT. No plain-text reader: read TOML with NightConfig (explicit overload above).
- Any path inside the game folder works (`config/`, `defaultconfigs/`, `saves/`); the generated README's claim that only
  `kubejs/config` is writable is outdated. Dumps for the user: `JsonIO.write('kubejs/exported/x.json', obj)`.
- `kubejs/data` and `kubejs/assets` act as packs above the mod jars: a file with the same path replaces the jar's file, but
  TAG files merge - add `"replace": true` to really replace a tag. Lang keys are global: extra lang files can live in their own
  namespace folder (`kubejs/assets/<any>/lang/ru_ru.json`) so a generator that owns another lang file never overwrites them.
  (Mod JAR assets are NOT below `kubejs/assets`: a mod's own display / model files win over kubejs copies; only packs loaded
  below kubejs - e.g. the TaCZ resource packs - are overridden. To override a mod jar's file ship a small mod jar that loads AFTER it.)
- At startup KubeJS validates EVERY file name under `kubejs/assets` and `kubejs/data` (log: `Validated N files in kubejs/assets/`):
  only resource-path characters `[a-z0-9/._-]`. One uppercase letter (`CREDITS.txt`, `README.md`, `Texture.png`) = startup
  error screen `Invalid file name: Uppercase 'C' in kubejs/assets/...`. Generators must write lowercase names (check with
  `re.fullmatch(r'[a-z0-9/._-]+', relpath)`); keep notes/licences lowercase or outside those folders. On Windows a file written
  as `credits.txt` over an existing `CREDITS.txt` keeps the old name - the case-only rename has to be done on the machine.

## Events and timing (2101)
| When | What runs | Notes |
|---|---|---|
| KubeJS mod constructor (parallel mod construction) | startup scripts' top-level code, `StartupEvents.init` | before CLIENT/COMMON configs load, after STARTUP configs of mods already constructed |
| `RegisterEvent` | `StartupEvents.registry('item'…)` | `event.create(id).texture().maxStackSize().rarity().maxDamage()` unchanged |
| `FMLLoadCompleteEvent` | `StartupEvents.postInit`, `ItemEvents.modification`, `BlockEvents.modification` | COMMON configs loaded |
| world load/creation, inside `WorldLoader` (no `MinecraftServer` yet) | server scripts' top-level code, `ServerEvents.tags`, `ServerEvents.recipes` (at `RecipeManager.apply`) | **SERVER mod configs not loaded yet** (they load right after, in `handleServerAboutToStart`). Opening the Create World screen runs this pass too. |
| `/reload` | the same server-script pass | server running, SERVER configs loaded |
| NeoForge `ServerStartingEvent` (after `loadLevel`, spawn prepared, before the first tick) | `ServerEvents.loaded` | SERVER configs loaded; worldgen of spawn chunks already done |
| `ServerStoppingEvent` / every tick | `ServerEvents.unloaded` / `ServerEvents.tick` | |
No script event on `ServerAboutToStart`. All `ServerEvents`: registry, generateData, loaded, unloaded, tick, tags,
commandRegistry, command, basicCommand, basicPublicCommand, recipeMappingRegistry, recipeSchemaRegistry, recipes,
afterRecipes, specialRecipeSerializers, compostableRecipes, modifyRecipeResult, modifyRecipeIngredient.
- There is **no `Utils.server`** in 2101 (a right-click handler using it died with `has no public instance field or method named
  server`). Use `event.server`, or
  `Java.loadClass('net.neoforged.neoforge.server.ServerLifecycleHooks').getCurrentServer()` (null while no server runs,
  i.e. during the world-loading pass of server scripts).
- A command: `ServerEvents.commandRegistry(event => { event.register(event.commands.literal('x').requires(src => src.hasPermission(2))
  .executes(ctx => { let src = ctx.getSource(); try { ... src.sendSystemMessage(Text.gold('...')) } catch (e) { src.sendSystemMessage(Text.red('/x failed: ' + e)) } return 1 })) })`.
  Put every lookup that may differ in a helper `safe(fn, fallback)` that logs a warning and returns the fallback, so one failing
  Java call never hides the rest of the output.
- Run code AFTER the other handlers that touch a joining mob (e.g. In Control `onjoin` rules set the base max health): in
  `EntityEvents.spawned` only push the entity into a queue, process the queue in `ServerEvents.tick` (end of the tick, after every
  join handler), and mark the mob in its `persistentData` so a chunk reload does not apply it twice. Unverified in game
  (offline-tested with the real Rhino only, Oct 2026): confirm the order with a log line.
- Other events (all used in the DeceasedCraft port): `EntityEvents.spawned('minecraft:item')`, `EntityEvents.beforeHurt` (`event.damage`,
  `event.setDamage(x)`, `event.source.actual`), `EntityEvents.death`, `PlayerEvents.tick` (fires per player; check
  `player.level.isClientSide()`, throttle with `player.tickCount % 20`), `PlayerEvents.inventoryChanged`,
  `ItemEvents.rightClicked` (`event.item`, `event.player`, `event.cancel()` = exit, put it last), `ItemEvents.modifyTooltips`
  (works from server scripts, synced to clients), `ItemEvents.dynamicTooltips` (client).
- `NativeEvents.onEvent('full.event.Class', e => ...)` for mod events (e.g. TaCZ `EntityHurtByGunEvent$Pre`): these handlers
  are NOT wrapped by KubeJS error handling - always `try/catch` and log once.

## ItemEvents.modification (2101 source)
`event.modify(itemPredicate, item => { item.maxDamage = 500 })`. Available: `maxStackSize`, `maxDamage`, `damage`,
`setUnbreakable()`, `itemName`, `repairCost`, `food`/`modifyFood`, `setFireResistant()`, `tool`, `rarity`, `lore`,
`glintOverride`, `addAttributeModifier(attr, AttributeModifier, EquipmentSlotGroup)`, `setAttributeModifiers(list)`,
`setAttributeModifiersWithTooltip`, `attackDamage`/`attackSpeed`/`baseAttackDamage`/`baseAttackSpeed`, `burnTime`,
`craftingRemainder`, `tier(cb)`, `disableRepair()`. **No** `armorProtection`/`armorToughness`/`digSpeed` (the wiki page is
outdated). Armor stats → attribute modifiers on the item (or NeoForge `ItemAttributeModifierEvent` via NativeEvents in a
startup script, which replaces modifiers by id per slot group).

## Custom items, tools, shields (registered without errors in game, Oct 2026; the unverified parts are marked)
- Tool items: `StartupEvents.registry('item', e => e.create(id, 'sword'|'axe'|'pickaxe'|'shovel'|'shears').tier('pack:t2')
  .attackDamageBaseline(x).speedBaseline(y).maxDamage(n))`; damage shown = 1 (player base) + tier attack bonus (wood 0,
  iron 2, diamond 3, netherite 4) + damage baseline; attack speed shown = 4 + speed baseline (so baseline = speed - 4).
- Own tiers: `ItemEvents.toolTierRegistry(e => e.addBasedOnExisting('pack:t2', 'iron', t => { t.repairIngredient = ... }))`.
  An unknown tier name in `.tier()` silently falls back to IRON - log/check the names.
- A class KubeJS has no builder for (e.g. a real shield): `e.createCustom(id, () => new $ShieldItem(new $ItemProperties()
  .durability(n)))` with `Java.loadClass('net.minecraft.world.item.ShieldItem')` / `...Item$Properties`; the blocking pose
  needs `ItemEvents.modelProperties(e => e.register(id, 'minecraft:blocking', (stack, level, entity) => ...))` in the same
  startup script (unverified: the blocking pose itself was not confirmed in game, Oct 2026).
- Hide items a mod still registers: `StartupEvents.modifyCreativeTab(tab, e => e.remove(id))`, recipe viewer
  `RecipeViewerEvents.removeEntriesCompletely('item', e => e.remove(id))` (client script), `ServerEvents.tags('item',
  e => e.removeAllTagsFrom(id))` + recipe removal (scripts load clean; unverified: whether JEI really hides the item, Oct 2026). A mod item cannot be
  unregistered by scripts.

## API changes from 1.20.1 hit in practice
```js
// recipe type of a findRecipes() result: r.type is a callable RecipeTypeFunction (String(r.type) -> "Cannot find default value")
let type = r.json && r.json.has('type') ? String(r.json.get('type').getAsString()) : ''
// ingredient stacks: r.getOriginalRecipeIngredients().forEach(ing => ...)
ing.getStackArray()                       // ing.getItems() -> "Cannot find function getItems"; first id: String(stacks[0].id)
stack.id; stack.getMaxStackSize()         // 'tacz:ammo'
player.stats.getPlayTime()                // ticks; player.nbt.playtime is gone, PlayerStatsJS has no getValue(stat)
event.server.runCommandSilent(`hordes start ${event.player.username} 6000`)
event.player.tell(Component.translate('key').append(' ').append(Component.green(String(n))))
```
- Tags `#forge:*` → `#c:*` (`c:ingots/iron`, `c:plates/steel`, `c:rods/iron`, `c:wires/iron`, `c:leathers`, `c:strings`,
  `c:sands`, `c:glass_blocks`, `c:dyes/<color>`).
- Item NBT → data components (`minecraft:custom_data`, `minecraft:max_stack_size`, …). TaCZ: `GunId`/`AmmoId` in
  `custom_data`; ammo stack size only via `stack.getItem().setAmmoId(stack, stack.getItem().getAmmoId(stack))`.
- `event.findRecipes(...)` sees the datapack recipes only, not recipes added by scripts in the same pass - keep your own
  list of what a script added (e.g. to generate scrapping recipes from it).
- No KubeJS Create addon → `event.recipes.create.*` is undefined; use `event.custom({...})` with Create 6 JSON (from Create
  `mc1.21.1/dev` generated recipes):
  ```js
  const ing = s => s.startsWith('#') ? { tag: s.substring(1) } : { item: s }
  event.custom({ type: 'create:crushing', ingredients: [ing('minecraft:iron_helmet')], processing_time: 150,
    results: [{ id: 'minecraft:iron_nugget', count: 4, chance: 0.5 }] }).id('pack:scrap/iron_helmet')
  event.custom({ type: 'create:mechanical_crafting', category: 'misc', accept_mirrored: false, show_notification: false,
    key: { c: ing('#c:plates/steel') }, pattern: ['ccc', 'c c'], result: { id: 'pack:thing', count: 1 } }).id('pack:thing')
  const step = (inc, what, keep) => Object.assign({ type: 'create:deploying', ingredients: [ing(inc), ing(what)],
    results: [{ id: inc }] }, keep ? { keep_held_item: true } : {})
  event.custom({ type: 'create:sequenced_assembly', ingredient: ing('immersiveengineering:sheetmetal_iron'),
    transitional_item: { id: 'pack:incomplete_part' }, loops: 4, results: [{ id: 'pack:part' }],
    sequence: [step('pack:incomplete_part', 'pack:part_blueprint', true), step('pack:incomplete_part', '#c:plates/iron')] }).id('pack:part')
  // fluid TAG ingredient (NeoForge inline), e.g. in create:filling (verified vs Create mc1.21.1/dev generated recipes):
  event.custom({ type: 'create:filling', ingredients: [ing('minecraft:glass_bottle'), { type: 'neoforge:tag', tag: 'c:honey', amount: 25 }],
    results: [{ id: 'minecraft:honey_bottle' }] })
  ```
  A mod fluid without a common tag: ship your own fluid tag (`data/<ns>/tags/fluid/x.json`).

## Mod configs from scripts
Prefer letting NeoForge load the file (see `neoforge-mod-configs`: defaultconfigs seeding by deleting `config/<file>` in a
startup script). If a value must be set from JS: box Int/Long, never `cv.set(5)` on an `IntValue`; `set()` doesn't save and
only updates the cached value when the spec entry has no restart requirement - good for temporary in-memory switches
(in the DeceasedCraft port: Lost Souls chest lock off on day 0, back from the config file afterwards).

## Script hygiene
- Scripts of one type share ONE global scope: prefix top-level names (`dcThing`, `$DCClass`), or two files with
  `const helper` collide (the DeceasedCraft port uses the prefix `dc`). Startup and server scripts are separate scopes. Check:
  `Select-String -Path *.js -Pattern '^const ([A-Za-z_$]*)' | ForEach-Object { $_.Matches[0].Groups[1].Value } | Group-Object | Where-Object Count -gt 1`.
- Headers: `// priority: N` (higher first, then path), `// ignored: true`, `// packmode: x`, `// requires: <modid>` (repeatable,
  `requires: client` = client only).
- Guard optional items: `try { return !Item.of(id).isEmpty() } catch (e) { return false }`.
- Replacing a mod recipe: `event.remove({ output: id })`, then add with a stable `.id()`.
- `kubejs/config/common.json`: `match_json_recipes`, `server_only` (vanilla shaped/shapeless, disables KubeJS registries),
  `startup_error_gui`, `default_max_stack_size`; `allow_async_streams` is read but unused.

## Offline test with the real Rhino
Take `mods/rhino-*.jar` from the instance, the NightConfig `core` and `toml` jars and the guava jar from its `libraries/`
folder; compile a small Java runner (JDK 21) against them that creates `ContextFactory`, registers `Path`/`File` type wrappers
resolving strings against a fake game dir (as KubeJS does), binds mock `JsonIO`/`console`/`ServerEvents`/`Java.loadClass` and
real NightConfig classes, then evaluates the script. A runner that evaluates several JS files in ONE scope is the simplest
shape: `java -cp "out;rhino.jar" Runner prelude.js script.js test.js` (`;` separates the classpath on Windows, `:` on Linux).
Mocks must use the renamed names, or the test passes while the game fails. On Windows in DSH (Windows PowerShell 5.1): write the runner and test
scripts to files (`python -c` with backslashes / apostrophes breaks; 5.1 has no heredoc), pass `C:/...` paths (not `/c/...`) to
Windows java / python, and pass a long classpath through an `@argfile`.
In the DeceasedCraft port the ready runners are in its `_port/tools/` (not shipped with this skill): `rhino_harness/`
(`Harness.java`, `KubeMock.java` for config scripts; `armor/` = `JsRun.java` + `prelude.js`, pure-JS mocks using the KubeJS
names above) and `dchp/test/` (`JsRun2.java`).

## Passport
Created: 2026-10 from the DeceasedCraft 1.21.1 port (KubeJS scripts for armor, melee, recipes, hordes, config seeding).
Checked: Oct 2026 against KubeJS 2101.7.2 build.377 + Rhino 2101.2.8 build.91 sources and real Rhino runs; v34 audit made the
skill portable (project paths and status removed, examples labelled).
Limits: KubeJS 2101 / NeoForge 1.21.1 only; for 1.20.1 or 1.18.2 KubeJS the renames and the event table differ. Items marked
"unverified" were tested offline only.
History: CHANGELOG.md next to this file (what changed, when and why).
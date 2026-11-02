---
name: "tps-optimization-neoforge"
description: "Лаги в NeoForge 1.21.1 модпаке, особенно с KubeJS 2101 и толпами мобов (зомби/орды, Lost Cities, In Control, Enhanced AI): падение TPS, «Can't keep up», пики MSPT, фризы, просадки FPS. Метод: замер spark (сервер и клиент), логи, потом правка скриптов, модов и миксинов, конфигов. Триггеры: «лаги», «тпс упал», «фризы», «фпс просел», «тормозит в городе / на орде», «оптимизация», «разбери профиль», «спарк», «зависает при выходе», spark link, «сервер ждёт чанки», «дыры в лодах», «прогрузка зависла»."
---

# TPS / FPS optimization: KubeJS 2101 scripts + NeoForge 1.21.1 mods

Rule: measure first, change one thing, measure again. Code reading only gives candidates; a profile or a log
correlation decides. Related skills (same repository, if installed): `kubejs-neoforge-2101` (script API), `neoforge-mod-configs`
(configs), `modpack-port-neoforge` (porting a pack: folders, converters). Mod facts below carry version stamps; they were
verified in the DeceasedCraft port and in Space Journey (NeoForge 21.1.x, October 2026) - re-check them against your
versions. Passages marked "In the DeceasedCraft port" are examples of the method, not rules for every pack. Numbers in the
examples are measurements of the named pack: quote them as an example, never as the gain, rate or frequency to expect in
another pack - there its own profile sets the ceiling (section 1) and its own runs the frequency.

## 1. Measure
- **spark** (NeoForge 1.21.1 build in `mods/`):
  - `/spark tps`, `/spark health --upload` - overview (TPS, MSPT mean / 95th, CPU, memory); `/spark gc` - GC pauses.
  - Hitch hunting: `/spark profiler start --only-ticks-over 100 --timeout 300`, reproduce the lag (enter the
    building, wait for the horde, fly into new chunks), `/spark profiler stop` -> viewer link. Normal load:
    `/spark profiler start --timeout 120`. Allocation pressure: `--alloc`. Worker threads (chunk gen): `--thread *`.
  - Client FPS (render thread): `/sparkc profiler start --timeout 60` - the client-side spark command.
  - `/spark tickmonitor --threshold-tick 100` prints every slow tick in chat (timestamps for the log).
  - Read the tree by mod / package; KubeJS work shows as Rhino frames (`dev.latvian.mods.rhino.*`) under the event
    that called it (`EventHandler.post`, the NeoForge event class) - find the handler by the event, then bisect by
    disabling scripts.
  - **Reading a profile as data** (reliable numbers instead of clicking the viewer). Raw profile: the protobuf at
    `https://spark-usercontent.lucko.me/<id>`. Fetching `https://spark.lucko.me/<id>` without a browser returns the viewer
    page, not the data. Without the scripts below, open `https://spark.lucko.me/<id>?raw=1&full=true` in a browser - the viewer
    decodes the profile and shows JSON (plain `?raw=1` = metadata only); save it (Ctrl+S) or run JavaScript on the page.
    Shape: `threads[].children[]` is a FLAT node list (`className`, `methodName`, `times[]` per time window in ms,
    `childrenRefs[]` = indexes into the same list), `threads[].childrenRefs` = roots, `classSources` = class -> mod id
    (vanilla / Java classes missing), `timeWindowStatistics` = per-window TPS / MSPT / entities. inclusive = sum(times),
    self = inclusive - children; count a method once per stack (recursion / event re-entry); % of the thread's root total.
    Scripts of this skill (Python stdlib only, each has `--help`; run them with `python -I -X utf8`: a profile is downloaded data):
    `python -I -X utf8 scripts/spark_fetch.py <id|link|file.bin> [--out spark_profiles]` downloads the
    protobuf (or decodes a saved .bin offline) and writes `<out>/<id>.json`, byte-identical to the viewer's raw page;
    `python -I -X utf8 scripts/spark_summary.py <json> --thread "Server thread" [--grep <regex>]` prints top self / inclusive methods, per mod, callers of
    a method (pools are grouped as `c2me-worker (x5)`, a unique prefix works); `python -I -X utf8 scripts/spark_chains.py <json> --thread <name> --match
    <regex>` sums the time of the matching methods by the chain of their callers, mixin glue skipped (who holds the server thread
    in `ServerChunkCache.getChunkBlocking`, who asks OpenGL state on the render thread).
  - `EventBus.post` with a big share is the SUM of all mod handlers of the events - split it by the frames below it.
  - A large SELF time in a tiny method = it is called in a loop by its parent (look at the callers), not slow itself.
- **NeoForge**: `/neoforge tps` (per dimension), `/neoforge entity list` (counts per type - look for hundreds of
  one mob, items, arrows, XP orbs).
- **Logs** (`logs/latest.log`): `Can't keep up! ... Running Nms or N ticks behind` lines; correlate each with the
  lines 0-3 s before it (advancements, chat messages like "entered a horde building", chunk / block entity errors,
  `/reload` = "Loaded N advancements" + datapack reload). False spikes: world load, "Saving and pausing game"
  (singleplayer pause; a big spike right after "Saving chunks for level ..." lines is usually Esc), first join;
  `/reload` takes ~6 s (expected).
  A log of more than ~10 MB per session = spam: every stack trace is built on the thread that logs it.
- **Reading `Can't keep up`** (MinecraftServer.runServer, MC 1.21.1): the number is the lag accumulated since the last
  warning, not a rate. It is printed only when the server is more than 1 s + 20 ticks behind (2 s at 20 TPS), at most once
  per 10 s + 100 ticks of schedule (300 ticks), and then the whole ticks of lag are written off
  (`nextTickTimeNanos += (lag / tickLength) * tickLength`). Do not read N ms as a rate (per minute or per tick): it is the
  backlog of the last ~300 ticks. Under sustained overload MSPT = wall time between two warnings / 300 = 50 + N / 300 ms,
  TPS = 1000 / MSPT. A single long tick is found in the lines 0-3 s before its warning; sustained overload builds up over the
  whole interval since the previous warning, so look at everything between the two. Example (Space Journey, 2026-10-14):
  warnings with N = 30-37 s were first read as 1-2 TPS; the real rate from their timestamps was 5.7-7.3 TPS.
- MSPT measures the tick, not the waits between ticks. When the main thread blocks outside the tick (tasks run in
  `waitUntilNextTick`, a synchronous chunk wait), MSPT stays low while the server falls behind: a flight over new terrain showed
  MSPT 5.9 ms and "Running 39219ms or 784 ticks behind" (Sengoku Jidai World, 2026-10-27). Count the real TPS (server ticks per
  second of wall time) next to MSPT.
- Main thread blocked on chunks: in the profile `ServerChunkCache.getChunkBlocking` -> `MainThreadExecutor.managedBlock`; follow
  the callers. From `ServerGamePacketListenerImpl.handleMovePlayer` (`doCheckFallDamage` -> `getFluidState`): the player moves
  faster than chunks generate and the server waits for the chunk under him (vanilla; 88% of the server thread in a 20 blocks/s
  flight over a new world); levers are pre-generation and faster generation, not configs of the client. From a mod's tick
  handler: section 4, `isLoaded` and `getHeight`.
- spark's Java sampler (the engine on Windows) slows the whole JVM: the server fell from 7-9 TPS to about 1 during a profile,
  with `--thread *` and with the server thread alone (2026-10-27). Shares of time in such a profile still point at the cause;
  absolute numbers come from runs without it.
- Separate server lag from client FPS: `[Server thread]` / TPS vs `[Render thread]` / FPS (a GPU / render problem
  is not a TPS problem).
- A hang is not lag: when a tick never ends (stuck on "Saving worlds", a black screen after leaving a world, the server stops
  answering) read thread stacks, not a profile. Take the `Server thread` stack 2-3 times 5 s apart (`jcmd <pid> Thread.print`
  of a JDK, or a watchdog thread in your own mod: `Thread.getAllStackTraces()` after a time limit, and in an unattended test
  run then `Runtime.getRuntime().halt(3)` so it ends); the frames that repeat in every dump are the loop (Space Journey
  2026-10-16: a watchdog with three dumps found the case in section 4). The same stack in every dump in `getChunkBlocking` ->
  `managedBlock` while the chunk workers (C2ME) idle is a chunk wait that never ends: section 4, `getHeight`.
- Compare variants under the same load: an already generated world (a new world generates chunks and LODs in the background
  for minutes) and nothing else heavy on the PC (builds, other agents' runs; Space Journey 2026-10-16: the same computation took
  147.9 s alone and 200.1 s next to review agents). Client FPS: the same spot, one factor off at a time, several F3 readings per
  step (5-25 there); a number from another dimension or another world is no baseline.
- A method's share of a thread in the profile is the ceiling of what fixing it gives that thread: removing 4% of the server
  thread lifts TPS by about 4% at most, not by 25%. Shares of different threads do not add up: the thread that limits the work
  sets the ceiling (the server thread for TPS; the C2ME workers for Chunky speed while the server thread idles; in a flight that
  waits for the chunk under the player, the speed of generation). Measure the baseline 3+ times: one run cannot show an
  effect smaller than the spread of the baseline, and a run that beats the ceiling is noise until repeated (or the switch
  changed more than the profiled method - profile that variant too). Sengoku Jidai World 2026-10-27, flight over a new world:
  baseline TPS 7.2-7.8 (3 runs), one run with the feature switched off 9.6; the fix of the same 4% gave 7.5 while the profile
  showed the chain gone.
- No spark (e.g. a dev client): JFR on the live JVM, `jcmd <pid> JFR.start settings=profile`, then
  `jcmd <pid> JFR.dump filename=<f>.jfr` while it runs; the `jdk.ThreadCPULoad` events give the CPU share per thread (the render
  thread is named `main` there).
- Memory: ask for the launcher's `-Xmx` and the RAM. Too small heap = frequent GC stutter, far too big = long pauses.
  Java 21: G1 (default) or Generational ZGC (`-XX:+UseZGC -XX:+ZGenerational`). There is no manual memory management
  in Java - the lever is the allocation rate (fewer temporary objects per tick), which `--alloc` shows.

## 2. Usual causes, in this order
1. Error / log spam per block, entity or tick (failed block entities in world generation, unknown registry ids in
   data, a script error inside a tick handler). Fix the data in the converter; log once.
2. Missing performance mods / configs that the ORIGINAL pack had (when the pack is a port): compare the mods folders
   first (a port often drops 20-30 of them silently) and the AI mod configs (a newer Enhanced AI with default config =
   every module on).
3. Mass spawns: horde buildings, hordes, In Control spawner bursts - N mobs x (spawn rules + AI goals + equipment +
   attribute changes + scripts on spawn) in one tick. Levers: mobs per batch / per tick, max mobs, spacing in time.
4. Pathfinding: many mobs with a target inside buildings (mining / climbing AI multiplies it), large follow range.
5. Chunk generation (Lost Cities, structure mods): worker threads + main thread chunk loading; pre-generate
   (Chunky) or lower view / simulation distance for tests.
6. Entity count growth: items / XP orbs / projectiles that never despawn, mobs that persist (name tags, picked up
   items, `persistenceRequired`).
7. Scripts and mixins on hot paths (below).
8. Client FPS in a pack with Distant Horizons: its distant generation and its LOD rendering (Space Journey 2026-10-21, one PC,
   DH 3.3.2, LOD radius 256, F3 on one spot: 55 FPS as is, 109 without distant generation, 226 without DH rendering).
   DH 3.3.3 render thread (Sengoku Jidai World, 2026-10-27, profile of a flight): `GLState.saveState` / `close` around every
   post-processing pass (SSAO, fog, vanilla fade, TAA, copy) took about 40% of the render thread in glGet* / glIs* queries
   (likely driver sync points where the CPU waits for the GPU - not measured; the profile only shows where the thread waits);
   DH's `LightMapWrapper.uploadLightmap` asks the active texture with `glGetInteger` on every lightmap update (about 10% in a
   second profile); config levers `enableSsao`, `enableAntiAliasing`, `vanillaFadeMode`. Polytone 5.2.1
   `VoxelVolumeManager.bindTo` calls `glGetUniformLocation` on every `ShaderInstance.apply` (about 10%).
   DH LOD holes near the edge of the generated world: DH 3.3.3 pauses its own generation (`ThreadPoolUtil.worldGenThreadsCanRun`,
   bytecode) when `pauseIfMovingQuickly` and the camera averages more than 20 blocks/s, when the ChunkToLodBuilder queue holds
   more than 1000 (in code), or when `limitIfServerUnhealthy` and the server is unhealthy. In a 20 blocks/s flight over a new
   world switching off either config alone changed nothing (holes 93-100% before and after): the server waited for the chunk
   under the player (section 1), so fix the server first.

## 3. KubeJS 2101 scripts
- Tick handlers (`ServerEvents.tick`, `PlayerEvents.tick`, `LevelEvents.tick`) run 20x per second (x players).
  Throttle and return before any Java call: `if (event.server.tickCount % 20 != 0) return`; per player stagger
  `(player.tickCount + player.id) % 20`. Do the expensive part every N ticks, the cheap check every tick only if needed.
- No per-tick block / entity scans in JavaScript: one Java-side query (`level.getEntitiesOfClass(cls, aabb)`,
  `ChunkAccess.findBlocks(Predicates.in(stateSet), consumer)` - palette skips empty sections), queues with a budget
  per tick (N chunks per tick, retry later, drop after M tries); never walk a whole waiting list every tick (FIFO
  queues: one for new work, one for retries with a constant delay).
- `Java.loadClass` once at the top of the file (or lazily once), never inside a handler. Cache registry lookups and
  derived tables (JS objects / Java HashMap); prefer a Java `Predicate` over a JS lambda called per element.
- Hot events: `NativeEvents.onEvent` on `ItemAttributeModifierEvent` (fires per stack per attribute query, not
  cached by NeoForge), `LivingIncomingDamageEvent` (fires for every `hurt()`, even hits blocked by invulnerability
  frames) / `EntityEvents.beforeHurt` / `afterHurt` (`LivingDamageEvent.Pre` / `Post`, every applied hit),
  `EntityJoinLevelEvent` / `EntityEvents.spawned` (every arrow, item, XP orb, bullet, and every entity loaded with a
  chunk), `PlayerEvents.inventoryChanged`. Exit on "no player involved" with the first 2-3 calls; merge handlers of
  the same event; keep the body O(1).
- **Targeted handlers**: `EntityEvents.spawned('minecraft:zombie', cb)` per type. KubeJS skips building the event
  and entering Rhino for a type only when EVERY handler of the event is targeted - one untargeted handler anywhere
  makes all types pay (`TargetedEventHandler.hasListeners`). Register per type from a list or from the registry.
- Overloaded Java methods: call the hot ones by signature (`level['playSound(net.minecraft.world.entity.player.Player,double,double,double,net.minecraft.sounds.SoundEvent,net.minecraft.sounds.SoundSource,float,float)'](...)`) - no per-call
  overload search, no ambiguity.
- No allocation-heavy work per tick: string building, `console.*`, `Text` components, JSON, NBT reads / writes
  (`persistentData`). Keep state in JS maps keyed by UUID string; write NBT on change / logout.
- `server.runCommandSilent` parses with Brigadier every call - fine for a right click, not for a tick loop; prefer the
  mod API.
- Errors: try/catch in every `NativeEvents` handler (KubeJS does not catch them and the throw repeats every tick),
  count errors, log the first ones, disable the handler after ~20. A try/catch that swallows a TypeError per call is
  itself slow (~7-9 us per exception in Rhino vs ~0.2 us for the right check) and hides bugs.
- Offline check before shipping: run the script in the Rhino harness with stubs and count Java calls per tick.

### Rhino 2101.2.8 pitfalls (verified with the real jar)
- `const` anywhere inside a `try { }` block throws `TypeError: redeclaration of var X` on EVERY call (also inside an
  `if` within the try). `const` in a loop body keeps the FIRST iteration's value (silent). Closures created in
  `for (let i ...)` all see the last `i`. `let` in the loop body and `forEach` callbacks are fine; top-level `const`
  and `const` directly in a function body are fine. Scan all scripts with an acorn AST walker (const inside
  TryStatement.block or a loop body without a function boundary in between).
- `entity.getType()` / `entity.type` is `kjs$getType()` = the id String (`.getCategory()` throws); use `e.isMonster()`
  (= category not friendly), `e.living`, `e.player`. `level.dimension` is a property (ResourceLocation).
- Load order of scripts: higher `// priority:` first, then path A-Z case-insensitive. A script that must run after
  another one's handler of the same event needs a lower priority (e.g. `// priority: -100`).

## 4. Java mods and mixins
- Mixins on hot paths (entity tick, `getEntities`, render, lighting): HEAD inject with a cheap early return, no
  allocation, no logging; cache per tick when the same answer is asked many times.
- `Level.isLoaded(pos)` / `hasChunkAt` means "the chunk has a FULL ticket", not "the chunk is ready" (MC 1.21.1). A tick handler
  that checks it and then calls `getBlockState` makes the server generate the chunk synchronously. Example: Sengoku Jidai 2.1.5
  `WarmWaterSystem.meltIceNearMagma` (every 20 ticks, 6 random spots within 8 blocks of each player): 11% of the server thread in
  a flight over generated land, 4% over a new world. The non-blocking check is
  `level.getChunkSource().getChunkNow(x >> 4, z >> 4) != null`; a mixin with it (`@WrapOperation` on that `isLoaded` and on
  `getBlockState` in `isNearMagmaBlock`) removed the chain from the profile, and the flight TPS stayed within the baseline
  spread (section 1: a 4% ceiling).
- `Level.getHeight(type, x, z)` has the same trap: it checks only `hasChunk` - the chunk has a FULL ticket and may still be
  generating - and then `getChunk` waits for it (a chunk without a ticket gets `getMinBuildHeight()` at once, no wait). That
  wait can also never end: Sengoku Jidai 2.1.5 `IkuchiSpawner.findOceanSpawn` (every 2400 ticks, up to 40 random spots
  32-96 blocks from a player) hung the server thread for 14 minutes during a Chunky run - the same stack in 22 watchdog dumps,
  the C2ME workers and the Chunky thread idle (C2ME 0.4.0-alpha.0.123, not in every run; why the chunk never came is not
  known). Same fix: `getChunkNow` first. For a chunk that is not ready skip the spot; Ikuchi's mixin answers
  `level.getMinBuildHeight()` (what `getHeight` returns for a chunk without a ticket) because the caller then reads the fluid
  at that height - 1, below the world, where nothing loads. If the caller reads at the height itself (inside the world), that
  read waits for the chunk again: skip the spot instead or guard that read too. A hang that does not come in every run is
  shown gone only by several clean runs after the fix, not by one (2026-10-27).
- A world generation step that gets slower as the session goes on: a global registry walked for every noise sample. Sengoku
  Jidai 2.1.5 `AdjustableBeardRegistry.computeContribution(x, y, z)` loops over all beard boxes ever added (added in the
  `PoolElementStructurePiece` constructor, at generation and at every load from NBT; cleared only at server start): 16.4% of the
  C2ME workers' own time during a 16 641-chunk Chunky run. There is no config; the fix that kept the terrain the same: walk only
  the boxes that can reach the sample's chunk column. `AdjustableBeardBox.computeContribution` returns exactly 0.0 when the
  point is `radius` or more blocks from the box on X or Z, so the boxes left out add nothing, and kept in the registry's order
  the floating-point sum is the same bit for bit. A `@ModifyExpressionValue` on the `ACTIVE_BEARDS` read hands the loop a
  per-thread cached array for the column (rebuilt when the column or the registry array changes; nothing allocated per sample).
  No lock is needed only because Sengoku's `add` replaces the volatile array with a longer copy (copy-on-write): a thread's
  snapshot never changes under it. A registry that appends in place needs that first (a copy-on-write array or a lock in `add`),
  or the cache can miss a box. The cache rescans the whole registry once per column and thread - cheap for the beard boxes of
  that run; for a much larger registry index the boxes by chunk in `add` instead (each chunk keeps the boxes that reach it, in
  registry order). The registry left the top of the workers' profile, and the Chunky run gained about as much as its share had
  been (section 1). Prove the equality offline first: the real classes, random boxes and points on the noise grid, compare
  `Double.doubleToRawLongBits`, and a filter made wrong on purpose must fail (one block short of `radius` is still exact here -
  zero starts at `radius`; two blocks short is caught). The cost grows with the registry, so the gain grows with the run:
  compare runs of the same length.
- Bytecode of a Fabric mod loaded through Sinytra Connector with Mojang names: Connector keeps the remapped jar in
  `<game>/.cache/connector/<mod>_mapped_moj_1.21.1.jar` (javap there shows `ServerLevel.isLoaded` instead of
  `class_3218.method_8477`). Mixins of a NeoForge mod apply to such a mod (Connector 2.0.0-beta.17, 2026-10-27: it sits in the
  TRANSFORMER layer, `sengoku@2.1.5` in stack traces; a log line from the mixin handler proved it). No Fabric jar on the compile
  classpath is needed when the handlers use only Minecraft types: `@Mixin(targets = "<class>")` plus MixinExtras
  `@WrapOperation` (bundled with NeoForge 21.1); depend on the Fabric mod's id with the exact version in `neoforge.mods.toml`
  (the mixin was written against that bytecode). When a handler needs the mod's own types (its fields, a class of it as a
  parameter), compile against the remapped jar: `compileOnly files("<game>/.cache/connector/<mod>_mapped_moj_1.21.1.jar")`;
  the mod and yours share the game layer, so a helper class in your own package may use those types too (Sengoku 2.1.5,
  2026-10-27).
- Event listeners: right bus and side, filter first; `receiveCanceled = true` only when needed.
- Diagnostics (StackWalker, exceptions for stack traces): once per source (`Set` of seen keys), never per call.
- Block entities: no tick work while idle; invalid saved block entity data in structure palettes -> strip it in the
  converter (it fails again in every chunk that uses the palette).
- MCreator mobs: look for `refreshDimensions()` in `baseTick` ("model scale" feature) - an `EntityEvent.Size` post per
  mob per tick; a mixin can skip it while the scale is unchanged (only if the profile shows it).
- Broken throttles in mod tick handlers: read the bytecode of a handler that shows up every tick. Example, Lost Radar 2.0.0
  `EventHandlers.onPlayerTickEvent`: `tickCounter` starts at 10 and is never reset -> `PlayerMapKnowledge.tick` (a
  Lost Cities `getChunkInfo` of the player's chunk) runs every tick per player (a measurable share of the tick in a city).
  Fix with a mixin (reset the counter / skip while the player stays in the same chunk). Check first whether your pack
  already carries such a fix.
- Lost Cities queries from OTHER mods are a hidden cost: `ILostCityInformation.getChunkInfo` -> `BuildingInfo` ->
  `City.getCityFactor` loops over the chunks in the city radius calling `City.isCityCenter` (a `new Random` per chunk,
  not cached). Callers seen: Lost Radar, In Control `city` rule checks (`LostCitySupport.isCity`), Lost Souls per tick.
  A per-chunk cache (pure function of seed + chunk + profile) is a safe mixin target.
- Per-tick `canUse()` that runs pathfinding (MCreator goals, e.g. Undead Revamped `TheheavyEntity$2`): throttle in a
  mixin (every N ticks) if the profile shows it.
- Prove mixins apply offline (Mixin + ASM verifier harness), then profile in game.
- Mixin checklist (verified cases, DeceasedCraft port, v32): a call into ANOTHER mod's code from a tick (its container
  capability, its registry) goes inside try / catch that logs once - an exception there crashes the server tick;
  `@Pseudo` + `remap = false` for mod targets, default require = 1 when silence would hide a broken feature; a machine
  output goes only into storage blocks (#c:chests / #c:barrels / explicit ids), never into hoppers / chutes / funnels / belts - they
  may be the input of the same machine and a rejected item jams them; read the target with `javap` over the full classpath
  (in the DeceasedCraft port: `_port/tools/jp.py <class>`, `--find <part>`, `--decompile <class>`) instead of guessing
  descriptors.
- Server stop that never ends, MC 1.21.1 code (NeoForge 21.1.250; newer builds not checked; no Mojira match on 2026-10-15): at
  stop `ChunkMap.processUnloads` runs with `hasMoreTime = () -> true`, and a `scheduleUnload` callback whose chunk holder still
  has generation running puts itself back into `unloadQueue`, while that generation waits for the main thread. Seen in
  Space Journey 2026-10-16 when the player left a place before its chunks finished generating (teleports, dimension changes,
  the mod's own load tickets) and quit within seconds. Player workaround: wait a few seconds before quitting. Mod fix: a mixin
  that lets one `processUnloads` call poll at most as many entries as the queue held at its start (`@WrapOperation` on
  `Queue.poll`): stop > 180 s without it, "All dimensions are saved" after 11 s with it (tested once).

## 5. Config levers (verified mod facts)
- In Control 10.3.0 spawner (`spawner.json`, bytecode): every mob of a rule's `mob` list is tried separately with
  chance persecond x weight / sum of weights (no weights: 1 / list size); each try makes `attempts` position tries;
  `maxlocal` walks ALL entities of the level per attempt (O(entities x attempts)); spots are a random column within
  `maxdist` (3D) and a random height scanned down to a floor - use `minverticaldist` / `maxverticaldist` in caves.
  `spawn.json`: every spawn walks the rules - put `mob` / `dimension` filters in each rule, deny early. A phase like
  "day 0-1 deny" explains lag that starts on day 2.
- Enhanced AI (4.x): compare with the original pack's module set; per-mob modules (Pathfinding, Climbing, Custom /
  Better nearby targeting, Teleport to target, Miner, Pick up and throw, Riding, Parkour) multiply AI cost with mob
  count; Leaders adds banner mobs with x4 health; miner / climber / target switch chances raise pathfinding cost.
  Porting a 2.6.8 config: modules map by name (Pets -> Snow Golems), tags moved from `tags/entity_types/<name>` to
  `tags/entity_type/mobs/...` (`allow_climbing` -> `mobs/can_climb`, `can_be_miner` -> `mobs/can_mine`,
  `allow_target_switch` -> `mobs/targeting/allow_target_switch`), 4.x-only features off for parity. Per-mob data
  (insanelib): key `<module ns>:<feature name lower case, spaces -> _>/<name>` stored in NeoForge persistent data
  (`NeoForgeData.enhancedai.miner_mobs.time_to_break_multiplier`), filled on join with applyIfAbsent; set it from KubeJS
  with the mod's own `EAIData.apply(mob, value)` (`Java.loadClass(...MinerMobs).TIME_TO_BREAK_MULTIPLIER`) in a TARGETED
  `EntityEvents.spawned(id, ...)` - not `entity.persistentData` (KubeJS's own tag) and not `mergeNbt` (save + load of
  the whole mob). In the DeceasedCraft port: generator `_port/tools/eai_port.py`, report `_port/reports/enhancedai.md`.
- Lost Souls `lostsouls-server.toml`: `minMobs` / `maxMobs`, `spawnMaxNearby` / `spawnMaxNearbyRadius`,
  `serverTickTimeout` (time budget per tick), `checkValidSpawn`; building `haunted` chances in the pack's building data.
- The Hordes (horde size, interval, data `config/hordes`).
- Vanilla: simulation distance (server load) vs render distance (client).

## 6. Performance mods for NeoForge 1.21.1 (checked 2026-10-08; re-check versions)
Try one at a time with a profile: Lithium (official NeoForge build; test Create Aeronautics / Sable ships, fallback
`mixin.entity.collisions=false`), Immersive Optimization (entity / block entity tick rate by distance and visibility;
blacklist mobs that must keep full AI), Let Me Despawn (+ Almanac; mobs with picked-up items despawn), Entity
Culling (client), ModernFix (keep `dynamic_resources` / `dynamic_entity_renderers` off with KubeJS / Connector /
GeckoLib), FerriteCore, ImmediatelyFast (client; test with Sodium 0.8), AllTheLeaks. Alternatives / low: ServerCore
(activation range - not together with Immersive Optimization), ScalableLux (not with Sable / Create Aeronautics: Sable 2.0.6
declares it incompatible in its mods.toml, checked 2026-10-23; Sable also refuses Sodium older than 0.8.12-alpha.2), Clumps,
BadOptimizations, Noisium.
Do not add: Async, Moonrise (crashes Sable), Radium / Canary / Starlight (replaced), Embeddium next to Sodium, Fabric
copies through Connector, Universal Optimization (switches collisions off, global spawn caps). MCreatorMemFix has
no 1.21.1 build and the 1.21.1 MCreator mods do not need it.

## 7. Report
MSPT mean / 95th and TPS before -> after, FPS before -> after, "Can't keep up" count per hour of play, spark top
frames (with the profile link), entity counts; what was changed (one change per test) and what is still an
assumption. Keep the profile links and findings in the project journal (see `project-journal`; in the DeceasedCraft port:
`_port/HANDOFF.md`), not in this skill.

## Project state is not kept here
Current profiles, measured numbers of one world and the order of steps belong in the project's journal and reports.
Read them before proposing a step, so as not to repeat one that is already done. In the DeceasedCraft port: `_port/reports/perf_plan.md`
(newest status at the top), `perf_spark_v*.md`, `perf_code_places.md`, `perf_mods.md`, `perf_kubejs_hotpaths.md`, and
`_port/HANDOFF.md` (Done / Queue).

## Паспорт
Создан: 2026-10 из этапа производительности порта DeceasedCraft на NeoForge 1.21.1 (профили spark, байткод модов); журнал порта -
`_port/skills-lab/` и `_port/HANDOFF.md` (в навык не входят).
Проверен: факты о модах - по байткоду и профилям порта на NeoForge 21.1.x, даты и версии в разделах (раздел 6 - 2026-10-08).
Пункты с пометкой Space Journey - в том проекте 2026-10-14..23 (NeoForge 21.1.250), зависание при остановке и правка - один повтор.
В журнале нет записи о прогоне навыка целиком в чистом контексте по схеме skill-forge (шаг 5).
Тест 2026-10-25 (шаг 5 skill-forge, исполнители Opus, судьи Sonnet): только правка S-14 (зависание при остановке), одна задача,
прежний текст : новый 2:9 и 3:9, новый лучше (прежний обвинил билет мода); S-33, S-34 и S-35 не тестировались.
Дополнено 2026-10-27 по проекту Sengoku Jidai World (NeoForge 21.1.264, C2ME, DH 3.3.3, Sengoku через Connector): TPS против MSPT,
ожидание чанка под игроком, `isLoaded`, глобальный реестр, паузы и цена рендера DH. Тест шага 5 (прежний текст : новый, исполнители
Sonnet, один слепой судья Sonnet): задача "полёт в новый мир, мод Frontier", 12:15.
Скрипты spark в `scripts/` с 2026-10-27 (spark_fetch, spark_summary из порта DeceasedCraft, spark_chains из Sengoku Jidai World): тест
шага 5 с двумя слепыми судьями, без скриптов : со скриптами 13:15 и 14:15 (точность та же, вдвое меньше вызовов и времени).
Правка 2026-10-27 (доля в профиле как потолок прибавки, тёплая вода без числа одного прогона, миксины в моды Connector): новая задача
"Chunky, мод Hearthfire" прежний : новый 11:14 и 11:14 (два слепых судьи Sonnet); повтор задачи Frontier против прежнего ответа
15:15 и 14:15 (не хуже). Открыто: числа проекта из примеров навыка уходят в ответы как ожидание (у всех вариантов).
Правка 2026-10-27, веха T18 (`getHeight` и ожидание чанка без конца, правка бороды с ценой кэша и условием copy-on-write,
`compileOnly` на jar Connector, оговорка о числах примеров): тест шага 5, исполнители и судьи Sonnet, по два слепых судьи,
прежний : новый - новые задачи Tidewatch 11:13 и 12:14 (на v5), Stonewright 13:16 и 14:16; повтор Ironwood 12:16 и 12:16,
Frontier 14:16 и 15:16. Три круга правки: первый вариант проиграл Frontier на балл (кэш без условия copy-on-write),
исполнители путали, какой чанк ждёт `getHeight`, и переносили приём с низом мира туда, где он не годится. Числа примеров
попадают в ответы реже, но попадают.
Границы: сборки без KubeJS и без большого числа мобов покрыты только разделами 1, 2, 4, 6; версии модов перепроверять.
История изменений: CHANGELOG.md в папке навыка (что, когда и почему).

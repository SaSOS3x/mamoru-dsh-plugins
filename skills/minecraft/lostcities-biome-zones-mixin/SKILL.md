---
name: "lostcities-biome-zones-mixin"
description: "Зоны биомов по правилу (пустошь каждые N блоков) миксином на источник биомов, NeoForge 1.21.1; полоса без городов на границе стилей Lost Cities, офлайн-доказательство миксина, диапазоны зависимостей, C2ME. Триггеры: «зоны биомов», «пустошь каждые 10000 блоков», «город на границе биомов», «город другого стиля в пустоши», «миксин не сработал», «мир крашится при генерации», 'mod only supports lostcities', MultiNoiseBiomeSource, TerraBlender / Biolith."
---

# Biome zones + Lost Cities border strip (NeoForge 1.21.1)

Verified 2026-10-07 on NeoForge 21.1.250, Lost Cities 8.4.4, Biomes O' Plenty 21.1.0.14, TerraBlender 4.1.0.8,
Quark 4.1 (Biolith 3.0.10 jar-in-jar), C2ME 0.4.0-alpha.0.120. Re-check version numbers before trusting a line on another build.
TerraBlender regions cannot give "a zone every N blocks": they are weighted patches, so the zones are placed by a mixin on the biome source.

Reference implementation (example, it exists only on the author's PC): in the DeceasedCraft port it is `game/_port/tools/terrain/`
(`mod/src/.../WastelandZones.java`, `ZoneBiomes.java`, `BiomeHook.java`, `mixin/*`, `verify/run_all.sh`), design report `_port/reports/terrain.md`.
Where this skill says `verify/...`, `ZoneTest`, `MainAll` etc. it means that harness. Outside the port those files are not available:
write equivalents from the step descriptions (each is a small Java / python file) - do not assume a path exists.

Platform (checked on the author's Windows 11 PC, 2026-10-12): the `.sh` steps below are bash (a harness script for the user to run in Git Bash,
not a DSH command); write scripts longer than 5 lines to a file and run the file (quotes and backslashes break inline); give python / java
`C:/...` paths, not `/c/...`; Java classpath separator is `;` on Windows (`:` on Linux, so a colon-joined classpath copied from a Linux example
fails); pass long classpaths through an `@argfile`; `unzip` exists, `zip` does not.

## Why styles mix (Lost Cities, from the code)
- The STYLE of a city = biome at the city CENTRE (`WorldStyle.getRandomCityStyle` -> `BiomeInfo.getMainBiome`).
- Whether a chunk is a city chunk is decided PER CHUNK: `City.getCityFactor` x `WorldStyle.getCityChanceMultiplier(IDimensionInfo, ChunkCoord)` (the chunk's own biome, e.g. x10 on a tag).
- City radius 120..240 blocks (profile `cityMinRadius` / `cityMaxRadius`): a city centred on one side of a biome border covers chunks on the other side -> modern hospital in a wasteland, wasteland houses in a modern city.
- Cure: a city-free strip around the border at least as wide as the biggest city radius (or biome borders that never cross a city).

## Zone model (pure function of seed, x, z)
- Defaults of the port's `WastelandZones` (all are config values): square cells of `spacing` (5000) with a corner at the origin; one zone per cell: centre jitter +-0.30 cell, radius r (1500, capped at spacing / 3) x (1 +- 0.25), edge wobble 0.20 by one smoothstep value-noise octave (lambda 1800); a zone that could reach closer than 2500 to the origin is dropped (spawn). Seed: `ServerAboutToStartEvent` -> `getServer().getWorldData().worldGenOptions().seed()`; clear on `ServerStoppedEvent`; cache per cell in a `ConcurrentHashMap` (worker threads!).
- Signed depth `(R(p) - d) / L` with `L = 1 + wobble * rmax * 3*sqrt(2) / lambda` (gradient bound of smoothstep value noise) is 1-LIPSCHITZ: |depth(p) - depth(q)| <= |p - q|. So every point within 240 blocks of the border has |depth| <= 240; strip = |depth| <= 256 contains every such point -> no city (radius <= 240) can cover valid chunks on both sides. Sentinels DEEP / FAR for points far from every zone. Neighbourhood = `cellReach` cells around the point, NOT a fixed 3x3: a zone `dx` cells away has its centre >= (dx - 0.5 - jitter) x spacing away and matters when its outer edge + the strip window `L x stripHalf + 8` reaches the point; 1 (3x3) at the defaults, 2 for a very wide strip. Test the pruned depth against a brute-force depth over a big window (a fixed 3x3 gave 145 wrong points in 120 000 at strip 5000).
- Cost of the guarantee: strip width = 2 x half x L. With the defaults above (spacing 5000, radius 1500) L = 1.88, width 965 blocks. At spacing 10000 / radius 2000 L = 2.18 (formula 1116 blocks; measured along rays across zone edges: min 670, median 1100, p90 1340). Narrower: lower the wobble (0.10 -> L 1.44 -> 738 wide); half-width below the max city radius loses the guarantee. At spacing 5000 / radius 1500 the plane is 13.8% wasteland WITH cities, 34.7% city-free strip, 51.5% modern; wobble 0.10 gives 16.7 / 26.9 / 56.4 - tell the user, a third of the world without cities surprises people.
- Honest numbers (spacing 5000, radius 1500): 28.9% of the plane inside zones, nearest edge 2748..6870 from the origin (median 3276), a straight walk enters a zone 1.21 times per 10000 blocks (one zone per ~8300 blocks). With 10000 / 2000: 12.9%, 0.42 per 10000 (one per 24000). "Every N blocks" means the grid spacing, say so; radius / spacing decide how often a walker meets a zone.

## Mixins
- Biomes: `@Mixin(value = MultiNoiseBiomeSource.class, priority = 100)` extends `BiomeSource`; `@Inject(method = "getNoiseBiome(IIILnet/minecraft/world/level/biome/Climate$Sampler;)Lnet/minecraft/core/Holder;", at = @At("HEAD"), cancellable = true)`.
  - NEVER `@At("RETURN")` on this method in a modded pack: Biolith (jar-in-jar of Quark 4.1, `MixinMultiNoiseBiomeSource`, HEAD, cancellable, priority 900) and TerraBlender (HEAD, cancellable, 1000) always set the return value at HEAD, so every RETURN injector is dead code (a RETURN version was tested in the game and did nothing).
  - Lower priority = applied first = its handler is called first. The HEAD handler re-enters the method under a per-thread, per-source guard (port class `BiomeHook`: `ThreadLocal<Object[]>`, `inside(this)` -> return, `enter(this)` / `leave(prev)` in try/finally), gets the answer of all the other mods, transforms it and cancels with that value.
  - Coordinates are QUARTS: block = (q << 2) + 2. Per-instance `@Unique volatile` fields with lazily resolved plains / wasteland / steppe holders taken from `possibleBiomes()` (feature order stays valid); resolve returns null for sources without plains + the target biome (Nether, End, other dimensions) -> untouched. Log once per biome source whether the zones are ACTIVE or not used (synchronized WeakHashMap) - that line is how the game proves the hook runs.
- Classification: keep oceans / rivers / beaches (tags + name parts), mushroom fields, caves; open land (plains, meadow, savanna, desert, badlands, tundra ...) -> `wasteland_steppe`, everything else on land -> `wasteland`; outside zones the natural BOP wasteland -> plains (so no wasteland outside). Example from the DeceasedCraft port: another mod's biome that must not appear near the spawn (Zombie Extreme `scorched_earth`) -> plains within the spawn exclusion, in the same hook. Cache the class per holder only when `holder.tags()` is bound.
- Cities: `@Pseudo @Mixin(targets = "mcjty.lostcities.worldgen.lost.cityassets.WorldStyle", remap = false)`, `@Inject(method = "getCityChanceMultiplier(Lmcjty/lostcities/worldgen/IDimensionInfo;Lmcjty/lostcities/varia/ChunkCoord;)F", at = @At("RETURN"), cancellable = true, remap = false)` (nobody cancels this one at HEAD - checked); return 0.0F when `provider.getType() == Level.OVERWORLD` and the chunk centre `(chunkX << 4) + 8` is in the strip. Mod dependency `lostcities` optional, `ordering = "AFTER"`, `versionRange = "[1.21-8.4,)"` (see Dependency ranges). Mixin config in `neoforge.mods.toml` `[[mixins]]`, `required: true`, `defaultRequire: 1`, `compatibilityLevel JAVA_21`, javac `-proc:none` (no refmap on Mojang names).
- Several mods mix into the same method: handler names differ (`handler$zzc000$...`, `handler$zzh000$...`); prove the ORDER with all of them applied (verify step 2c), not by reading one mod.

## Switching off another mod's ores / features
- A NeoForge biome modifier `{"type": "neoforge:none"}` at the same path (`data/<modid>/neoforge/biome_modifier/<name>.json`) in a jar that loads AFTER the owning mod (`ordering = "AFTER"`, optional dependency) replaces it. Check the path list against the mod jar with a script (port: `verify/ze_ores_check.py`, Zombie Extreme ores), and check first that the pack does not use the products before removing generation (in the port the beta pack had removed their recipes).

## Dependency ranges (a hard error at the mod loading screen, learned 2026-10-07)
- An unsatisfied `versionRange` stops the game even for `type = "optional"`: "Mod X only supports lostcities 8.4 or above" / `ModSorter: Unsupported installed optional dependencies ... Expected range: '[8.4,)', Actual version: '1.21-8.4.4'`. Lost Cities calls itself `1.21-8.4.4`; Maven order puts that BELOW 8.4, so `[8.4,)` fails and `[1.21-8.4,)` passes (also 1.21-8.5.0, 1.21-8.10.0; rejects 1.21-8.3.9). Other version strings seen in the same pack (2026-10): `2101.7.2-build.377`, `1.1.8-hotfix-r6`, `0.5.2-neoforge-1.21.1-HOTFIX`.
- Never guess a range: run `verify/dep_check.py <mod jar> <game folder>` (reads the jar's `neoforge.mods.toml`, takes the installed versions from the mods' toml / manifest `${file.jarVersion}` and `libraries/`, tests each pair with the game's own `maven-artifact` jar via `VerCheck.java`; its self test shows `[8.4,)` vs `1.21-8.4.4` fails). The mixin harness and ASM verifier do NOT catch this: they never run FML's dependency check. If the mod only looks things up by id after registration, leave the dependency out entirely.
- If the cause was your own jar, tell the user plainly ("the mod is not outdated, nothing to download"), fix the jar and install it.

## Verify offline (no Minecraft): port harness `verify/run_all.sh`, `GAME=<game folder>` (both bash)
0. `dep_check.py` on the built jar (step 0b of `run_all.sh`).
1. Pure maths `ZoneTest`: coverage per seed, distance origin -> nearest zone, Lipschitz over 1.7 M point pairs, strip guarantee over 7.9 M (centre, chunk) pairs, 8 threads on a shared cache, pruned depth vs exact depth for 6 settings. `StripWidth`: strip width along rays. Run time ~4 minutes: start `run_all.sh` in the background (`nohup ... &`, bash) and poll the log.
2. Real Mixin library (`mixin-noservices.jar` = the game's `sponge-mixin` jar without `META-INF/services/*`) + a test `IMixinService`; `MainAll -Dcfg=a.mixins.json,b.mixins.json <out> <target classes> <NeoForge client jar> <srg client jar> <universal jar> <logging> <slf4j> <mod jars...>`: the first jar containing a class wins, so the NeoForge-patched client jar goes first -> "transformed ... changed: true", "all mixins applied" (an `InvalidMixinException` here = the game would not start).
2c. Every mod that hooks the method together: Biolith extracted from Quark (`META-INF/jarjar/biolith-*.jar`) + MixinExtras from the NeoForge universal jar-in-jar + TerraBlender + your other mixin jars + all libraries except sponge-mixin; `handler_order.py` parses `javap -c` of the result (regex `Method (handler\$[\w$]+)` - `\w+` stops at `$`) and requires your handler to be called FIRST.
3. ASM verifier (`Verify`): libraries passed as SEPARATE arguments (one colon-joined argument fails), NeoForge client + universal jars first (else `NoClassDefFoundError IHolderExtension`), every transformed class and every class of the mod.
4. E2E: run the transformed `MultiNoiseBiomeSource` on the vanilla srg jar WITHOUT NeoForge jars (NeoForge's FeatureFlagLoader NPEs without a loading mod list), child-first class loader, `SharedConstants.tryDetectVersion(); Bootstrap.bootStrap();` then restore `System.out` (Bootstrap wraps it), stub `<client jar>/assets/minecraft/lang/en_us.json` = `{}` (or the client `-extra.jar`); fake biome list + `Climate.Sampler` constants; assert the biome per case (zone centre, outside, ocean, Nether-like source, zones off, 8 threads).
4b. The E2E again with TerraBlender's cancelling HEAD handler applied: a RETURN jar must FAIL here (it reproduced the game), the HEAD + re-entry jar must pass.
5. State plainly what only the game can show: mod loads, the ACTIVE log line per biome source, real shapes, cities at the strip, interplay with other biome mods.

## C2ME (multithreaded chunks) - what to check before installing
- `c2me-neoforge-mc1.21.1-0.4.0-alpha.0.120.jar` bundles 19 modules (jar-in-jar); needs only minecraft; `dynview` / `betterchunkloading` discouraged. `config/c2me.toml` = `"default"` strings; a real value is a TOML literal (`false`); `-Dc2me.base.config.override.<key>=...` overrides without editing.
- `fixes.enforceSafeWorldRandomAccess` (default true = hard crash when a mod uses the world random from a worker thread; false = warning in the log). For a 100-mod pack start with false, search `latest.log` for "random" / "multiple threads", then decide.
- Read the mixin targets in the jar (extract the nested jars with `tar -xf` or `Expand-Archive`, then `javap -v`): natives-math hits `Climate$ParameterList` / `BiomeManager.getBiome`, base adds accessors to `MultiNoiseBiomeSource`; density-function compiler compiles datapack functions (a density wrapper included). A `getNoiseBiome` HEAD injection does not collide (checked for the port's hook); the zone cache must be thread safe (worker threads).
- Alpha: never claim it works with the pack until the log shows it; if the game dies in chunk generation, delete the C2ME jar first. A "Can't keep up! Running 31890ms behind" during generation: C2ME is the first suspect.

## Checklist
1. Reproduce the cause in the code (centre vs per-chunk), do not guess.
2. Write the zone function as a pure, thread safe function; prove Lipschitz + strip numerically.
3. Hook at HEAD with re-entry; prove the handler order with every mod that touches the method.
4. Build, run the whole harness on the FINAL jar (incl. `dep_check.py`), and make sure the jar you tested is byte-identical (hash) to the one you ship.
5. Tell the user: NEW world, config keys, a command that finds the nearest zone (port: `/dczones`), the ACTIVE log line, the interpretation of "every N blocks", the strip width cost.

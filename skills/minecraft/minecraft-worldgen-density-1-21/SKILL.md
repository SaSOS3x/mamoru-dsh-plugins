---
name: "minecraft-worldgen-density-1-21"
description: "Рельеф Minecraft 1.21.1 (NeoForge): обёртки density functions (offset, erosion, jaggedness), noise_settings, регионы TerraBlender, подгонка высот под Lost Cities, замер высот офлайн кодом игры. Триггеры: «слишком гористо», «сделай рельеф ровнее», «меньше гор», «города не влезают в рельеф», «больше такого-то биома», «высота земли», density function, noise settings, «замерь без запуска игры»."
---

# Terrain in Minecraft 1.21.1 (NeoForge): density functions, noise settings, TerraBlender, Lost Cities

Use for: flatter / hillier land, fewer mountains, more of one biome, "cities do not fit the terrain", reading `noise_settings`.
Verified 2026-10-06 on 1.21.1 / NeoForge 21.1.250 / TerraBlender 4.1.0.8 / BOP 21.1.0.14 / Lost Cities 8.4.4. Re-check version numbers on another build.
Tested 2026-10-25 (skill-forge step 5, Opus executors, Sonnet judges): only the S-37 passage (checking the noise map against real chunks), one task,
previous text : this text 4:9 and 3:9, this text better; `references/router-java.md` (S-36) was not tested.
Reference implementation (example, it exists only on the author's PC): the DeceasedCraft port keeps its tools in `game/_port/tools/terrain/`
(`terrain_gen.py`, `build_terrain.py`, `harness/run.sh`) and its design and measured results in `_port/reports/terrain.md`. Outside the port write
equivalents from the steps below; do not assume those paths exist.

Platform (checked on the author's Windows 11 PC, 2026-10-12): the `.sh` steps are bash (a harness script for the user, not a DSH command); scripts longer than 5 lines
go into a file, not inline (quotes and backslashes break inline); python / java get `C:/...` paths, not `/c/...`; Java classpath separator `;` on Windows
(`:` on Linux); long classpaths through an `@argfile` (command line limit ~32k chars).

## How the terrain is built (overworld)
- `data/<ns>/worldgen/{noise,density_function,noise_settings}/...`. `noise_settings/overworld.json`: `noise` {min_y -64, height 384, size_horizontal 1, size_vertical 2},
  `sea_level` 63, `noise_router` with 15 entries (barrier, fluid_level_floodedness, fluid_level_spread, lava, temperature, vegetation, continents,
  erosion, depth, ridges, initial_density_without_jaggedness, final_density, vein_toggle, vein_ridged, vein_gap) that reference named functions.
- `minecraft:overworld/continents`, `erosion`, `ridges` = `flat_cache(shifted_noise)`; `ridges_folded` = -3*(|(|ridges|)-2/3| - 1/3).
- `overworld/offset` = flat_cache(cache_2d(blend + (-0.50375 + SPLINE(continents -> erosion -> ridges_folded)) * blend_alpha)); leaves s run -0.3 .. 1.5.
  `overworld/factor`, `overworld/jaggedness` = splines of the same three inputs. `overworld/depth` = y_clamped_gradient(y -64..320, 1.5..-1.5) + offset.
  `overworld/sloped_cheese` = 4*quarter_negative((depth + jaggedness*half_negative(jagged noise))*factor) + base_3d_noise.
- **Surface height ~ 63.5 + 128 * s** (s = spline value without the -0.50375; 3D noise ignored). s = 0 sea level, 0.285 -> y 100, 0.4 -> y 115, 1.0 -> y 191.
- The BIOME SOURCE reads the same `continents` / `erosion` / `ridges` / `depth`: changing them moves biomes together with the terrain (good: no snowy peak biome on a flat hill).
  Climate parameter classes: continentalness mushroom <-1.05, deep ocean <-0.455, ocean <-0.19, coast <-0.11, near-inland <0.03, mid-inland <0.3, far-inland;
  erosion index 0..6 at -0.78 / -0.375 / -0.2225 / 0.05 / 0.45 / 0.55; temperature index 4 (desert row) only above 0.55, humidity/temperature are continental-scale noises (a 6000 block window can be 2% or 12% hot).
- Vanilla seed statistics (measured on only 2 seeds, chunk corners - indicative, re-measure for your seed): ~25-29% ocean (continentalness < -0.19); land chunks above y 115: 7-9%; erosion idx 1: median 103, 35% above 115; idx 3: median 70, 7% above 115; idx 4: median 67, p90 79.

## Changing it: WRAP, do not copy-edit
1. Put the exact vanilla JSON under your namespace: `data/<modid>/worldgen/density_function/offset_raw.json`.
2. Override `data/minecraft/worldgen/density_function/overworld/offset.json` with a wrapper that references `<modid>:offset_raw` (a function cannot reference itself under the same id).
   - compress land above O by k: `min(o, O + k*(o - O))` = `min(raw, add(mul(k, raw), O*(1-k)))`, with `O = (y - 63.5)/128 - 0.50375` for the surface height y where compression starts.
   - raise the low tail (fewer hills): `max(e, T + k*(e - T))` on erosion; scale: `mul(0.4, raw_jaggedness)`; shift: `clamp(add(raw, b), -1.2, 1.2)` on continents (b>0 = less ocean).
   - keep the vanilla `flat_cache` / `cache_2d` markers around the wrapper.
3. Ship in a mod jar (`data/` above vanilla) or `kubejs/data/` (above mods). Another worldgen mod overriding the same function wins by load order: `unzip -l` every jar for `worldgen/density_function`.
4. Existing chunks never change: **new world** (an old/new border has cliffs). A JSON error = "Failed to load registries" at world load: test with the offline harness below.
- `overworld_large_biomes/*` and `amplified` use their own functions; the default world type uses `overworld/*`.
- Example, the DeceasedCraft port's measured result of this recipe (erosion + offset + jaggedness wrappers, 2 seeds): in `_port/reports/terrain.md`.
- Rewriting the router in Java (noise coordinates remapped for a custom world geometry, a `NoiseBasedChunkGenerator`
  subclass): read `references/router-java.md` first.

## Measure offline (no Minecraft needed; any machine with JDK 21)
- Classpath from the instance `libraries/`: `client-1.21.1-*-srg.jar` (official names, no assets), datafixerupper, guava, failureaccess, brigadier, gson, slf4j-api, logging, fastutil, commons-lang3, joml, netty-*, authlib, icu4j, oshi-core, log4j-api/core/slf4j2-impl (the binding: otherwise registry errors are swallowed by the NOP logger and you only see an empty "Exception in thread main").
  Stub `<client jar>/assets/minecraft/lang/en_us.json` containing `{}` on the classpath (Bootstrap reads it).
- Vanilla JSON of the game's own code: `SharedConstants.tryDetectVersion(); Bootstrap.bootStrap(); new RegistriesDatapackGenerator(new PackOutput(dir), CompletableFuture.completedFuture(VanillaRegistries.createLookup())).run(CachedOutput.NO_CACHE).join();` (6 s, 6 MB).
- Load packs like the game: `new MultiPackResourceManager(PackType.SERVER_DATA, List.of(new PathPackResources(new PackLocationInfo(id, Component.literal(id), PackSource.BUILT_IN, Optional.empty()), dir) ...))` (later wins),
  `RegistryDataLoader.load(rm, RegistryAccess.fromRegistryOfRegistries(BuiltInRegistries.REGISTRY), [NOISE, DENSITY_FUNCTION, NOISE_SETTINGS filtered from RegistryDataLoader.WORLDGEN_REGISTRIES])`,
  `RandomState.create(settings.value(), access.lookupOrThrow(Registries.NOISE), seed)`, `new NoiseBasedChunkGenerator(anonymous BiomeSource, settings).getBaseHeight(x, z, Heightmap.Types.OCEAN_FLOOR_WG, levelHeightAccessor(384, minY -64), rs)`; `rs.sampler().sample(qx, qy, qz)` gives the climate target point.
- Speed (measured on a 2-core cloud machine): ~13 ms per getBaseHeight, so 4 corners x 4000 chunks ~ 1 min. Compare variants on the same seeds (2+), report: share of land chunks with a corner above the city limit, share fully inside the window, height percentiles, erosion index shares.
- Against real chunks of a generated world: compare with the `MOTION_BLOCKING_NO_LEAVES` heightmap. `WORLD_SURFACE` counts
  leaves and grass, and frozen-sea ice is not land: they gave false 47 % and 81 % in a first check. Later stages (trees,
  icebergs, ice, canyons) are not in the noise, so a good match is exact height about 90-97 %, water 98-100 %, biome 100 %
  (Space Journey's own generators, 4 worlds, 2026-10-15..19). Sample 16 columns in each of about 25 chunks, not 400 separate
  chunks: every far chunk generates its whole neighbourhood (400 did not finish in 10 min).
- Speed in the game (desktop PC, one thread, 2026-10-19, an Exotic Worlds world): getBaseHeight(OCEAN_FLOOR_WG) 4.4 ms per
  column, a biome alone (`ServerLevel.getUncachedNoiseBiome`) 0.02 ms: for a detailed map take dense biomes over sparse
  interpolated heights.
- TerraBlender classes use an access widener at runtime (`OverworldBiomeBuilder.addBiomes` protected): outside the game patch the class with ASM (make it public) and put it first on the classpath.

## TerraBlender regions (more of a biome)
- A `Region(ResourceLocation, RegionType.OVERWORLD, weight)` registered with `Regions.register` in `FMLCommonSetupEvent.enqueueWork` covers the world by weight (TerraBlender config keys `vanilla_overworld_region_weight` (10) and `overworld_region_size`; BOP primary 10 / secondary 8 / rare 2).
  Registering a region changes the region indices: new world.
- `addModifiedVanillaOverworldBiomes(mapper, b -> b.replaceBiome(from, to))` = the vanilla layout (7593 points) with biomes replaced; oceans, rivers, beaches keep working. Use `registry.containsKey(target)` first; register the region only if the other mod is loaded.
- BOP tables: `BOPSecondaryOverworldBiomeBuilder` MIDDLE_BIOMES row 4 (hottest) = wasteland, VARIANT row 4 / PLATEAU = wasteland_steppe; BOP config `config/biomesoplenty/generation.toml` keys `overworld.bop_primary_overworld_region_weight` (10), `bop_secondary_overworld_region_weight` (8), `bop_overworld_rare_region_weight` (2).
- Check a region offline: call `region.addBiomes(proxy Registry, list::add)` and run `new Climate.ParameterList<>(points).findValue(target)` over sampled climate points: biome shares of the region.
- A mod needs: `modLoader="javafml"`, `@Mod` constructor `(IEventBus, ModContainer)`, `container.registerConfig(ModConfig.Type.COMMON, spec, "x-common.toml")`, dependency on `terrablender` with `ordering="AFTER"`, `pack.mcmeta` pack_format 48.

## Lost Cities 8.x and the terrain
- `City.getCityFactor`: perlin city map (`cityPerlinScale`, `cityPerlinInnerScale`, `cityPerlinOffset`), plus the city radius bonus, then **height gate**: `ChunkHeightmap.getHeight()` < profile `cityMinHeight` or > `cityMaxHeight` -> 0; only then the world style's biome multiplier (`WorldStyle.getCityChanceMultiplier`, e.g. x10 on a biome tag) multiplies the factor; a chunk is a city above `cityThreshold`.
- `ChunkHeightmap.calculateAccurateHeight` samples `ChunkGenerator.getBaseHeight(OCEAN_FLOOR_WG)` at chunk offsets (2,2) (2,14) (14,2) (14,14): oceans / deep rivers (< min) and mountains (> max) are never city chunks. Cities are a feature on the normal overworld (no own noise settings), so density-function changes apply to them.
- Align terrain and profile: compare the profile's height window and groundLevel with the (compressed) land height, count the share of land inside; water (25-29% ocean) is a separate loss of city area. Example, the DeceasedCraft port (profile `deceasedcraft_largecities`): window 60..115, groundLevel 71, 92.6-94.0% of land chunks inside after compression (2 seeds; the earlier "~95%" in this skill was rounded up); details in `_port/reports/terrain.md`.

## Checklist
1. Measure vanilla first (2 seeds), decide the target (share inside the window), change one wrapper at a time.
2. Load the final jar data through `RegistryDataLoader` and compare heights with the generator output (compare the CSV files, e.g. `Compare-Object` in PowerShell).
3. State what is not verified: the mod loads in the game, the real Lost Cities result, other mods overriding the same functions.
4. Tell the user: NEW world; where the weights / parameters are; how to read the log line of the mod.

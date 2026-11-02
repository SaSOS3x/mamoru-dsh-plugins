# Project state moved out of the skills (v33, 2026-10-12)

Proposed by the skill-quality-v33 workflow (4 Sonnet agents). Each passage left a skill because it is project progress /
status, not method. Kept here verbatim with the target where it belongs; most targets already hold the same facts.

## lostcities-biome-zones-mixin
- Line 20 history '(5000; the first version used 10000)': dropped '; the first version used 10000' -> target HANDOFF.md 'Done' section of the terrain/zones step (or reports/terrain.md). Text: 'Zone spacing: first version used 10000, current default 5000.'
- Line 27 history '(terrain 0.2.0/0.2.1 did nothing in the game: natural wasteland patches near the spawn, hospitals in wastelands)' replaced by '(a RETURN version was tested in the game and did nothing)' -> target reports/terrain.md, history part. Text: 'terrain 0.2.0/0.2.1 used @At(RETURN) on getNoiseBiome and did nothing in the game: natural wasteland patches near the spawn, hospitals in wastelands. Fixed by HEAD + re-entry in 0.2.2.'

Kept in the skill (unsure whether method or state):
- Line 8 'Verified ... 2026-10-07 (terrain 0.2.2)' and version list: kept as validity stamp.
- Line 30 'Zombie Extreme scorched_earth -> plains within spawn exclusion': project-specific decision, kept as an example of the method.
- Line 35 'check first that the beta pack did not use the products (it removed the recipes)': kept.
- Line 22-23 numbers (13.8/34.7/51.5 %, 28.9 % etc.): measured properties of the chosen parameters, kept.
- Line 38 'Other versions in the same pack: ...': kept as verified version-string examples.

Contradictions found:
- None (no reference files). Minor: step 'terrain 0.2.2' stamp vs the CLAUDE.md note that zones live in deceasedcraft-terrain-0.1.0.jar file name - not a contradiction, file name is fixed by design.

## minecraft-worldgen-density-1-21
- Line 35 'Measured result of erosion T -0.10 k 0.5 + offset y 100 k 0.45 + jaggedness x0.4: land chunks above 115 from 9.4% / 7.0% to 2.1% / 2.0%, p99 150 -> 114, max 208 -> 132, no mountain biomes removed (idx 1 10.8% -> 2.9%)' replaced by a pointer -> target _port/reports/terrain.md, section with measured results. Text to put there verbatim: 'Measured result of erosion T -0.10 k 0.5 + offset y 100 k 0.45 + jaggedness x0.4: land chunks above 115 from 9.4% / 7.0% to 2.1% / 2.0%, p99 150 -> 114, max 208 -> 132, no mountain biomes removed (idx 1 10.8% -> 2.9%).'
- Line 58 'window of the profile (here 60..115, groundLevel 71) ... (here ~95% of land inside)' generalised in the skill -> target _port/reports/terrain.md. Text: 'DeceasedCraft profile: height window 60..115, groundLevel 71; after compression ~95% of land chunks inside the window.'

Kept in the skill (unsure whether method or state):
- Lines 24 'Vanilla seed statistics (2 seeds ...)': measured vanilla facts, kept.
- Line 9 stamp 2026-10-06 and versions: kept as validity stamp.
- Line 51-53 BOP weights (10/8/2) and config keys: verified mod facts, kept.

Contradictions found:
- None (no reference files). Check: the pointer to _port/reports/terrain.md assumes that report holds or will receive the moved text; if it does not, the user must add it there.

## tps-optimization-neoforge
- Section 'Known in this pack' (5 bullets, old lines 168-182) removed from SKILL.md and replaced by a 3-line pointer section 'Project state is not kept here' (perf_plan.md, perf_spark_v*.md, perf_code_places.md, perf_mods.md, perf_kubejs_hotpaths.md, HANDOFF.md). Per bullet:
- (a) 2026-10-05 '~2 s stalls after You've entered a horde building (Lost Souls)': target _port/reports/perf_plan.md, section 'Hitches / open items'; text: '2026-10-05 test log: ~2 s stalls right after "You've entered a horde building!" (Lost Souls horde spawn); profile with --only-ticks-over 100 while entering one.' (Likely already covered by perf_spark_v26-v29.md; check for duplicates before adding.)
- (b) Chunk generation ~1000 'Failed to create block entity create:fluid_pipe' stack traces per test, fixed in deceasedcraft-an 0.2.0 palette overrides: target HANDOFF.md newest Done section for that version (or Facts that cost time); text: 'Chunk generation produced ~1000 "Failed to create block entity create:fluid_pipe" traces per test (pipe/pump/RS cable block entity data in Lost Cities palettes); fixed in deceasedcraft-an 0.2.0 (palette overrides).'
- (c) '/reload = ~6 s (expected); pause / world load spikes are not lag': NOT moved, it is method knowledge - merged into section 1 Logs line ('/reload takes ~6 s (expected)'); the pause/world-load part was already there.
- (d) 2026-10-08 (v24) 'port lacks ~30 performance mods the beta had; EAI config = 4.2.4 defaults while beta 2.6.8 had most modules off; In Control phase after_day1 lifts hostile deny on day 2; plan in perf_plan.md, perf_mods.md, perf_kubejs_hotpaths.md': target HANDOFF.md section 'Done (24)'/perf_plan.md header; text = the bullet verbatim. Generic version of the same lessons stays in Section 2 items 2-3 and Section 5.
- (e) 2026-10-08 (v25) first profiles, 8 performance mods installed, laboratory horde MSPT median 25-28 ms (p95 43-48), dense city + horde 16 ms, ~500-650 entities, heap ~4.5 of 8 GB, biggest costs (isCityCenter self 4-5%, GoalSelector 12% + PathFinder 9%, theheavy goal up to 4.5%, NaturalSpawner 4.4%, Sable getEntities ~2%, KubeJS ~3%, Serene Seasons ~1.7%), 2-2.6 s freezes after IE multiblock autoform / advancements / autosave, EAI = beta set from v25: target _port/reports/perf_spark_v25.md (already holds these numbers per CLAUDE.md) and HANDOFF.md 'Done (25)'; text = the bullet verbatim.

Kept in the skill (unsure whether method or state):
- Section 6 'Performance mods' (checked 2026-10-08, with do-not-add list): kept as dated verified recommendations, not as progress; it does not say what is installed. The ModernFix/Sable/Create Aeronautics remarks are port-specific.
- Section 5 'Config levers (DeceasedCraft port)' and the Lost Radar / Lost Cities / Undead Revamped items in section 4: kept (verified mod-bytecode facts with versions), but they are port-specific; some may already be fixed by deceasedcraft-fixes (0.11.0+). Not marked as fixed because the skill cannot know; could add 'fixed in fixes 0.11.0' stamp if the user wants.
- Section 4 'Mixin checklist (verified cases of the port, v32)': kept as method with a version stamp; mentions the spent-rod mixin review which is project history.

Contradictions found:
- Section 1 says read a spark profile by opening spark.lucko.me/<id>?raw=1&full=true in a browser (Cowork route); CLAUDE.md v26 says on this PC use spark_fetch.py + spark_summary.py (spark-usercontent.lucko.me). Fixed by naming spark_fetch.py first and keeping the browser route labelled Cowork.
- Section 'Related skills' says modpack-port-neoforge covers 'Cowork file flow' - Cowork-only, not rewritten per instruction.

## agent-delegation
- Nothing moved. The body is method; dated items are validity stamps of facts (token costs 60 thousand per empty agent, 20 percent errors found by reviewers, audit 2026-10-12 found 12 of 27 failure types unrecorded, table column 'Основание' with 'проверено: этап 1 v32') and the 'Паспорт' block required by skill-forge step 4. Kept as is.

Kept in the skill (unsure whether method or state):
- Section 6 sentence about the 2026-10-12 audit (12 of 27 types unrecorded) is evidence, not method; kept as a dated stamp. Could be moved to _port/skills-lab/agent-delegation/JOURNAL.md if the user wants a purer method text.
- Table column 'Основание' values such as 'проверено: 17 из 17 профилей', 'проверено: этап 1 v32' are project history used as evidence for model choice; kept.
- Section 1 numbers (60 thousand tokens entry cost, 0.15-0.6 million for real work) are Claude 5 / Claude Code figures per the Паспорт; kept with the stamp already in the Паспорт 'Границы'.

Contradictions found:
- Паспорт says 'Исполнение по навыку - см. журнал (этап 1 v31)' while the table and 'Изменения' refer to 'этап 1 v32'; likely a typo (v31 vs v32), not changed - user to confirm.
- Ловушки row 'Отчёт агента не появился' (Write may refuse a report file, result returns as text) is consistent with section 3 (schema answer) - no contradiction.

## kubejs-neoforge-2101
- Offline-test paragraph listed what the Rhino tests cover ('tests for the armor sets, recipes, tiers, day-0 script and wasteland air' for rhino_harness/armor; 'mocks of level / entity / events / commands for the horde HP script' for dchp/test). Removed from SKILL.md, keep paths and how-to there. Target: _port/HANDOFF.md, section 'Facts that cost time' (or the tools inventory), exact text to add: 'Rhino test runners in use: _port/tools/rhino_harness/armor (JsRun.java + prelude.js) tests the armor sets, recipes, tiers, day-0 script and wasteland air; _port/tools/dchp/test (JsRun2.java) has mocks of level / entity / events / commands for the horde HP script.'
- Added to SKILL.md (not moved out): one line with the Windows rule from CLAUDE.md 'Shell traps' for running the harness (Write tool into scratchpad, C:/ paths, ';' classpath).

Kept in the skill (unsure whether method or state):
- Frontmatter-like stamp 'Verified ... in Oct 2026' kept (validity stamp).
- 'Custom items, tools, shields (registered in game, Oct 2026)': 'blocking pose not yet confirmed in game' and 'JEI result not checked yet' are open items of the port (state) but also unverified-fact caveats; kept in place, candidates for HANDOFF Queue.
- 'Run code AFTER the other handlers ... (In Control onjoin) ... Offline-tested; confirm the order in game' and the EntityEvents.spawned entity.type note 'offline-tested, confirm in game': kept as unverified-fact stamps.
- 'Other events used here' list and the 'Lost Souls chest lock off on day 0' example in 'Mod configs from scripts': pack-specific examples, kept as illustrations.
- 'a /command died in game, 2026-10-06' kept as a dated evidence stamp.

Contradictions found:
- references/api-changes.md says 'findRecipes sees recipes added earlier in the same pass? Not verified'; SKILL.md states it sees datapack recipes only, not script-added ones. SKILL.md is the newer, firmer claim; kept, the unverified line is dropped with the file.
- api-changes.md Config section says only 'see neoforge-mod-configs' - consistent.

## neoforge-mod-configs
- None moved with confidence: the body is method plus verified, version-stamped facts.

Kept in the skill (unsure whether method or state):
- Section 'Making defaultconfigs/ the one place to edit (pattern used in this pack)' names the pack's own scripts (defaultconfigs_sync.js, defaultconfigs_loader.js, lists DC_MANAGED_CONFIGS / DC_SERVER_MANAGED / DC_CHECK). It is a reusable pattern, but also pack structure; kept. If the user wants it out: target _port/HANDOFF.md 'Facts that cost time', text = that section verbatim.
- Hordes bullet 'The 1.20.1 pack used an entity TAG ... port both into the new files': port-specific hint plus a verified default (zombie 0.75 x 0.75 = 56%/hit); kept.
- Lost Souls 'The beta uses true' for useChunkCheck: a fact about the beta pack with the date stamp 2026-10-08 v26; kept.
- 'Never ship a 1.20.1 file as-is ... config_port.py': workflow rule tied to this pack's tool; kept.

Contradictions found:
- mods.md vs SKILL.md on Lost Cities: mods.md says a non-empty COMMON profiles.dimensionsWithProfiles OVERRIDES the overworld profile over the Create World GUI/world/selectedProfile (so 'minecraft:overworld=<profile>' + Config.resetProfileCache() is the GUI-free default); SKILL.md says dimensionsWithProfiles only fills the cache and the overworld then follows GUI > world data > SERVER selectedProfile, so selectedProfile in lostcities-server.toml is the working default. I looked at the bytecode of Config.getProfileForDimension (lostcities-1.21-8.4.4.jar): the loop over dimensionsWithProfiles builds a map, then LostData/selected profile are consulted, but I did not finish tracing the precedence. Left SKILL.md as is; needs a decision/verification before either is trusted.
- mods.md labels Lost Souls '1.21-5.0.x' and Hordes '1.21-1.6.x' vs SKILL.md '5.0.1' / '1.21.1-1.6.3f'; SKILL.md is the precise one.

## modpack-port-neoforge
- 'Original pack settings still not ported (create, createbigcannons, immersiveengineering, parcool, securitycraft, solcarrot, sophisticatedbackpacks, lostradar, artifacts) - on request' -> already in HANDOFF Queue (item 6, 'Other original server configs (create, createbigcannons, IE, parcool, securitycraft, solcarrot, lostradar, artifacts)') and reports/tech_port_plan.md point 4 and beta_gap_v29.md. Only difference: sophisticatedbackpacks is missing in the Queue item; add to that Queue line: ', sophisticatedbackpacks (config/sophisticatedbackpacks-server.md exists in reports)'.
- Apocalypse Now history 'first replaced (TaCZ Armor + Zombie Extreme armor, ZE melee) since 2026-10-03/05 back under original apocalypsenow:* ids' -> HANDOFF Done 2026-10-03 (2), (5) and 2026-10-05 (12) already hold it. Skill keeps the current mechanism (KubeJS melee, deceasedcraft-armor, deceasedcraft-an, an_world.py) and a pointer to these sections. Text to add to HANDOFF 'Facts that cost time' only if the user wants it: 'Apocalypse Now: replaced by TaCZ/ZE gear on 2026-10-03, restored under the original ids 2026-10-03/05.'
- 'Hordes infection ... port still has the 1.21 mod default infection_entities.json ... Needs a data port (pending user decision)' -> DELETED, it is false now: HANDOFF Done 2026-10-02 says 'Hordes infection ported (config/hordes/data/hordes/infection/): 45 infecting mobs at chance 0.02, playerInfectionResistance 0.0, only villager conversion, no wearables, golden/enchanted apple immunity 120 s'. Nothing to add to HANDOFF, the entry already exists.

Kept in the skill (unsure whether method or state):
- 'Older chat deliverables (deceasedcraft-data-<ver>.jar, kubejs_2101.zip, ftbquests_1.21.1.zip, deceasedcraft_configs.zip) now go straight into game/' - Cowork-era history, kept.
- LSO 2.4.7 data-json lesson ends with 'fixed by a mixin in deceasedcraft-fixes 0.5.0' and the scorched_earth / LsoMalus lessons name the fixing classes - fact plus fix; kept as facts with fix pointers.
- 'defaultconfigs don't apply' lesson ends 'Fixed 2026-10-01 (startup re-seed + check script)' - history stamp, kept.
- Rotatable-tag lesson: 'convert.py should write the asphalt id into the data jar's own tag' - an open TODO, kept; if still open, belongs in HANDOFF Queue.
- Example numbers in Build pipeline (--version 0.2.2, DCTweaks_5.10.14, 'Test 0.2.2' world) - examples, kept.
- Toolchain table: every script exists in game/_port/tools (checked), but the old text said scripts/ = skill folder, which does not exist; I changed the header to _port/tools (checked 2026-10-12).

Contradictions found:
- SKILL.md 'Hordes infection ... still default' vs HANDOFF Done 2026-10-02 'Hordes infection ported': the skill passage was obsolete, removed.
- references/conversion-rules.md 'Apocalypse Now replacement' (TaCZ + Zombie Extreme armor, no base_layer... in loot) vs SKILL.md (ids restored via deceasedcraft-armor / -an since 2026-10-03/05): reference is obsolete.
- SKILL.md said scripts are in 'scripts/' of the skill; there is no scripts/ folder, scripts are in _port/tools (fixed).
- Minor: reference writes container key Count, SKILL.md writes count (1.21 components format uses count); SKILL.md kept.

## port-from-1182-pack
- 'Done so far: wastelands (2026-10-02) -> mods/deceasedcraft-wasteland-<ver>.jar ...; the Abyss (2026-10-07) -> mods/deceasedcraft-abyss-0.1.0.jar' -> HANDOFF already has 'Wastelands from 5.5.5 (done 2026-10-02, first test 2026-10-03)' and Done 2026-10-07 sections; add one line to HANDOFF 'Status': 'Ported from 5.5.5: wastelands (2026-10-02) -> mods/deceasedcraft-wasteland-<ver>.jar, tools _port/tools/wasteland/, report reports/wasteland.md; the Abyss (2026-10-07) -> mods/deceasedcraft-abyss-0.1.0.jar, tools _port/tools/abyss/, report reports/abyss.md; the laboratory dimension (2026-10-07, Done 23).' The skill keeps only the tool paths and report names as worked examples, pointing to HANDOFF Status.

Kept in the skill (unsure whether method or state):
- 'Mutationcraft and Alex's Mobs have no 1.21.1 version in the port' - availability fact with no date; kept (could be a dated stamp 'as of v25').
- 'Custom Portal API Reforged exists for NeoForge 1.21.1, but the session cannot download it ... a small own mod is enough' - mixes a Cowork-session limit with a decision/design; kept.
- 'FX Control is not in the port: do its effects in KubeJS (see wasteland_air.js)' - status plus guidance; kept.
- The laboratory dimension (Done 23) is not covered by the body; the description deliberately names only the Abyss as dimension example.

Contradictions found:
- None found (no references). Checked the skill against HANDOFF section names; no conflicting fact seen.

---
name: "neoforge-dev-experiments"
description: "Автотесты своего мода в dev-прогонах NeoForge 1.21.1 из Gradle (ModDevGradle): конфиг и папка на опыт, настройки папки до первого запуска, мир из кода, тур с RESULT PASS/FAIL, лимит на каждое ожидание, watchdog выхода, честные FPS/TPS. Триггеры: «dev-клиент из Gradle», «dev-сервер», «автотест», «тур», «опыт в игре», «поэтапно с тестами», runClient, «прогон висит», «зависло окно», «чёрный экран после выхода», «dev-сервер не закрылся», «замер в dev», Found unused register callbacks, Sodium в dev."
---

# Automated experiments in NeoForge 1.21.1 dev runs

An experiment here is an unattended run of your own mod from Gradle: a dev client or a dev server makes or opens a world, does
the steps, writes `RESULT PASS` or `RESULT FAIL <n>` and exits by itself. Rule: a run counts only when it loaded what it should,
ended by itself and wrote its RESULT. Anything else (did not load, hung, no RESULT) is "no result", not a FAIL of the mod.
Checked in one project (Space Journey, 2026-10-14..23): Minecraft 1.21.1, NeoForge 21.1.250 (FML 4.0.44), ModDevGradle 2.0.148,
Gradle 9.2.1, Java 21. Re-check names and versions on other builds. Related skills: `tps-optimization-neoforge` (hangs, equal
load), `neoforge-mod-configs` (Distant Horizons), `minecraft-worldgen-density-1-21` (a map against real chunks); `test-mutations` (can the check fail at all),
`agent-delegation` (limits on long runs), `project-journal` (the user and the game window).

## 1. A run config and a folder per experiment
```groovy
neoForge { runs {
    myCheck {                                   // Gradle task runMyCheck
        client()                                // a server check: server() and programArgument '--nogui'
        systemProperty 'mymod.experiment', 'my-check'
        gameDirectory = project.file('run-my-check')
    }
} }
```
- The mod registers the experiment's listeners only when `System.getProperty("mymod.experiment")` names it (client ones also
  behind `FMLEnvironment.dist.isClient()`): the normal game and the other runs never see them.
- `run-*/` goes into `.gitignore`; each folder has its own options.txt, config/, saves/ and logs/.
- A fresh world on every run: `def w = file('run-my-check/world')` at the top level of build.gradle, then
  `tasks.matching { it.name == 'runMyCheck' }.configureEach { doFirst { w.deleteDir() } }` (worked with the configuration cache
  on). A run that reuses another run's world (a pre-generated template) copies it only when that run's summary.txt contains
  `RESULT PASS`, and the template run deletes its old summary first: otherwise a half-made world passes.
- Gradle 9 fails the `test` task when src/test holds plain check programs and no JUnit tests:
  `tasks.named('test', Test) { failOnNoDiscoveredTests = false }`.

## 2. Prepare the folder before the first launch
A new folder starts from defaults: it is not in git and its files appear only on the first launch. Copy the files from a
checked folder and search them. Each setting below answers a failed or spoiled run; a Gradle task that writes them was not tried.

| File | Setting | Why |
|---|---|---|
| options.txt | `onboardAccessibility:false` | the accessibility onboarding screen of a fresh folder holds an unattended client |
| options.txt | `soundCategory_master:0.0`, `pauseOnLostFocus:false` | silence for the user; a window without focus pauses the game, and the paused integrated server stops ticking |
| options.txt | `enableVsync:false`, `maxFps:260` | FPS numbers are not cut by vsync or the 120 cap |
| server.properties | `max-tick-time=-1` | a check that spends minutes in one tick is killed by the vanilla watchdog after 60 s |
| config/fml.toml | `maxThreads = 1` | a cheap, unproven guess against the Registrate failure (Traps) |
| config/DistantHorizons.toml | `ignoredDimensionCsv` | only with DH in the dev run: `neoforge-mod-configs`, Distant Horizons block |

`Select-String -Path run-x/options.txt -Pattern '^(onboardAccessibility|soundCategory_master|pauseOnLostFocus|enableVsync|maxFps):'`, then
`Select-String -Path run-x/config/fml.toml -Pattern maxThreads` and `Select-String -Path run-x/server.properties -Pattern max-tick-time`.

## 3. Check what really loaded
A mod in the mods list is no proof: find a line of its own work in the log (or one from a mod that detects it) and write that
sign into the summary. The known case is Sodium 0.8.13 from the Modrinth maven: its jar is a wrapper (FML type LIBRARY, its own
mods.toml declaring `sodium`, the real Sodium in META-INF/jarjar). As a Gradle dependency FML keeps the wrapper as the mod
("dependency jar for JarJar which was passed in as source: sodium") and the renderer never loads: every dev client there before
the fix ran without Sodium. The nested jars alone fail with a ClassNotFoundException (`Workarounds$Reference`: Sodium's mixins use the
wrapper's classes); the wrapper without its mods.toml as a library fails too (the game layer does not see plain classpath jars).
What works (2026-10-15; the wrapper's early driver workarounds do not run this way):
```groovy
configurations { sodiumWrapper }
dependencies {
    sodiumWrapper "maven.modrinth:sodium:<version id>"
    localRuntime fileTree(layout.buildDirectory.dir('sodium-jarjar')) { exclude '*sodium-neoforge*' }.builtBy('unpackSodium')
    localRuntime files(layout.buildDirectory.file('sodium-dev/sodium-dev.jar')).builtBy('sodiumMod')
}
tasks.register('unpackSodium', Sync) {          // the nested jars
    from({ zipTree(configurations.sodiumWrapper.singleFile) }) { include 'META-INF/jarjar/*.jar'; eachFile { path = name } }
    includeEmptyDirs = false
    into layout.buildDirectory.dir('sodium-jarjar')
}
tasks.register('sodiumMod', Zip) {              // the Sodium mod jar plus the wrapper's own classes
    dependsOn 'unpackSodium'
    from({ zipTree(fileTree(layout.buildDirectory.dir('sodium-jarjar')).matching { include '*sodium-neoforge*' }.singleFile) })
    from({ zipTree(configurations.sodiumWrapper.singleFile) }) { exclude 'META-INF/**' }
    duplicatesStrategy = DuplicatesStrategy.EXCLUDE
    archiveFileName = 'sodium-dev.jar'
    destinationDirectory = layout.buildDirectory.dir('sodium-dev')
}
```
Signs that it loaded: the class `SodiumWorldRenderer` resolves; in that pack also Exotic Worlds' `sodium_present=true` and Sable's
"Using Sodium renderer mixins". Wrappers that declare no mod themselves (Exotic Worlds, Create Aeronautics) load fine, and in a
player's game folder FML unpacks the Sodium wrapper normally.

## 4. The world from code
`--quickPlaySingleplayer` opens only an existing world. A fresh one is made from code once the title screen is up:
```java
GameRules rules = new GameRules();
rules.getRule(GameRules.RULE_DOMOBSPAWNING).set(false, null);
mc.execute(() -> mc.createWorldOpenFlows().createFreshLevel(name,
        new LevelSettings(name, GameType.SURVIVAL, false, Difficulty.PEACEFUL, true, rules, WorldDataConfiguration.DEFAULT),
        new WorldOptions(seed, false, false), WorldPresets::createNormalWorldDimensions, new TitleScreen()));
```
An existing world (a copied template): `mc.createWorldOpenFlows().openWorld(folderName, onFail)`. Fix what makes two runs
differ, unless the check is about it: the seed, peaceful, noon with `RULE_DAYLIGHT` and `RULE_WEATHER_CYCLE` off,
`RULE_RANDOMTICKING` 0, no mob spawning (set on `server.getGameRules()` once the world is loaded).

## 5. The tour: steps that end by themselves
- Client tour: one listener on `RenderFrameEvent.Post` (NeoForge.EVENT_BUS). It fires on every frame from the title screen on,
  so one state machine drives the menus, the loading and the world: title screen -> create or open the world -> wait for
  `mc.level` and `mc.player` -> steps -> finish. Server check: `ServerStartedEvent`, the checks, the RESULT line in `finally`,
  then `server.halt(false)`.
- A limit on every wait, each with a FAIL line that names the step and the screen: world load 300 s, a measurement's warm-up
  120 s, the whole run 60 min (values that worked there). A wait without a limit looks like work: a warm-up waited 20 min for
  "all sections built", which never happens under Sodium (it builds only sections in the camera frustum, and
  `hasRenderedAllSections()` means only an empty build queue): wait for the columns in view.
- Modal screens are answered by the tour. A world made on a dedicated server with datapack dimensions opens "Worlds using
  Experimental Settings" (`BackupConfirmScreen`): press its button whose translation key is `selectWorld.backupJoinSkipButton`
  ("I know what I'm doing"). The onboarding screen is prevented by options.txt.
- One gate for every experiment, not `scenarioA || scenarioB` inside the client tour. Put
  `isExperimentEnabled()` over all scenario properties in the client class and register the same modal-screen
  handler for all of them. A third scenario (`perf`, `mob-sweep`, a new load test) that is added only to the server
  side will stop on the experimental-world screen, and the run has **no result**. Test the new property with the
  modal handler before measuring. If the screen is visible in an unattended run, fix the gate; do not click it by hand.
- One `finish()` that every exit goes through: write `<run folder>/<experiment>/summary.txt` (one line per check, the last one
  `RESULT PASS` or `RESULT FAIL <n>`), start the exit watchdog, `mc.stop()`. Numbers in `Locale.ROOT` (a decimal comma of a
  Russian locale spoiled a run). Put the event's time into the line itself: summary lines logged by `finish()` carry its time.
- The exit watchdog (a daemon thread started right before `mc.stop()`, 180 s limit there, then stacks and `Runtime.halt`) and the
  vanilla stop loop it caught: `tps-optimization-neoforge`, section 1 "A hang is not lag" and section 4 "Server stop that never
  ends". Without it a hung exit holds the Gradle task and the window for ever.

## 6. The player in a tour
- Survival with `mayfly`, not creative: in creative and spectator the server skips the "moved wrongly" check, so "0 moved
  wrongly" there proves nothing. Count the `ClientboundPlayerPositionPacket`s the server sends to the player: each one is a
  correction.
- Move the player from `ServerTickEvent.Post`, not from `PlayerTickEvent` (the move is put back); velocity then from
  `getKnownMovement()`. Fly over the terrain with the movement keys: a client `setPos` through blocks is refused.
- More server and client facts with their classes and dates: `references/vanilla-facts.md`. Read it before a check that
  compares the client with the server, follows chunks, light or entities, or casts the player's ray.

## 7. Check the run
- Three signs: Gradle `BUILD SUCCESSFUL`, exit code 0, a `RESULT` line in summary.txt. No RESULT is no result: read the output.
  Read the exit code right after the command (PowerShell `$LASTEXITCODE`, or `.ExitCode` of a `Start-Process -PassThru`):
  `cmd /c "gradlew ... > file"` hides it.
- Keep the Gradle output in a file: a bare `> file` writes UTF-16LE with BOM in 5.1 and `2>&1` on a native command throws
  NativeCommandError, so run `Start-Process .\gradlew.bat -ArgumentList runMyCheck -RedirectStandardOutput run-my-check\gradle-run.out -RedirectStandardError run-my-check\gradle-run.err -NoNewWindow -Wait -PassThru`
  and read `.ExitCode` (в DSH не проверено): exceptions of mod threads that nobody catches reach only stdout / stderr, not logs/latest.log.
- List the java processes after the run (Windows: `Get-CimInstance Win32_Process -Filter "Name='java.exe'"` with `ProcessId`
  and `CommandLine`) and stop the run's leftovers. MDG passes the JVM arguments in files `build/moddev/<run>RunVmArgs.txt` and
  `<run>RunProgramArgs.txt`, so the command line shows the run's name, not its folder: a script that looked for the folder left
  three dev servers running on one port (server.properties defaults to 25565). Limits and killing the process tree:
  `agent-delegation`, section 4.
- Real dev runs one at a time (a window, several GB of memory, the port), and tell the user before a window opens:
  `project-journal`, section «Человек в контуре».
- A run that did not load is no result: run it once more (Traps, Registrate). Whether the check can go red at all:
  `test-mutations`.

## 8. Honest numbers
- `Minecraft.disconnect` sets `level` to null only at its end: frames while leaving still show the old world (a "join" timed
  during the exit gave a false 19.6 s).
- `fpsString` jumps from 1 to 116 after a teleport: take the mean FPS over 2 s at the spot, with vsync off and maxFps 260.
- Write into the summary the load signs of the mods that matter and a snapshot of the settings the numbers depend on (a review
  of one unchecked measurement found 9 defects, 3 of them changed the conclusions).
- Keep screenshots (what the player sees) apart from counters (what is ready).
- Check the measure itself: is it degenerate (a "ring" in view was one column), does it depend on the look pitch (the camera's
  up vector against the radius did)?
- Two sides of a live world (client and server, two snapshots) are compared at the same moment or in a world at rest: leaves
  and fluids tick in between (what stops them: `references/vanilla-facts.md`, "A world at rest").
- Variants under the same load (a generated world, nothing heavy alongside): `tps-optimization-neoforge`, section 1.
- MSPT does not see the waits between ticks: a flight over new terrain showed MSPT 5.9 ms and "Can't keep up! Running 39219ms".
  Count the real TPS per window: (`server.getTickCount()` at the window end - at its start) / window seconds; it showed 7-8.
- One run's FPS varies by tens of percent (two identical runs: 80 and 98 FPS at the warm-up); compare FPS over 2-3 runs. Holes
  counted on screenshots and the real TPS were stable between runs (Sengoku Jidai World, 2026-10-27).
- A spark profile changes the numbers it explains: with spark's Java sampler the server fell from 7-9 TPS to about 1, with
  `--thread *` and with the server thread alone (Windows, 2026-10-27). Take numbers from runs without the profiler; a profile
  that must reach the summary ends before the run does (a 120 s profile in a 100 s run never returned its link).

## 9. An autotest in the player's game folder
When the pack cannot run in dev (Fabric mods through Sinytra Connector, the user's patched jars), test the real launcher folder
with the same state machine (sections 5-8). Checked in one project (Sengoku Jidai World, TLauncher, NeoForge 21.1.264,
2026-10-27, 8 runs); example: repo `IAlexVoss/sengoku_jidai_world`, `bench/` (mod) and `tools/bench.ps1` (runner).
- Launch without the launcher: take the game's command line once from the running process (`Win32_Process.CommandLine` of the
  java process with `--launchTarget forgeclient`; TLauncher itself is a java process too), put the bench `-D` properties right
  after the java executable and `--quickPlaySingleplayer <world folder>` at the end. TLauncher's natives stay in
  `versions/<version>/natives`. Capture again after a NeoForge or launcher update; the line holds an access token: not in git.
- The bench mod sits in `mods/` only for the run, so normal play stays clean; the mod also
  does nothing without its `-D` property. **Always overwrite a same-name jar, and keep the old bytes for `finally`.** A runner
  that does `if not exists: copy` measured an old `0.6.0` jar after the code changed: the log said 0.6.0, but the new scenario
  class was missing and the run produced no summary. Print the requested jar's SHA-256 and size before launch. Back up
  options.txt; set `soundCategory_master:0.0` **and** `pauseOnLostFocus:false` (the server pauses without focus, so no tick
  scenario runs and `PerfScenario` never fires), then put the original bytes back after the run. The launcher opens a small
  window (925x530 there): `GLFW.glfwMaximizeWindow(mc.getWindow().getWindow())` gives the same size every run; write it into the
  summary.
- A fresh copy of a template world each run (the user's world without region/, entities/, poi/ and the Distant Horizons
  database). Copies keep the template's level name, and the user, playing a manual check from the world list, opened the
  original instead of the copy: let the runner open the folder by quick play.
- The runner's commands go through the integrated server: while it lags, `time set` and `tp` land seconds late (a screenshot
  10 s after `time set noon` was still night). Hold what the measurement depends on from the client every tick (the look
  direction) or wait for the effect, not for a fixed time.
- Chunky 1.4.23: "Task finished" goes to the server console only, not to the player's chat; `ChunkyAPI.startTask` returned
  false with nothing in the log (cause not found). Working path: the commands `chunky center/shape/radius/start`, the end from
  the API events `onGenerationProgress` / `onGenerationComplete` (registered by reflection, no compile dependency on Chunky).
  The bench result matched a manual run: 6:35 against 6:41 for 16 641 chunks.
- A fresh world measures generation and holes, not the render cost of Distant Horizons: it has few LODs yet (GPU 25-37%).

## Traps
| Symptom | Cause | Fix |
|---|---|---|
| Mod loading stops with `IllegalStateException: Found unused register callbacks` (Create 6.0.10), the same code loads next time | not found; Registrate checks this only in dev (`AbstractRegistrate.onRegister` throws when `isDevEnvironment`). 4 of 204 saved logs (2026-10-16..23), all in folders with `maxThreads = -1`; 0 of about 44 at 1, but one folder had 0 of 37 at -1 too | treat it as "did not load" and repeat the run once; `maxThreads = 1` costs nothing but is not proven |
| A server check dies after 60 s | vanilla watchdog, `max-tick-time` 60000 by default | `max-tick-time=-1` in that folder |
| The window waits on a screen | onboarding of a fresh folder; experimental settings warning | options.txt; the tour answers (section 5) |
| Black screen after the tour, the client never closes | a server stop that never ends | exit watchdog; the vanilla case in `tps-optimization-neoforge` section 4 |
| Numbers "with Sodium" equal those without | the Modrinth wrapper loaded instead of Sodium | section 3 |
| A teleport repeats every tick (up to 20 times) | moved from `PlayerTickEvent` | `ServerTickEvent.Post` |
| Sampling far real chunks never ends | a far chunk generates its whole neighbourhood | many columns in a few chunks: `minecraft-worldgen-density-1-21` |
| A finished pre-generation is not on disk | `getChunkFuture` off the main thread holds its ticket for 1 tick | `references/vanilla-facts.md`, "Chunks" |

## Boundaries
- For dev runs of your own mod from Gradle and, by section 9, for an autotest in the player's launcher folder. Not for pack
  configs (`neoforge-mod-configs`) or lag hunting (`tps-optimization-neoforge`).
- NeoForge GameTest (the template's `gameTestServer` run) was not tried; it runs on a server, so checks of what the client sees
  need a tour anyway.
- One project on one Windows PC; the limits and the 2 % rate come from there. Fallback when a tour is too much for a one-off
  question: the user plays in the dev client (`runClient`) and the agent reads its log afterwards (`project-journal`).

## Passport
Created: 2026-10-25 from the dev experiments of the Space Journey mod (about 15 run configurations, about 200 dev launches,
2026-10-14..23). Journal: `skills-lab/neoforge-dev-experiments/JOURNAL.md` in this repository (not shipped with the skill).
Checked: 2026-10-25 against the project's journal and archive, its build.gradle, the run folders' settings, the saved logs (the
Registrate count) and the NeoForge 21.1.250 sources and jar (the vanilla facts); reviewed by a skeptic (workflow wf_6513e25f-1ba).
Tested 2026-10-25 (skill-forge step 5; Opus executors, Sonnet judges; game and Gradle not run, judged by code and text): repeat of the
original task passed on the first try after section 7 was extended (first run: partly, no way to see the exit code and the java
processes); two new tasks, without the skill : with the skill 5:8 and 6:8 (portal transfer autotest), 3:9 and 3:9 (FPS measurement
with Sodium), with the skill better on both.
Section 9 and the new points of section 8 added 2026-10-27 from the Sengoku Jidai World autotest (TLauncher, NeoForge 21.1.264,
9 runs). Tested 2026-10-27 (step 5, previous text : new text, Sonnet executors, one blind Sonnet judge): one new task (autotest
plan in a TLauncher folder), 11:15.
Limits: MC 1.21.1, NeoForge 21.1.250-21.1.264, ModDevGradle 2.0.148, Gradle 9.2.1; two projects.
History: CHANGELOG.md next to this file (what changed, when and why).

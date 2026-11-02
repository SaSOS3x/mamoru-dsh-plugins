# Задача: прогрузка Chunky встала, сервер не отвечает

Сборка: Minecraft 1.21.1, NeoForge 21.1.264, Sinytra Connector 2.0.0-beta.17, C2ME 0.4.0-alpha.0.123, Distant Horizons 3.3.3,
ModernFix. Мод Tidewatch 1.4.0 (Fabric, грузится через Connector) добавляет морские буи с маяками.

Что видит пользователь: одиночная игра, игрок стоит на месте, в консоли идёт `/chunky start` (радиус 1024, 16 641 чанк).
На 41% прогресс перестал меняться. Прошло 12 минут, окно игры живо (меню открывается), но мир не тикает.

Лог (`logs/latest.log`), по порядку:

```
[14:52:10] [Server thread/INFO] [Chunky] Task running ... Processed: 6823 chunks (41,00%), Rate: 48,9 cps
[14:52:13] [DH-Chunky Timeout Handler Thread[0]/INFO] [DistantHorizons]: Chunky no longer running. Re-enabling DH world gen...
[14:52:50] [ModernFix integrated server watchdog/ERROR]: A single server tick has taken 40002, more than 40000 milliseconds
[14:52:50] [ModernFix integrated server watchdog/ERROR]: Thread Dump:
```

Дамп потоков сторож ModernFix снимает каждые 40 с; за 12 минут 18 дампов. У потока сервера во всех 18 один и тот же стек:

```
"Server thread" TIMED_WAITING
  at jdk.internal.misc.Unsafe.park
  at net.minecraft.util.thread.BlockableEventLoop.waitForTasks
  at net.minecraft.util.thread.BlockableEventLoop.managedBlock
  at net.minecraft.server.level.ServerChunkCache$MainThreadExecutor.managedBlock
  at net.minecraft.server.level.ServerChunkCache.getChunkBlocking
  at net.minecraft.server.level.ServerChunkCache.getChunk
  at net.minecraft.world.level.Level.getChunk
  at net.minecraft.world.level.Level.getHeight
  at com.tidewatch.buoy.BuoySpawner.pickSpot
  at com.tidewatch.buoy.BuoySpawner.tick
  at net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents ... onEndTick
  at net.minecraft.server.MinecraftServer.tickServer
```

Остальные потоки в последнем дампе: `c2me-worker-0..4` - WAITING на семафоре (работы нет); поток Chunky - WAITING на своём
семафоре; `DH-World Gen Thread[0..4]` - два RUNNABLE (генерируют LOD), остальные ждут.

Байткод `BuoySpawner` (Connector хранит переименованный jar в `.cache/connector/tidewatch-1.4.0_mapped_moj_1.21.1.jar`):
`tick` раз в 1200 тиков для каждого игрока зовёт `pickSpot`; `pickSpot` делает до 24 попыток: случайная точка в 48-128 блоках от
игрока, `level.getHeight(Heightmap.Types.OCEAN_FLOOR, x, z)`, затем `level.getBlockState(new BlockPos(x, h, z))` и проверка, что
над дном вода глубиной 6+. Проверки, загружен ли чанк, нет. Конфиг Tidewatch: только `buoySpawnChance` и `maxBuoysPerChunk`.

Предложения в чате сборки:
- "C2ME не справляется - поставь ему больше потоков или выключи C2ME";
- "это DH: в логе он включил свою генерацию прямо перед зависанием";
- "выключи буи: `buoySpawnChance = 0`".

Пользователь просит: что на самом деле случилось, что делать сейчас и что исправить, чтобы не повторилось, и как проверить, что
исправлено. Буи в игре он хочет оставить.

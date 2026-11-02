# Задача: прогрузка чанков зависла на 32.91%

Сборка: Minecraft 1.21.1, NeoForge 21.1.264, Sinytra Connector 2.0.0-beta.17, C2ME 0.4.0-alpha.0.123, Distant Horizons 3.3.3,
ModernFix, Sengoku Jidai 2.1.5 (Fabric через Connector). Автотест: игрок стоит на месте, Chunky генерирует квадрат 16 641 чанк.

Пользователь: "Прогрузка чанков зависла на 32.91%". Последняя строка прогресса в 14:39:59, сейчас 14:53, окно игры живо.
Сторож ModernFix с 14:40:38 пишет "A single server tick has taken ... more than 40000 milliseconds" и дамп потоков; в 22 дампах у
потока сервера один и тот же стек:

```
"Server thread" TIMED_WAITING
  at net.minecraft.util.thread.BlockableEventLoop.waitForTasks
  at net.minecraft.util.thread.BlockableEventLoop.managedBlock
  at net.minecraft.server.level.ServerChunkCache$MainThreadExecutor.managedBlock
  at net.minecraft.server.level.ServerChunkCache.getChunkBlocking
  at net.minecraft.server.level.ServerChunkCache.getChunk
  at net.minecraft.world.level.Level.getChunk
  at net.minecraft.world.level.Level.getHeight
  at com.shioh.sengoku.spawn.IkuchiSpawner.findOceanSpawn
  at com.shioh.sengoku.spawn.IkuchiSpawner.trySpawn
  at net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents ... onEndTick
  at net.minecraft.server.MinecraftServer.tickServer
```

`c2me-worker-0..4` - WAITING на семафоре, поток Chunky - WAITING на своём семафоре, в 14:40:02 DH написал "Chunky no longer
running. Re-enabling DH world gen...". Байткод `findOceanSpawn`: до 40 попыток, случайная точка в 32-96 блоках от игрока,
`level.getHeight(WORLD_SURFACE, x, z)`, затем `getFluidState` в этой колонке; проверки чанка нет; `trySpawn` раз в 2400 тиков.
Конфига у спавнера нет (только игровое правило doMobSpawning). В прошлых прогонах этот же поиск за прогон трижды заканчивался сразу.

Что случилось, что делать сейчас, что исправить (морского монстра Ikuchi пользователь хочет оставить) и как проверить?

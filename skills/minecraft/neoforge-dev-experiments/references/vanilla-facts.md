# Vanilla Minecraft 1.21.1 facts for dev checks

Each fact below cost at least one run in Space Journey (NeoForge 21.1.250, 2026-10-15..23). Names are Mojang names. The date
says when it was checked: by bytecode or source, or by a fix and a rerun; "source 2026-10-25" means the NeoForge 21.1.250
sources jar. Re-check on another version.

## Moving the player
- A player moved from `PlayerTickEvent` is put back: `ServerGamePacketListenerImpl.tick` runs after `player.doTick` and returns
  the player to the last accepted position (`absMoveTo(firstGoodX, ...)`); the move fired again every tick, up to 20 times. Move
  in `ServerTickEvent.Post`. There `position - xo` is 0, so take the velocity from `getKnownMovement()` (2026-10-15, fix and a
  rerun of 14 moves of 14).
- "moved wrongly" is checked only outside creative and spectator (`handleMovePlayer`: `!gameMode.isCreative()` and not
  `GameType.SPECTATOR`; 2026-10-21 bytecode, source 2026-10-25). Creative still refuses a move into blocks silently
  (`isPlayerCollidingWithAnythingNew`) and sends a teleport (2026-10-20). An honest tour flies in survival with `mayfly` and
  counts the position packets.
- A client `setPos` through terrain is refused by the server: fly over it with the movement keys (2026-10-15).

## Chunks
- `ServerChunkCache.getChunkFuture` called off the main thread adds a `TicketType.UNKNOWN` ticket, which lives 1 tick: the
  generation stops and the future completes with a failed `ChunkResult`, which looks done. Check the result or the chunk's
  status, and hold your own ticket until the chunk is FULL (2026-10-15: a pre-generation "done in 58 s" had 428 of 14 995 chunks
  FULL on disk; source 2026-10-25).
- `Level.getHeight` over a chunk that is not loaded returns the world's bottom (`getMinBuildHeight()`): load the chunk first
  (2026-10-17: a landing put the player at the bottom; source 2026-10-25).
- `ClientLevel.hasChunk` always returns true. Check a client chunk with `getChunk(x, z, ChunkStatus.FULL, false)`, which gives
  null for a missing one; with `true` it gives the `EmptyLevelChunk` (2026-10-20; source 2026-10-25).
- `ServerChunkCache.getChunkNow` returns null as soon as the chunk's tickets no longer allow FULL
  (`GenerationChunkHolder.isStatusDisallowed`), while the chunk is still in memory; `ChunkEvent.Unload` comes later (2026-10-22,
  bytecode).
- The vanilla `ChunkTrackingView.difference` for a view of another class does `a.forEach(remove)`, `b.forEach(add)`: the client
  drops and gets the whole view again on every step over a chunk border. A custom view needs its own difference (2026-10-20,
  bytecode).
- A far chunk generates its whole neighbourhood first: compare with real chunks as many columns in a few chunks
  (`minecraft-worldgen-density-1-21`, "Measure offline").

## Light
- The server sends light updates only to players for whom the chunk is at the edge of their view (`ChunkHolder.broadcastChanges`:
  `getPlayers(pos, true)`); the client relights inner chunks itself after a block change. Compare client and server light only
  where the blocks did not change (2026-10-22, bytecode).

## A world at rest
- `server.tickRateManager().setFrozen(true)`: `ServerLevel.tick` skips block and fluid ticks, `ServerChunkCache.tick` still
  loads, sends and lights chunks. Frozen, it does not call `purgeStaleTickets`: temporary tickets never expire and chunks never
  unload. Freeze for a snapshot, not for a whole tour (2026-10-22, bytecode).
- A freshly generated chunk keeps pending block and fluid ticks and its `PostProcessing` lists. The lists are applied on the
  chunk's first tick (`ChunkMap.prepareTickingChunk` -> `LevelChunk.postProcessGeneration`: fluid ticks, shape updates,
  `setBlock`), and freezing does not stop that. A pre-generated world is at rest only when both are cleared before the tour
  (2026-10-22: with only the ticks cleared, a tour still saw blocks change in thousands of chunks).

## Entities and the player's ray
- `Entity.pick` looks along the head's yaw (`LivingEntity.getViewYRot(1)` is `yHeadRot`), and the head follows `yRot` only on a
  tick: right after a rotation packet `pick()` looks the old way (2026-10-23, javap). The ray of an item use is
  `Item.getPlayerPOVHitResult(level, player, fluid)`, along `getXRot()` / `getYRot()` to `blockInteractionRange()`. It is
  `protected` in vanilla 1.21.1, and NeoForge 21.1.250's own access transformer makes it `public` (its accesstransformer.cfg
  and javap of neoforge-21.1.250.jar, 2026-10-25). The same ray by hand, with `eye = player.getEyePosition()`:
  `level.clip(new ClipContext(eye, eye.add(player.calculateViewVector(player.getXRot(), player.getYRot()).scale(player.blockInteractionRange())), ClipContext.Block.OUTLINE, ClipContext.Fluid.NONE, player))`.
- The client has no `MOTION_BLOCKING_NO_LEAVES` heightmap: only `WORLD_SURFACE` and `MOTION_BLOCKING` are sent
  (`Heightmap.Types` usage CLIENT). Do not read it in client code (2026-10-23: a floor height taken from it put the player into
  the floor; source 2026-10-25).
- An entity's numeric id changes when its chunk is loaded again: track entities by UUID (2026-10-23).

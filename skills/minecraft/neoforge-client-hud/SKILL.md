---
name: neoforge-client-hud
description: "NeoForge 1.21.1 client HUD and its settings screen: keep the physical size at GUI x2 on x3/x4, four corners, whole-HUD/font/wave scales in a CLIENT ModConfigSpec, a persistent screen and a key binding, full-texture drawing without background, and client/server attachment sync that does not lock the UI. Triggers: HUD слишком большой на x3, настройки HUD, GUI scale, клиентский конфиг HUD, stale client state, лечение не нажимается."
---

# NeoForge client HUD and settings

Use this when a mod has a custom HUD or panel and the user asks for a settings screen, a different corner, a size that does not grow at GUI scale 3, or reports that a button stopped working after a synced action. It covers the client layout, the client config, the drawing order and the sync boundary. It does not cover the game experiment harness or general config loading; see the boundaries.

## 1. Author the HUD at GUI scale 2

Treat all HUD constants as if the GUI scale were 2. At render time:

```java
float guiScale = Math.max(1, mc.getWindow().getGuiScale());
double hudScale = HudConfig.hudScale();          // user setting, default 1.0
float drawScale = (float) (2.0 / guiScale * hudScale);
float screenW = graphics.guiWidth() * guiScale;  // physical pixels
float screenH = graphics.guiHeight() * guiScale;
```

Choose a physical padding, for example 16 px. Convert a corner to physical coordinates, then to logical coordinates for `pose.translate`, and scale the pose:

```java
float leftPhys = switch (position) {
    case TOP_LEFT, BOTTOM_LEFT -> PAD;
    case TOP_RIGHT, BOTTOM_RIGHT -> screenW - PAD - boxW;
};
float topPhys = switch (position) {
    case TOP_LEFT, TOP_RIGHT -> PAD;
    case BOTTOM_LEFT, BOTTOM_RIGHT -> screenH - PAD - boxH;
};
pose.pushPose();
pose.translate(leftPhys / guiScale, topPhys / guiScale, 0);
pose.scale(drawScale, drawScale, 1);
// draw with local coordinates 0..W, 0..H
pose.popPose();
```

`boxW` and `boxH` are the reference box multiplied by the physical factor: `W * 2 * hudScale`. If the visible art starts inside the box (labels and rays do), subtract that inset from the left and mirror it on the right, otherwise the visible content has a larger margin on one side. The inset is a **physical** number measured from a screenshot at `hudScale=1`; multiply it by `hudScale` too:

```java
float inset = CONTENT_INSET_PHYS * hudScale;
float left = PAD - inset;                                  // left corners
float right = screenW - PAD - (W * 2f * hudScale - inset); // right corners
```

Do not mix design pixels and physical pixels: at GUI scale 2 the design pixel is already 2 physical pixels. A constant that is not multiplied by `hudScale` breaks at `hud.scale=1.5`.

**Check:** screenshot at x2 and x3; the red/visible bounding box should be identical in physical pixels. In the tested case both were `X 16..291`, `Y 754..1061` at 1920x1080. Log `Window#getGuiScale()` in the run so the claim is observed, not inferred. Add a negative test: remove `2/guiScale`, and the x3 box must grow by 1.5. This is the proof that the scale lock works, not the code review.

## 2. Put settings in a CLIENT config and save them

Use `ModConfig.Type.CLIENT`, not COMMON, for corner and size preferences:

```java
POSITION = BUILDER.defineEnum("hud.position", HudPosition.BOTTOM_LEFT);
HUD_SCALE = BUILDER.defineInRange("hud.scale", 1.0, 0.5, 2.0);
FONT_SCALE = BUILDER.defineInRange("hud.fontScale", 0.65, 0.35, 1.5);
WAVE_SCALE = BUILDER.defineInRange("hud.waveScale", 1.0, 0.5, 2.0);
SPEC = BUILDER.build();
container.registerConfig(ModConfig.Type.CLIENT, SPEC);
```

In the screen:

```java
HudConfig.POSITION.set(next);
HudConfig.SPEC.save();          // set() alone does not write the file
```

Read the values every frame; do not cache them in a field that only builds once. A screen with a position button, minus/plus buttons for each scale, reset and done is enough. Use `Button.builder(...).bounds(...).build()` and add it with `addRenderableWidget`. The screen should have a parent so Escape returns where it came from.

Give the screen a key mapping with `KeyConflictContext.IN_GAME`. Apostrophe (`GLFW_KEY_APOSTROPHE`) is the same physical key as Russian `э`; a US user sees `'`. Check the key only when `minecraft.screen == null`. Keep the existing HUD visibility key and its `showHud` start state separate; do not let the settings key replace or duplicate the toggle, and test a rebound key.

The HUD is normally hidden while any screen is open. To make "applies live" true, extract the drawing into a method used by both the overlay event and the settings screen, and render it as a preview on the settings screen above the background. Otherwise the user only sees the new scale after closing the screen.

**Pitfall:** `ConfigValue.set()` alone changes memory but leaves the file old; next launch restores the old value. Always call `SPEC.save()`. Guard values with `SPEC.isLoaded()` if the screen can be opened during loading, and read them per frame rather than caching a field.

## 3. Draw textures whole, and draw text last

- A downscaled `blit(texture, x, y, 0, 0, 4, 4, 8, 8)` samples a 4x4 **region**, not the whole 8x8 image. For a drop icon or silhouette, draw the full texture or use `pose.scale` around its centre.
- A full silhouette with `pose.scale(0.40)` stays intact; blitting a small destination rectangle can look cut off. Use the same rule for rays: scale the full `ray_XX.png`, do not crop its region.
- Draw the sun, rays and silhouette first, then labels and waves. Keep label positions above ray tips. If labels still collide, shorten the rays or move the labels outward before adding a background; this HUD is intentionally transparent.
- Wave bars are also a setting: scale their width, thickness and amplitude together. Do not scale only the width.

## 4. Do not let the client gate authoritative state

This is the failure that looked like a stuck button. The panel read synced `LimbRegen`, saw a stale "bandage is active" entry and blocked every click until death.

**Verified source fact:** in NeoForge 21.1.250, `AttachmentHolder.setData(type, value)` always calls `syncData(type)`, even when `value` is the same instance. The sync codec then writes the current fields. A same-instance `setData` is therefore not the reason a client misses an update. Check the version's sources before blaming identity dedupe. If the client never received the active entry at all, it could not block the second click; that contradiction is a useful diagnostic.

The real permanent lock in the tested case was a treatment record that never stopped. A queued heal can leave a positive remainder while the limb is already full (including a float residue), so `active(limb)` stays true forever. The client then used a queue-wide "any bandage is active" gate and swallowed every later click, including other limbs; only death reset the attachment. Fix the record, not the packet:

```java
boolean healedAnything = health.heal(limb, amount) > 0.0;
if (regen.remaining(limb) <= 0.0 || (!healedAnything && regen.remaining(limb) > 0.0)) {
    regen.stop(limb);             // full limb, zero progress
}
if (limb == Limb.TORSO && entity.getHealth() >= entity.getMaxHealth()) {
    regen.stop(limb);
}
```

Rules:

1. The client may check whether the action is **possible** (limb damaged, item held), but the server checks the cooldown, the active treatment and the limb state.
2. Server-side pruning is the real fix for a stale treatment. Stop a record when its limb is full or when it restored zero health with a positive remainder; prune such records before rejecting a new action.
3. Do not make a global "one item at a time" rule when the product wants parallel work. Check `regen.active(limb)` per limb; a bandage on the arm must not block a bandage on the leg. Keep the item cooldown separate and explain it in the UI.
4. Keep the client's UI code free of a hard block on a synced queue. The final contract is: the client always sends the click; the server alone decides `active(limb)`. Do not add a "temporary" per-limb client gate: it can go stale for the same reason. Use the synced state only for display (labels, HUD, a grey hint).
5. If you make the state immutable, storing a copy is good design, and one `setData` is enough. Do not add `AttachmentSync.syncEntityUpdate` after every `setData` without measuring: it can send a second packet for no reason.
6. When the symptom is "works until death", inspect the **server's active map** first, then the client gate. A `/reload` or respawn that clears both proves nothing about which one was stuck.
7. Sync lands at the end of the server tick or at the next tracking update. In a test, tick once before reading the client-side `getData`; do not assert immediately after the packet handler. When a record is stopped, publish the cleared value with `setData` so the client mask clears too, not only the server's rejection path.

**Check:** a unit test that finishes one treatment and applies a second one; a test for a stale entry on a full limb; a test for two different limbs in parallel; and, if possible, a real click in a dev client. The unit test alone did not catch the client-side stale gate. For the sync claim, test on a real `ServerLevel` and count payloads; Mockito's `setData` mock proves nothing about NeoForge's sync.

## 5. Verify the whole picture

- Settings screen screenshot in the user's language.
- HUD screenshot at GUI scale 2 and 3; compare the physical bounding boxes and log `getGuiScale()`.
- All four corners; a corner near a minimap or hotbar is a real layout case.
- One live action after the UI change, not only a `/give` or a code inspection.
- The HUD toggle (H) and its `showHud` start state still work; the settings key and a rebound key do not conflict with it.
- Silence and focus for automated runs: `soundCategory_master:0.0`, `pauseOnLostFocus:false`; restore the user's options after the run.

See `neoforge-dev-experiments` for the run harness, `neoforge-mod-configs` for config loading and `windows-shell-dsh` for Windows encoding/quoting. This skill does not repeat those.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| HUD is 1.5x larger at x3 | drawn in logical coordinates | anchor in physical pixels, `pose.scale(2/guiScale * hudScale)` |
| HUD content has unequal margins | visible art starts inside the box | subtract the content inset and mirror it on the right |
| Drop shows one quarter | `blit` with a destination smaller than source | draw full texture or pose-scale it |
| Silhouette looks cut | downscaled destination region | full texture with pose scale around centre |
| Settings reset after restart | `ConfigValue.set` without `SPEC.save` | call `SPEC.save()` |
| Button works once then never | treatment record never stops + client-wide gate | stop on zero progress/full limb; remove client-wide gate; check per limb |
| Same-instance setData blamed for a stuck client | NeoForge syncs on every setData | inspect the active record first; verify against the version's source |
| Second limb cannot be treated | global `regen.has(kind)` check | check `regen.active(limb)` only |
| Text is under a ray | draw order or label position | labels after rays and above their tips |

## Boundaries

Do not use this skill for server-only gameplay logic or for moving a feature between mods; that belongs to the project. Do not use it as a substitute for the experiment harness: a pretty screenshot is not a run result. If the mod has no client HUD, use the smaller `neoforge-mod-configs` and `windows-shell-dsh` combination. Values and GUI scale behavior were checked on NeoForge 21.1.250 / Minecraft 1.21.1; recheck another version.

## Паспорт

Создан: 2026-11-10 из задачи "HUD конечностей: фиксированный размер, экран настроек, синхронизация лечения", журнал: `skills-lab/neoforge-client-hud/JOURNAL.md`.
Проверен: 2026-11-10, NeoForge 21.1.250 / Minecraft 1.21.1, скриншоты x2/x3 и четыре угла, 393 unit-теста limb-damage, `runLimbCheck` PASS, `mob-sweep` PASS. Слепые судьи: задача настроек 2/2 за навык; задача залипания после правки 2/1 за навык (третий судья разрешил раскол). Остаточные замечания: тест должен учитывать конец тика/следующий tracking update, а остановка записи должна публиковать очищенное значение. Навык установлен в `skills/minecraft/neoforge-client-hud`; журнал лежит в `skills-lab/neoforge-client-hud`.
Границы: см. выше; не заменяет `neoforge-dev-experiments`, `neoforge-mod-configs`, `windows-shell-dsh`.
История изменений: `CHANGELOG.md`.

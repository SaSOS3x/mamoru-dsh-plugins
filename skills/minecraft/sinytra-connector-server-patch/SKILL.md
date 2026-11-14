---
name: "sinytra-connector-server-patch"
description: "Серверный патч Fabric-мода под NeoForge через Sinytra Connector: ITransformationService/ITransformer (не ILaunchPluginService), замена миксинов после ремапа, accessor по эразу, новые классы GAME-ресурсом, без патча кэша. Триггеры: «мод не работает на сервере через Connector», «InvalidInjectionException descriptor», «InvalidAccessorException», «No candidates were found matching», «Mixin apply failed», «client_only патч», Connector server patch."
---

# Серверный патч Fabric-мода под Sinytra Connector

Fabric-мод, который на клиенте запускается только с клиентским патчем (`sengoku_patch`, `client_only`),
на NeoForge-сервере падает на миксинах. Патч делается **не правкой jar и не патчем кэша**, а
`ITransformationService` в отдельном jar: он подменяет сломанные классы в момент загрузки и отдаёт
новые классы отдельным GAME-ресурсом. Такой патч работает с оригинальным jar мода, пустым кэшем
Connector и не требует клиентских модов.

Проверено на Minecraft 1.21.1, NeoForge 21.1.264, Sinytra Connector 2.0.0-beta.17, ModLauncher 11.0.5,
FancyModLoader 4.0.45, Sponge Mixin 0.16.4, Sengoku 2.1.5 (ноябрь 2026). Числа и имена классов ниже -
из этой задачи; на других версиях проверяй заново.

## 1. Сначала диагностика, а не код

Прочитай `logs/debug.log` (не только `latest.log`) и найди две строки:

```text
# без патча
Found transformer services : [mixin,fml,connector_loader]
# с патчем - твой сервис появился в списке
Found transformer services : [sengoku_server_patch,mixin,fml,connector_loader]
Found launch plugins: [mixin,slf4jfixer,runtime_enum_extender,accesstransformer,runtimedistcleaner]
```

- Если в `transformer services` нет твоего jar - FML не увидел `META-INF/services/...ITransformationService`.
- Если в `launch plugins` нет твоего jar - это нормально: **`ILaunchPluginService` из `mods/` не
  загружается**, `LaunchPluginHandler` смотрит только BOOT-слой. Код `handlesClass`/`processClass`
  в моде - мёртвый; не трать на него время.
- `ITransformationService` из `mods/` попадает в SERVICE-слой (`ModDirTransformerDiscoverer`), его
  родитель - BOOT: modlauncher, ASM, securejarhandler, log4j, gson. Классов Minecraft и мода там нет,
  поэтому сервис может работать только через ASM и ресурсы.

Дальше выясни, откуда Mixin берёт конфиг. На сервере это **mapped-кэш Connector**, а не оригинальный
Fabric-jar: `FabricModMetadataParser` → `ModFileParser.getMixinConfigs` → `LoadingModList` →
`DeferredMixinConfigRegistration` → `MixinConfig.create` через `MixinServiceModLauncher.getResourceAsStream`
(TCCL = TransformingClassLoader, GAME-слой). FML при discovery пропускает оригинальный Fabric-jar
(его мапит Connector), но сам оригинал остаётся источником для кэша.

Байткод миксинов идёт через `MixinInfo` → `getBytecodeProvider().getClassNode(name, true)` →
`ModuleClassLoader.getMaybeTransformedClassBytes` → `ClassTransformer.transform` → `ITransformer`.
Поэтому `ITransformer` заменяет и миксин-классы, и accessor-интерфейсы, и обычные классы.

## 2. Архитектура

Отдельный jar в `mods/`. В этой задаче он был с `neoforge.mods.toml`, и FML пометил его
`Skipping ... because it was already located`: как мод он не грузится. Без `mods.toml` discovery
идёт по `META-INF/services` и тоже должен работать, но это не проверено.

```text
META-INF/services/cpw.mods.modlauncher.api.ITransformationService   <- имя класса сервиса
sengoku_server_patch/targets.txt                                     <- список: какие классы менять (13 в этой задаче)
sengoku_server_patch/replacements/<path>.class                       <- готовые классы
sengoku_server_patch/game_layer_classes.jar                          <- НОВЫЕ классы (connectorfix)
```

Сервис реализует только `ITransformationService`:

- `beginScanning` **всегда** возвращает
  `new Resource(IModuleLayerManager.Layer.GAME, List.of(SecureJar.from(extractedJar)))` для jar'а с
  новыми классами. Не клади эти классы в mapped-jar: два GAME-jar'а с одним пакетом дают split package.
- `onLoad` читает `targets.txt` и создаёт `ITransformer<ClassNode>`.
- `transformers()` отдаёт трансформер. В `transform` достаточно вернуть готовый `ClassNode`
  замены (`new ClassReader(bytes).accept(node, 0)`); копировать поля вручную не нужно, потому что
  заменяется класс целиком.
- `handlesClass/processClass` не нужны вовсе.

`targets.txt` и replacements - это **весь** набор сломанных классов. Не копируй клиентские
`client/`, `*Screen`, `*Renderer`: проверь байты на `net/minecraft/client`, `com/<mod>/client`.

### Как собрать список замен

1. Если есть клиентский патч, возьми его `targets.txt` (у Sengoku 157 классов) и отбрось всё с
   `client/`, `screen/`, `*Client`, `mixin/client/` - останется 12 серверных.
2. Сверь с `sengoku.fabric.mixins.json`: нужны миксины, которые падают по логам, плюс классы, на
   которые они ссылаются через `extends`/`instanceof`. Дверную связку бери целиком, частично нельзя.
3. Добавь исправленный accessor. Итог этой задачи (13): `ShojiDoubleDoorBlock`,
   `ShojiTripleDoorBlock`, `ShojiTripleDoorBlock$1`, `DoorBlockMixin`, `DoorInteractGoalMixin`,
   `InteractWithDoorMixin`, `MobAttackSweepMixin`, `SlotMaxStackMixin`, `WalkNodeEvaluatorMixin`,
   `FlowingFluidMixin`, `AbstractIllagerBlockingDataMixin`, `RangedCrossbowAttackGoalMixin`,
   `RangedCrossbowAttackGoalAccessor`; плюс 5 новых `connectorfix/*` в GAME-jar.
4. Проверь каждый replacement на ссылки на клиентские классы и на отсутствующие классы
   (`javap -v`, поиск `com/<mod>`), иначе сервер упадёт позже, на загрузке блока или моба.

## 3. Accessor: заменять, а не удалять

Симптом: `InvalidAccessorException: No candidates were found matching mob:Lnet/minecraft/world/entity/monster/Monster;`
(или другой дескриптор). Причина: в NeoForge 21.1.264 `RangedCrossbowAttackGoal` стал generic,
поле `mob` имеет эразур `Mob`, а старый accessor объявляет `Monster`. Проверяй по **NeoForge**
jar'у, а не по ванильному `srg.jar`:

```powershell
javap -p -classpath "libraries/net/neoforged/neoforge/21.1.264/neoforge-21.1.264-server.jar" `
  net.minecraft.world.entity.ai.goal.RangedCrossbowAttackGoal
```

Если поставить `server-...-srg.jar` первым, увидишь ванильный `monster/Monster`: рантайм берёт
NeoForge-патч, и правильный ответ - `Mob` (и `final float attackRadiusSqr`).

Собери исправленный accessor в официальных именах (`@Mixin(RangedCrossbowAttackGoal.class)`,
геттер `Mob`, `@Mutable` для `final` поля). Удалять класс нельзя: конфиг в кэше всё равно содержит
запись `RangedCrossbowAttackGoalAccessor`, и Mixin упадёт на её отсутствии. Замена миксина, который
пользовался accessor'ом, обязательна; сам accessor после неё нужен только чтобы запись конфига
разрешилась.

## 4. Новые классы (connectorfix)

Если мод кладёт в свой jar классы в чужом пакете (Sengoku - `net.minecraft.world.level.block.*`),
Mixin не может их загрузить: `ClassNotFoundException`. Replacement-классы ссылаются на новые
`<mod>.block.connectorfix.*`. Трансформер не умеет добавлять классы, поэтому:

1. собери эти новые классы отдельным jar'ом;
2. положи его в ресурсы патча;
3. в `beginScanning` распакуй во временный файл и отдай `Resource(Layer.GAME, SecureJar.from(temp))`;
4. в mapped-jar их **не** добавляй.

## 5. Сборка (ModDevGradle)

- Проще всего на ModDevGradle: `plugins { id 'net.neoforged.moddev' }`, `neoForge { version = ... }`,
  и сервис компилируется против `net.neoforged:neoforge` - modlauncher, ASM и securejarhandler
  приходят транзитивно, отдельные `compileOnly` не нужны. Так собрано в проекте-источнике.
- `sourceSets { patchclasses { java.srcDir 'src/patchclasses/java'; compileClasspath += sourceSets.main.compileClasspath } }`
  для классов, которые должны иметь чужое имя пакета (accessor), но не быть обычными классами
  твоего jar.
- `processResources { from(sourceSets.patchclasses.output) { include '...'; into 'sengoku_server_patch/replacements' } }` -
  так класс уезжает в ресурсы и не создаёт split package.
- Если MDG нет, те же зависимости можно взять `compileOnly`:
  `cpw.mods:modlauncher:11.0.5`, `cpw.mods:securejarhandler:3.0.8`, `org.ow2.asm:asm:9.10.1`,
  `asm-tree:9.10.1`; Mixin нужен только для `@Mixin` в patchclasses.
- `clean build` должен проходить без сети после первого прогона (кеш Gradle).

## 6. Проверка на копии сервера

Не проверяй на боевом сервере. Сделай копию:

- `libraries` - junction на настоящий сервер, `mods` - копии jar'ов (не hardlink: правка тестового
  jar'а не должна портить настоящий), `world` - копия боевого мира, порт 25566.
- Первый запуск с пустым `.cache/connector` занимает ~100 с на мапинг 500-МБ jar'а; повторный - секунды.

Скрипт smoke-теста запускает сервер, ждёт `Done (`, шлёт команды (`summon` сломанных мобов,
`chunky` для генерации), затем `stop`, пишет `<log>.result.txt` с настоящим `exit_code`. Без
sidecar строка `Stopping the server` ничего не доказывает: JVM может не выйти (в этом модпаке
иногда висит non-daemon `pool-23-thread-1`).

Проверки:

1. `debug.log`: твой сервис в `Found transformer services`, его нет в `Found launch plugins`.
2. `latest.log`: `[<patch>] loaded N class replacements`, ни одного `Mixin apply ... failed`,
   `InvalidAccessor`, `InvalidInjection`, `NoClassDefFoundError` по моду.
3. Кэш не изменён: нет **нашего** маркера (`META-INF/<patch>.marker`), accessor внутри всё ещё с
   исходным дескриптором, новых классов нет. Осторожно: Connector сам пишет в `.cache/connector`
   файл `patch_audit.txt` - это не след нашего патча.
4. Чистый оригинальный jar + пустой кэш → `Done`, `summon` сломанного моба без ошибок.
5. `exit_code=0` в sidecar; повторный запуск тоже `Done`.

Проверяльщик должен уметь доказать, что проверка не слепая: подложи мутанта (например, accessor с
`()Ljava/lang/Object;`) и убедись, что `verify_patch_jar.py` краснеет. Проверяй точные дескрипторы,
а не подстроку `Mob` в имени метода.

## 7. Ловушки

| Симптом | Причина | Решение |
|---|---|---|
| `InvalidInjectionException ... Invalid descriptor ... Expected (InteractionHand, CallbackInfo) but found (..., boolean, CallbackInfo)` | intermediary даёт перегрузкам уникальные имена, Mojmap - одно; после Connector обработчик не совпадает | replacement-миксин с явными дескрипторами `method = {"swing(...)"}` |
| `InvalidAccessorException ... No candidates` | эразур поля (`Mob`, не `Monster`) | исправленный accessor, не удаление |
| `Mixin apply ... Super class '...Mob' was not found in the hierarchy of target class '...Mob'` | миксин объявляет неверный super | replacement без этого super, передавай mob явно |
| `ClassNotFoundException: net.minecraft.world.level.block.TripleDoorBlock$Part` | мод положил классы в чужой пакет | connectorfix-классы отдельным GAME-jar'ом |
| `java.util.zip.ZipException: zip END header not found` | кэш патчили, пока Connector его писал (или кэш битый) | не патчить кэш во время запуска; offline-патч возможен, но не нужен - хватает `ITransformer` |
| `ArrayIndexOutOfBoundsException` или `RuntimeException: Failed to execute task ...Mixin.class` | replacement'ы положили в jar мода **до** Connector | замены только в runtime |
| `ILaunchPluginService` ничего не делает | сервис из `mods/` не грузится | `ITransformationService.transformers()` |
| `Found transformable jar with unsupported mapping official` | другой мод (например, `fabric-language-kotlin`) с `Fabric-Mapping-Namespace: official` | убрать этот мод с сервера |
| `Detected setBlock in a far chunk` тысячами | большая структура мода (Sengoku fortress, `beard_box`, ~200x200); C2ME лишь распараллеливает генерацию | DSBG (см. §8) |

## 8. Шум worldgen (`Detected setBlock in a far chunk`)

Причина - структура мода, а не C2ME: `WorldGenRegion.ensureCanWrite` отклоняет блоки структуры вне
разрешённой области и логирует каждый; C2ME только распараллеливает генерацию, поэтому строки идут
с `c2me-worker-*`. У Sengoku структура `minecraft:pillager_outpost` заменена на
`shioh:outposts/fortress` с `terrain_adaptation: beard_box` и `max_distance_from_center: 100`;
на 729 чанках Chunky это 30 683 строки (в живой сессии на боевом мире - 30 723).

Фикс - серверный мод DSBG (`dsbg` на Modrinth, NeoForge 1.21.1, CC BY-ND 4.0): он отменяет
`Util.logAndPauseIfInIde` в `ensureCanWrite`, оставляя `return false`. Поведение мира не меняется,
блоки отклонялись и раньше. Проверка на копии мира: без DSBG 30 683, с DSBG 0; 18 строк
`Block-attached entity at invalid position` остаются (другое сообщение, не мешает).

Не подавляй лог, не поняв причину: если структура ломается из-за `setBlock`, фильтр спрячет симптом.

## 9. Границы

- Не для переноса данных 1.20.1 Forge → 1.21.1 NeoForge: это `modpack-port-neoforge`.
- Не для мода, который требует нативного клиента или содержит только серверно-несовместимый код:
  патч заменяет классы, но не переписывает логику.
- Не для обхода авторизации/лицензий; заменяй только классы, которые действительно сломаны ремапом.
- Если проблема решается конфигом мода - делай конфиг, а не патч.
- Запасной путь, если трансформер не подошёл: подготовленный jar мода без accessor'а + клиентский
  патч на сервере (только для диагностики, не финал), либо issue автору мода.
- Версии и имена классов стареют: перед переносом на новую версию мода пересобери список
  replacement'ов и проверь `targets.txt` (`tools/sync_replacements.py` в проекте-источнике).

## Паспорт
Создан: 2026-11-14 из задачи «серверный патч Sengoku Jidai 2.1.5 для NeoForge 21.1.264 + Connector
без клиентского sengoku_patch», журнал: `skills-lab/sinytra-connector-server-patch/JOURNAL.md`.
Проверен: 2026-11-14, NeoForge 21.1.264, Connector 2.0.0-beta.17, Sengoku 2.1.5; 6 прогонов
(чистый кэш, тёплый кэш, боевой сервер, сессия игрока, контроль/фильтр DSBG), проверяющий агент
нашёл и заставил исправить ложные PASS в приёмочных скриптах. Повтор задачи чистым исполнителем
(журнал, запись от 2026-11-14 21:26): пришёл к той же архитектуре, нашёл 6 неточностей, они
исправлены; проверено решение, а не полная сборка. Проверка фактов по jar'ам (журнал, 21:35):
9 групп, javap-команда и префикс ресурсов были неверны и исправлены.
Границы: одна версия мода/лоадера, без клиентских проверок; шум worldgen лечится отдельным модом.

# Journal: sinytra-connector-server-patch

## 2026-11-14 18:13 | анализ | Задача: Sengoku 2.1.5 на NeoForge-сервере через Connector без клиентского патча

Задача: dedicated-сервер NeoForge 21.1.264 + Sinytra Connector 2.0.0-beta.17 должен запускать Fabric-мод
Sengoku 2.1.5 без клиентского `sengoku_patch` (он `client_only`) и без правки клиентской сборки.
Предыдущая сессия оставила HANDOFF с рабочим обходом (удалённый accessor в 498-МБ jar + клиентский
патч на сервере) и с гипотезой «Mixin читает конфиг из оригинального jar».

Готового навыка нет: `modpack-port-neoforge` и `port-from-1182-pack` про перенос данных 1.20.1 Forge →
1.21.1 NeoForge, `neoforge-dev-experiments` про dev-прогоны, `minecraft-worldgen-density` про рельеф.
Ни один не описывает Sinytra Connector, трансформационные сервисы ModLauncher и ремап миксинов
intermediary→Mojmap. Решение: вести журнал, сделать задачу, затем оформить навык.

## 2026-11-14 18:20 | исследование | Как NeoForge находит сервис в mods/

Источник: `loader-4.0.45.jar`, `modlauncher-11.0.5.jar`, `securejarhandler-3.0.8.jar` из
`sengoku_server/libraries`; декомпиляция Vineflower, отчёт агента B (`work/agent-b/report.md`).

Проверено делом:
- `ModDirTransformerDiscoverer.scan` + `TransformerDiscovererConstants.SERVICES` берут jar из `mods/`
  в SERVICE-слой, если в нём есть `META-INF/services/` одного из шести сервисов, включая
  `cpw.mods.modlauncher.api.ITransformationService`.
- `TransformationServicesHandler.discoverServices` грузит сервис ServiceLoader'ом SERVICE-слоя;
  родитель - BOOT (modlauncher, ASM, securejarhandler, log4j, gson), классов Minecraft/Sengoku нет.
- `ILaunchPluginService` из `mods/` НЕ загружается: `LaunchPluginHandler` смотрит только BOOT-слой.
  В логе `Found launch plugins: [mixin,slf4jfixer,runtime_enum_extender,accesstransformer,runtimedistcleaner]`
  нашего имени нет, хотя файл сервиса лежал в jar.

## 2026-11-14 18:25 | исследование | Откуда Mixin берёт конфиг и байткод миксинов

Источник: декомпиляция `connector-2.0.0-beta.17`, `sponge-mixin-0.16.4`, FML; логи сервера; отчёт B.

Проверено:
- Конфиг миксинов берётся из **mapped-кэша** Connector, не из оригинального Fabric-jar:
  `FabricModMetadataParser` → `ModFileParser.getMixinConfigs` → `LoadingModList.addMixinConfigs` →
  `DeferredMixinConfigRegistration` → `MixinConfig.create` читает JSON через
  `MixinServiceModLauncher.getResourceAsStream` (TCCL = TransformingClassLoader, GAME-слой).
  Утверждение HANDOFF «из оригинала» неверно; путаница из-за гонки патча кэша.
- Байткод миксин-класса идёт через `MixinInfo` → `getBytecodeProvider().getClassNode(name, true)` →
  `MixinLaunchPluginLegacy` → `ModuleClassLoader.getMaybeTransformedClassBytes` →
  `ClassTransformer.transform` (BEFORE-плагины, затем `ITransformer` PRE_CLASS/FIELD/METHOD/CLASS,
  затем AFTER). Значит `ITransformer` заменяет и миксин-классы, и accessor-интерфейс.
- Mapped-jar пишется `ZipOutputStream` в конечный файл (`JarTransformInstance` → `Renamer`);
  открывать и патчить его во время записи нельзя (`zip END header not found`). После открытия
  SecureJar central directory кэшируется в памяти, и правка файла на текущий запуск не действует.

## 2026-11-14 18:30 | исследование | Почему падают конкретные миксины Sengoku

Источник: байткод Sengoku 2.1.5, replacement-классы `sengoku_patch-2.1.5.jar`, логи 2026-11-14,
отчёт агента A (`work/agent-a/report.md`).

Проверено:
- Intermediary даёт перегрузкам уникальные имена (`method_6104`, `method_23667` = оба `swing`),
  Mojmap - одно имя `swing`. После Connector `@Inject(method = "swing")` с обработчиком
  `(InteractionHand, boolean, CallbackInfo)` валидируется против `swing(InteractionHand)` →
  `InvalidInjectionException: Invalid descriptor ... Expected (InteractionHand, CallbackInfo)
  but found (InteractionHand, boolean, CallbackInfo)`. То же у `DoorBlockMixin` (`isWoodenDoor`) и
  `SlotMaxStackMixin` (`getMaxStackSize`).
- `RangedCrossbowAttackGoalAccessor`: в оригинале геттер объявлен как `Monster`, а поле
  `RangedCrossbowAttackGoal.mob` в 1.21.1 имеет эразию `Mob` (проверено javap по
  `neoforge-21.1.264-server.jar`); `InvalidAccessorException: No candidates ... monster/Monster`.
  Замена миксина accessor не использует, но запись в конфиге остаётся, поэтому нужен валидный
  accessor-класс, а не удаление.
- Sengoku кладёт в свой jar пять классов в пакете `net.minecraft.world.level.block`
  (`DoubleDoorBlock`, `TripleDoorBlock`, `$1`, `$Part`), которые Mixin не может загрузить
  (`ClassNotFoundException`); replacement-классы `Shoji*DoorBlock` наследуют
  `com.shioh.sengoku.block.connectorfix.*`. Это НОВЫЕ классы, трансформер их добавить не может.

## 2026-11-14 18:35 | разработка | Первая версия: патч кэша + ILaunchPluginService

Сделано: сервис по образцу клиентского `SengokuPatchTransformationService` - патч mapped-jar на
диске (маркер, watcher 25 мс, fallback GAME-jar) плюс `ILaunchPluginService` с replace в памяти.
Собрано, поставлено на изолированный стенд. Результат: `Done (23.378s)`, но выход завис, а в логе
были `zip END header not found` при попытке патчить недописанный кэш. Решение не принято.

## 2026-11-14 18:40 | разработка | Переход на чистый ITransformationService + ITransformer

После отчёта B: убраны патч кэша, watcher, маркер, mapped_overrides, `ILaunchPluginService`.
Осталось: `beginScanning` всегда отдаёт GAME-`Resource` с пятью connectorfix-классами;
`transformers()` отдаёт `ITransformer<ClassNode>` на 13 классов (12 из `sengoku_patch` + свой
accessor); `onLoad` читает `targets.txt` из ресурсов. Сборка: ModDevGradle, отдельный source set
`patchclasses` для accessor'а, его класс пакуется в `.../replacements/`, а не в корень jar.

Проверено: чистый оригинальный Sengoku jar (498 037 338 B) + пустой `.cache/connector` + только
этот jar → `Done (23.378s)`, спавн pillager/vindicator/ronin/oni brute, ни одной mixin-ошибки;
кэш после запуска не изменён (нет маркера, accessor внутри с `Monster`, connectorfix нет).

## 2026-11-14 19:05 | тест | Чистый кэш, чистый jar, summon, exit code

`work/logs/20261114-190322-smoke.log`, sidecar `.result.txt`: мапинг 102 с, `Done (3.440s)`,
`summon` Outlaw Ashigaru/Outlaw Samurai/Oni Brute, `exit_code=0`, `timeout_stop=false`.
Повторный запуск: `Done (4.986s)`, exit code 0. Боевой `sengoku_server` (оригинальный jar, без
`sengoku_patch`): `Done (2.991s)`, exit code 0.

## 2026-11-14 19:57 | тест | Сессия игрока и разбор лога

35 минут, 31 433 строки. Патч загрузился (`loaded 13 class replacements`), ни одной
`Mixin apply ... failed`, ни `InvalidAccessor`, ни `InvalidInjection`. 30 768 ERROR - 30 743 от
C2ME на генерации чанков, остальные 25 - стартовые (рецепты sake/Create, POIReplacer, spawn data).
Клиентские жалобы (яркий Энд, вода без тумана) - Polytone/Iris/DH, те же ошибки Polytone были в
16:48-17:06 до установки патча. Редстоун на тройной двери не работает и в оригинале: и
`TripleDoorBlock.method_9612`, и replacement только синхронизируют OPEN, `hasNeighborSignal` не читают.

## 2026-11-14 21:15 | исследование | Шум worldgen: Sengoku fortress + C2ME

Источник: лог сессии, `data/minecraft/worldgen/structure/pillager_outpost.json` внутри Sengoku jar,
код DSBG (Modrinth `dsbg`, NeoForge 1.21.1).

Проверено:
- Sengoku подменяет `minecraft:pillager_outpost` на `shioh:outposts/fortress` с
  `terrain_adaptation: beard_box`, `max_distance_from_center: 100`; крепость ~200x200 блоков.
  Ванильный `WorldGenRegion.ensureCanWrite` отклоняет блоки вне области и логирует каждый:
  30 683 строки за 25 с генерации.
- DSBG отменяет вызов `Util.logAndPauseIfInIde` в `ensureCanWrite` и возвращает false; поведение
  не меняется. На копии боевого мира (удалён `r.-1.-2.mca`, Chunky 729 чанков): без DSBG 30 683,
  с DSBG 0; 18 `Block-attached entity` остаются (другое сообщение).

## 2026-11-14 21:25 | анализ | Нужен ли навык

Задача повторится: любой клиентский Connector-патч для Fabric-мода на NeoForge-сервере упирается
в те же три вещи (ремап перегрузок, сервис не из mods/, новые классы только GAME-ресурсом).
Без подсказки путь долгий: в этой задаче он занял ~3 часа и потребовал четырёх агентов. Способ
проверен делом на чистом кэше, чистом jar и боевом сервере. Существующие навыки не покрывают.
Решение: создать `sinytra-connector-server-patch`; DSBG и разбор шума - отдельным разделом, так
как это частая попутная проблема.

## 2026-11-14 21:26 | тест | Повтор задачи чистым исполнителем по черновику

Исполнитель с чистым контекстом (запрещено читать HANDOFF/README/notes), на входе - текст ошибок
миксинов и путь к черновику `skills/minecraft/sinytra-connector-server-patch/SKILL.md`.

Результат: пришёл к правильной архитектуре (ITransformationService + ITransformer, GAME-Resource
для connectorfix, замена accessor'а, без патча кэша), назвал проверки по `debug.log`, первый
эксперимент на копии и риски. Значит, навык ведёт к решению, а не к обходу.

Исполнитель нашёл 6 неточностей, все исправлены в черновике:
- §5: проект собирается на ModDevGradle (`neoForge`), а не на явных `compileOnly`; переписал.
- §2: `copyClassNode` не нужен, `transform` возвращает готовый `ClassNode`; убрал.
- §7: класс исключения prepatch не гарантирован (`RuntimeException: Failed to execute task`);
  смягчил.
- §6: «нет маркера» неоднозначно, Connector пишет `patch_audit.txt`; уточнил, что проверять
  только наш маркер.
- §1: «оригинальный jar отбрасывается» - FML пропускает его при discovery, но Connector мапит
  его в кэш; переформулировал.
- Не было полного списка 13 классов; добавил список и процедуру отбора.

Граница теста: проверено решение, а не полная сборка/запуск исполнителем. Это слабее повтора
исходной задачи целиком и записано как ограничение.

## 2026-11-14 21:35 | тест | Проверка фактов навыка по jar'ам

Проверяющий-скептик сверил 9 групп утверждений с `debug.log`, javap и декомпиляцией Connector/Mixin.

Вердикты: 1-3 CONFIRMED (SERVICE-слой, mapped-кэш как источник конфига, путь `ITransformer` через
`MixinInfo` → `ModuleClassLoader`), 5 CONFIRMED (5 connectorfix в GAME-jar, `ClassTransformer`
меняет только существующие цели), 8 CONFIRMED (Sengoku fortress, `beard_box`, DSBG не меняет
поведение). Пункт 4 CONFIRMED для рантайма, но **команда javap в навыке была неверной** (REFUTED):
с `srg.jar` первым виден ванильный `Monster`, а рантайм NeoForge 21.1.264 - `Mob`. Пункт 6 PARTLY:
патч кэша возможен offline, но гонка с записью реальна; «нельзя вообще» - слишком сильно. Пункт 9:
префикс ресурсов `patch/` не совпадал с фактическим `sengoku_server_patch/`, а пример лога был без
патча.

Исправлено в черновике: javap только по `neoforge-21.1.264-server.jar` + оговорка про srg;
`patch/` → `sengoku_server_patch/`; «кэш не патчить вообще» → «не патчить во время запуска,
offline можно, но не нужно»; C2ME - не причина, а контекст; числа 30 683 (копия) и 30 723 (боевой);
пример `Found transformer services` теперь с сервисом. После правок навык 210 строк.

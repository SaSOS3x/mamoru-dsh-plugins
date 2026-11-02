# Задача: генерация Stonewright медленнее с каждой минутой

Сборка: Minecraft 1.21.1, NeoForge 21.1.264, Sinytra Connector 2.0.0-beta.17, C2ME 0.4.0-alpha.0.123. Мод Stonewright 3.0.2
(Fabric, через Connector) строит каменные террасы вокруг своих деревень. Пользователь пишет свой NeoForge-мод с миксинами
(ModDevGradle, MixinExtras есть в NeoForge).

Замеры: прогрузка Chunky (16 641 чанк, свежая копия мира): 512, 509, 515 с. Скорость падает по ходу прогона: первые 2 минуты
55 чанков/с, к концу 30. Профиль spark рабочих потоков C2ME (`--thread c2me-worker-.* --regex`, с 4-й по 5-ю минуту прогона):

```
self time, c2me-worker (x5):
  18.1%  com.stonewright.gen.TerraceRegistry.sample
   9.7%  net.minecraft.world.level.levelgen.synth.ImprovedNoise.noise
   7.9%  net.minecraft.world.level.levelgen.Aquifer$NoiseBasedAquifer.computeSubstance
   ...
callers of TerraceRegistry.sample:  NoiseChunk.handler$stonewright$addTerraces <- NoiseChunk.computeDensity (per noise sample)
```

Байткод (javap по `.cache/connector/stonewright-3.0.2_mapped_moj_1.21.1.jar`):

```java
public final class TerraceRegistry {
    private static volatile TerraceArea[] AREAS = new TerraceArea[0];   // add(): copy-on-write под локом, clear() при старте сервера
    public static double sample(int x, int y, int z) {
        TerraceArea[] arr = AREAS;
        double s = 0.0;
        for (TerraceArea a : arr) s += a.weight(x, y, z);
        return s;
    }
}
public final class TerraceArea {           // add() зовётся из конструктора куска деревни: при генерации и при загрузке из NBT
    public final int minX, minZ, maxX, maxZ, topY, falloff;   // falloff >= 1
    public double weight(int x, int y, int z) {
        int dx = x < minX ? minX - x : (x > maxX ? x - maxX : 0);
        int dz = z < minZ ? minZ - z : (z > maxZ ? z - maxZ : 0);
        if (dx >= falloff || dz >= falloff) return 0.0;
        double d = Math.sqrt(dx * dx + dz * dz) / falloff;
        return Math.exp(-3.0 * d * d) * Math.exp(-0.25 * Math.abs(y - topY));
    }
}
```

Конфига у Stonewright нет. Коллега в чате пишет: "миксином сюда не влезть: `TerraceArea` - класс Fabric-мода, в NeoForge-проекте
его нет на classpath, придётся рефлексией читать поля на каждый вызов".

Пользователь просит: как исправить, не меняя ни одного блока террас (мир уже частично сгенерирован), как доказать, что рельеф не
изменился, какой выигрыш ждать и как его честно измерить.

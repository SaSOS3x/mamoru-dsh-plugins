# Rewriting the noise router in Java (custom world geometry)

Verified in the Space Journey project (MC 1.21.1, NeoForge 21.1.250), 2026-10-14..21: one experiment and two later
implementations of the same remap, checked by comparing heights across the seams. One project, one line of work: re-check
on another one.

- `RandomState.create(...).router()` keeps cache markers around nodes (shift_x is `Marker(flat_cache, Marker(cache_2d,
  ShiftA))`): unwrap through the public interface `DensityFunctions.MarkerOrMarked` (`wrapped()`), not by class.
- `DensityFunctions.Noise`, `ShiftedNoise`, `Shift`, `ShiftA`, `ShiftB`, `WeirdScaledSampler` and `Marker` are protected
  records, and NeoForge's own AT opens none of them: reading their fields needs your `META-INF/accesstransformer.cfg`
  (`public net.minecraft.world.level.levelgen.DensityFunctions$Noise` and so on; `Marker` needs no line when you unwrap
  through `MarkerOrMarked`). `javap` without `-v` prints them as `public final class`: the real access is only in the
  `InnerClasses` attribute (`javap -v`).
- Nodes that read block coordinates themselves: Noise, ShiftedNoise, Shift*, BlendedNoise, WeirdScaledSampler (spaghetti
  caves), YClampedGradient (Y only). A remap that misses one leaves a seam (a missed WeirdScaledSampler: cave entrances did
  not meet at the edges).
- Make the walk throw on an unknown node and on a null lookup: a silent null fallback hid an unshifted climate for a whole
  run.
- A generator subclass: `NoiseBasedChunkGenerator` is final in vanilla, NeoForge's AT makes it `public-f`. Its codec writes a
  reference to the original `noise_settings`, not your nodes (found in code review: saving the world would fail on them).
  Surface rules, carvers and aquifers read storage coordinates past the router: this remap does not move them.

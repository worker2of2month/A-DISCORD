# Stelander portraits

The PNG sources are supplied artwork at 156x210. Runtime static portraits are
copied byte-for-byte by `tools.builders.build_adiscord_stp_portraits`.

- `portrait_STP_Petr_Ivanov.png`: civilian portrait and glitch source.
- `portrait_NOD_STS_administrator.png`: Nodrul hegemony administration.
- `portrait_VAL_STS_administrator.png`: Kefreyt hegemony administration.
- `portrait_STP_northern_administrator.png`: unified northern administration.

The animation has 52 horizontal frames at 12 fps. Both the leader portrait and
state-face panel use `gfx/leaders/STP/ivanov_glitch_animation.dds`. Quiet frames
and the loop seam retain the source pixels; glitches displace short horizontal
bands and colour channels while preserving source alpha. The GIF preview lives
in `docs/development/previews/ivanov-glitch.gif`.

Run the builder as a module with `--check`, then `--apply`, then `--check`.
The DDS dimensions and sprite frame counts must agree. A native cold-load check
is required to confirm playback and the portrait switch at Ivanov's final stage.

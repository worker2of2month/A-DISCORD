# A-Discord Vorkerland Party Texticons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ten detailed 25×25 party emblems and event-driven WRK/independent party identity switching for IVN, TVA, VAD, ZAO, PWR, VLA, ROM, SOL, and TRU.

**Architecture:** Store approved transparent master art under `tools/assets/source/party_texticons/` and make a deterministic Pillow builder the exclusive owner of the ten runtime PNGs. Keep display text in BOM-preserving Russian localisation, declare sprites in the existing party texticon registry, and use one country-scoped `set_party_name` synchronizer plus bounded startup/collapse/autonomy entry points. Put the party-specific autonomy listeners in a new on-action file so the feature composes with the existing dirty collapse hooks without copying their cleanup logic.

**Tech Stack:** HOI4 Clausewitz script, HOI4 GFX texticons, UTF-8-BOM YAML localisation, Python 3, Pillow, `unittest`, repository validators, built-in `imagegen`.

## Global Constraints

- Treat [the approved design](../specs/2026-08-16-adiscord-vorkerland-party-texticons-design.md) as the source of truth.
- VAD, ZAO, PWR, VLA, ROM, SOL, and TRU use the exact existing `GFX_WRK_worker_revolutionary_party_texticon` only while they are subjects of WRK or WKR.
- A subject of any other country keeps its independent party emblem.
- Generate exactly ten new unique emblems; NAM and DAN remain outside scope.
- Runtime PNGs are exactly 25×25 RGBA with transparent padding, no text, letters, numbers, signatures, or watermarks.
- The art must remain ornate and heraldic like the current WRK, STP, VAL, and military VAD references while keeping one readable dominant silhouette.
- Use built-in `imagegen` after loading the `imagegen` skill; do not substitute an external CLI or another image model without user approval.
- Use `set_party_name`; do not change ideology, popularity, elections, or leaders.
- Use fresh-campaign initialization and bounded collapse/autonomy hooks; do not add daily, weekly, monthly, or global polling and do not add old-save migration.
- Preserve the UTF-8 BOM in every edited Russian localisation file.
- Preserve unrelated dirty work. Before every edit and stage operation, inspect the exact paths. Commit steps are conditional: skip a commit if an exact staged diff would include pre-existing user changes.
- Do not launch HOI4 unless the user explicitly authorizes it. Static success is not runtime proof.

## File Map

- Create `tools/builders/build_adiscord_party_texticons.py`: deterministic source-to-runtime renderer and check/apply CLI.
- Create `tools/build_adiscord_party_texticons.py`: compatibility entry point.
- Create `tools/tests/test_build_adiscord_party_texticons.py`: builder, size, alpha, drift, and determinism contract.
- Create `tools/tests/test_adiscord_party_texticons.py`: sprite, localisation, state-machine, and lifecycle contract.
- Create ten files below `tools/assets/source/party_texticons/`: approved transparent high-resolution masters.
- Create ten files below `gfx/texticons/adiscord/parties/<TAG>/`: generator-owned 25×25 runtime icons.
- Modify `tools/data/generated_output_owners.json`: register exclusive ownership and pipeline order.
- Modify `tools/tests/test_generated_output_ownership.py`: add `party_texticons` to the required family set.
- Modify `interface/parties_texticons.gfx`: declare the ten new texticon sprites.
- Modify `localisation/russian/parties_l_russian.yml`: IVN identities and WRK/independent helper keys for the seven successor countries.
- Modify `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml`: TVA wartime party short and long names.
- Create `common/scripted_effects/ADISCORD_vorkerland_party_identity_effects.txt`: country-scoped and all-country synchronizers.
- Create `common/on_actions/05_ADISCORD_vorkerland_party_identity_on_actions.txt`: `on_puppet`, `on_release_as_puppet`, and `on_release_as_free` listeners.
- Modify `history/countries/WRK - WorkerLand.txt`: initialize the seven dependency identities after autonomy is assigned.
- Modify `events/ADISCORD_vorkerland_collapse_events.txt`: synchronize all seven identities immediately after claimant cosmetics are applied.

---

### Task 1: Generate and Own the Ten Runtime Icons

**Files:**
- Create: `tools/builders/build_adiscord_party_texticons.py`
- Create: `tools/build_adiscord_party_texticons.py`
- Create: `tools/tests/test_build_adiscord_party_texticons.py`
- Create: `tools/assets/source/party_texticons/IVN_roar_of_freedom_source.png`
- Create: `tools/assets/source/party_texticons/IVN_emergency_committee_source.png`
- Create: `tools/assets/source/party_texticons/TVA_wartime_technocratic_worker_source.png`
- Create: `tools/assets/source/party_texticons/VAD_vorkerland_imperial_source.png`
- Create: `tools/assets/source/party_texticons/ZAO_independent_party_source.png`
- Create: `tools/assets/source/party_texticons/PWR_independent_party_source.png`
- Create: `tools/assets/source/party_texticons/VLA_independent_party_source.png`
- Create: `tools/assets/source/party_texticons/ROM_independent_party_source.png`
- Create: `tools/assets/source/party_texticons/SOL_independent_party_source.png`
- Create: `tools/assets/source/party_texticons/TRU_independent_party_source.png`
- Create: `gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png`
- Create: `gfx/texticons/adiscord/parties/IVN/IVN_emergency_committee_party.png`
- Create: `gfx/texticons/adiscord/parties/TVA/TVA_wartime_technocratic_worker_party.png`
- Create: `gfx/texticons/adiscord/parties/VAD/VAD_vorkerland_imperial_party.png`
- Create: `gfx/texticons/adiscord/parties/ZAO/ZAO_independent_party.png`
- Create: `gfx/texticons/adiscord/parties/PWR/PWR_independent_party.png`
- Create: `gfx/texticons/adiscord/parties/VLA/VLA_independent_party.png`
- Create: `gfx/texticons/adiscord/parties/ROM/ROM_independent_party.png`
- Create: `gfx/texticons/adiscord/parties/SOL/SOL_independent_party.png`
- Create: `gfx/texticons/adiscord/parties/TRU/TRU_independent_party.png`
- Modify: `tools/data/generated_output_owners.json`
- Modify: `tools/tests/test_generated_output_ownership.py`

**Interfaces:**
- Consumes: ten user-approved RGBA master PNGs at least 512×512 pixels with transparent background.
- Produces: `AssetSpec`, `ASSETS`, `render_icon(source: Path) -> bytes`, `expected_outputs(root: Path = ROOT) -> dict[Path, bytes]`, `drift(root: Path = ROOT) -> list[str]`, and `apply(root: Path = ROOT) -> None`.
- Produces: ten deterministic 25×25 RGBA runtime icons consumed by `interface/parties_texticons.gfx` in Task 2.

- [ ] **Step 1: Write the failing builder tests**

Create `tools/tests/test_build_adiscord_party_texticons.py` with the complete approved asset manifest and renderer contract:

```python
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.builders import build_adiscord_party_texticons as builder


EXPECTED_KEYS = {
    "ivn_roar_of_freedom",
    "ivn_emergency_committee",
    "tva_wartime_technocratic_worker",
    "vad_vorkerland_imperial",
    "zao_independent_party",
    "pwr_independent_party",
    "vla_independent_party",
    "rom_independent_party",
    "sol_independent_party",
    "tru_independent_party",
}


class PartyTexticonBuilderTests(unittest.TestCase):
    def test_manifest_covers_exactly_the_ten_approved_icons(self) -> None:
        self.assertEqual({asset.key for asset in builder.ASSETS}, EXPECTED_KEYS)
        self.assertEqual(len(builder.ASSETS), 10)
        self.assertEqual(len({asset.source for asset in builder.ASSETS}), 10)
        self.assertEqual(len({asset.output for asset in builder.ASSETS}), 10)

    def test_render_icon_is_deterministic_25px_rgba_with_clear_padding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.png"
            image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.ellipse((72, 36, 440, 476), fill=(190, 30, 20, 255))
            image.save(source)
            first = builder.render_icon(source)
            second = builder.render_icon(source)
            self.assertEqual(first, second)
            with Image.open(io.BytesIO(first)) as rendered:
                self.assertEqual(rendered.mode, "RGBA")
                self.assertEqual(rendered.size, (25, 25))
                self.assertIsNotNone(rendered.getchannel("A").getbbox())
                for corner in ((0, 0), (24, 0), (0, 24), (24, 24)):
                    self.assertEqual(rendered.getpixel(corner)[3], 0)

    def test_runtime_outputs_are_current(self) -> None:
        self.assertEqual(builder.drift(), [])
        for asset in builder.ASSETS:
            with self.subTest(asset=asset.key), Image.open(builder.ROOT / asset.output) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (25, 25))
                self.assertIsNotNone(image.getchannel("A").getbbox())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the builder test and verify the expected failure**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_party_texticons -v
```

Expected: `ERROR` because `tools.builders.build_adiscord_party_texticons` does not exist.

- [ ] **Step 3: Implement the deterministic builder and wrapper**

Create `tools/builders/build_adiscord_party_texticons.py` with this implementation:

```python
"""Build the generated A-Discord party texticons from transparent masters."""

from __future__ import annotations

import argparse
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AssetSpec:
    key: str
    source: Path
    output: Path


ASSETS = (
    AssetSpec("ivn_roar_of_freedom", Path("tools/assets/source/party_texticons/IVN_roar_of_freedom_source.png"), Path("gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png")),
    AssetSpec("ivn_emergency_committee", Path("tools/assets/source/party_texticons/IVN_emergency_committee_source.png"), Path("gfx/texticons/adiscord/parties/IVN/IVN_emergency_committee_party.png")),
    AssetSpec("tva_wartime_technocratic_worker", Path("tools/assets/source/party_texticons/TVA_wartime_technocratic_worker_source.png"), Path("gfx/texticons/adiscord/parties/TVA/TVA_wartime_technocratic_worker_party.png")),
    AssetSpec("vad_vorkerland_imperial", Path("tools/assets/source/party_texticons/VAD_vorkerland_imperial_source.png"), Path("gfx/texticons/adiscord/parties/VAD/VAD_vorkerland_imperial_party.png")),
    AssetSpec("zao_independent_party", Path("tools/assets/source/party_texticons/ZAO_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/ZAO/ZAO_independent_party.png")),
    AssetSpec("pwr_independent_party", Path("tools/assets/source/party_texticons/PWR_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/PWR/PWR_independent_party.png")),
    AssetSpec("vla_independent_party", Path("tools/assets/source/party_texticons/VLA_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/VLA/VLA_independent_party.png")),
    AssetSpec("rom_independent_party", Path("tools/assets/source/party_texticons/ROM_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/ROM/ROM_independent_party.png")),
    AssetSpec("sol_independent_party", Path("tools/assets/source/party_texticons/SOL_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/SOL/SOL_independent_party.png")),
    AssetSpec("tru_independent_party", Path("tools/assets/source/party_texticons/TRU_independent_party_source.png"), Path("gfx/texticons/adiscord/parties/TRU/TRU_independent_party.png")),
)


def render_icon(source: Path) -> bytes:
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        if min(rgba.size) < 512:
            raise RuntimeError(f"party texticon master must be at least 512px: {source}")
        alpha = rgba.getchannel("A")
        if alpha.getextrema() == (255, 255):
            raise RuntimeError(f"party texticon master lacks transparency: {source}")
        bbox = alpha.getbbox()
        if bbox is None:
            raise RuntimeError(f"party texticon master is fully transparent: {source}")
        cropped = rgba.crop(bbox)
        cropped.thumbnail((23, 23), Image.Resampling.LANCZOS)
        cropped = cropped.filter(ImageFilter.UnsharpMask(radius=0.55, percent=115, threshold=2))
        canvas = Image.new("RGBA", (25, 25), (0, 0, 0, 0))
        canvas.alpha_composite(cropped, ((25 - cropped.width) // 2, (25 - cropped.height) // 2))
        output = io.BytesIO()
        canvas.save(output, format="PNG", optimize=False, compress_level=9)
        return output.getvalue()


def expected_outputs(root: Path = ROOT) -> dict[Path, bytes]:
    return {root / asset.output: render_icon(root / asset.source) for asset in ASSETS}


def drift(root: Path = ROOT) -> list[str]:
    problems = []
    for output, expected in expected_outputs(root).items():
        if not output.is_file() or output.read_bytes() != expected:
            problems.append(str(output.relative_to(root)))
    return problems


def apply(root: Path = ROOT) -> None:
    for output, expected in expected_outputs(root).items():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate generated icons (default)")
    actions.add_argument("--apply", action="store_true", help="write generated icons")
    args = parser.parse_args()
    if args.apply:
        apply()
        print("Built 10 party texticons.")
        return 0
    problems = drift()
    if problems:
        print("Party texticon drift: " + ", ".join(problems))
        return 1
    print("Party texticons are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `tools/build_adiscord_party_texticons.py`:

```python
"""Compatibility facade for the party-texticon asset builder."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.builders.build_adiscord_party_texticons import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Generate the ten transparent masters with built-in imagegen**

Load the `imagegen` skill. Generate one emblem per call so each result can be judged independently. Use this common suffix in every prompt:

```text
Single centered alternate-history political party emblem, intricate miniature heraldic medal, bold readable silhouette designed to survive at 25 by 25 pixels, thick dark outer contour, layered enamel and aged metal, subtle highlights and shadows, symmetrical compact composition, no text, no letters, no numbers, no signature, no watermark, no rectangular flag, isolated on a flat chroma-key background.
```

Use these exact subject prompts before the common suffix:

| Source | Subject prompt | Chroma key |
| --- | --- | --- |
| `IVN_roar_of_freedom_source.png` | Silver roaring heraldic lion breaking a gold chain over deep-green rays; hopeful civilian revolutionary energy, not a military badge. | pure magenta |
| `IVN_emergency_committee_source.png` | Dark-green emergency state seal, fortified shield, upright steel sword, restrained gold state ornament, severe and defensive. | pure magenta |
| `TVA_wartime_technocratic_worker_source.png` | Teal industrial cog enclosing a worker hammer and precise lightning-circuit motif, steel wartime technical order. | pure magenta |
| `VAD_vorkerland_imperial_source.png` | Navy-and-gold imperial medallion, compact crown, disciplined radial wings and laurels, strong central state symbol. | pure green |
| `ZAO_independent_party_source.png` | Red-and-gold western administrative crest, fortified rail junction and compact worker motif. | pure green |
| `PWR_independent_party_source.png` | Red-and-gold reconstruction seal, crossed engineering tools, masonry arch and small industrial sun. | pure green |
| `VLA_independent_party_source.png` | Blue-white-gold eastern military crest, winged spear and rising horizon, disciplined but not monarchical. | pure magenta |
| `ROM_independent_party_source.png` | Navy-and-crimson Frealor medallion, compass rose and coastal anchor geometry, dignified republican heraldry. | pure green |
| `SOL_independent_party_source.png` | Orange-and-white Solyarino seal, layered solar disk, turbine blades and central diamond. | pure green |
| `TRU_independent_party_source.png` | Purple-and-orange Zolotorevsk forge badge, faceted diamond, metalworking hammer and red-hot core. | pure green |

For each result, use the imagegen skill's chroma-key removal procedure to remove only border-connected background, inspect the alpha edge, and save a transparent RGBA master at the exact source path. Do not use Python to invent, repaint, or replace the generated emblem.

- [ ] **Step 5: Build the runtime icons and prove idempotence**

Run:

```powershell
python -B -m tools.builders.build_adiscord_party_texticons --apply
Get-FileHash -Algorithm SHA256 gfx/texticons/adiscord/parties/IVN/*.png,gfx/texticons/adiscord/parties/TVA/*.png,gfx/texticons/adiscord/parties/VAD/*.png,gfx/texticons/adiscord/parties/ZAO/*.png,gfx/texticons/adiscord/parties/PWR/*.png,gfx/texticons/adiscord/parties/VLA/*.png,gfx/texticons/adiscord/parties/ROM/*.png,gfx/texticons/adiscord/parties/SOL/*.png,gfx/texticons/adiscord/parties/TRU/*.png
python -B -m tools.builders.build_adiscord_party_texticons --apply
Get-FileHash -Algorithm SHA256 gfx/texticons/adiscord/parties/IVN/*.png,gfx/texticons/adiscord/parties/TVA/*.png,gfx/texticons/adiscord/parties/VAD/*.png,gfx/texticons/adiscord/parties/ZAO/*.png,gfx/texticons/adiscord/parties/PWR/*.png,gfx/texticons/adiscord/parties/VLA/*.png,gfx/texticons/adiscord/parties/ROM/*.png,gfx/texticons/adiscord/parties/SOL/*.png,gfx/texticons/adiscord/parties/TRU/*.png
python -B -m tools.builders.build_adiscord_party_texticons --check
```

Expected: both hash listings are identical and the final command prints `Party texticons are current.`

- [ ] **Step 6: Register generated-output ownership**

Add `party_texticons` once to `apply_sequence`, add it to `REQUIRED_FAMILIES`, and add this family object to `tools/data/generated_output_owners.json`:

```json
{
  "id": "party_texticons",
  "owner_module": "tools.builders.build_adiscord_party_texticons",
  "output_globs": [
    "gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png",
    "gfx/texticons/adiscord/parties/IVN/IVN_emergency_committee_party.png",
    "gfx/texticons/adiscord/parties/TVA/TVA_wartime_technocratic_worker_party.png",
    "gfx/texticons/adiscord/parties/VAD/VAD_vorkerland_imperial_party.png",
    "gfx/texticons/adiscord/parties/ZAO/ZAO_independent_party.png",
    "gfx/texticons/adiscord/parties/PWR/PWR_independent_party.png",
    "gfx/texticons/adiscord/parties/VLA/VLA_independent_party.png",
    "gfx/texticons/adiscord/parties/ROM/ROM_independent_party.png",
    "gfx/texticons/adiscord/parties/SOL/SOL_independent_party.png",
    "gfx/texticons/adiscord/parties/TRU/TRU_independent_party.png"
  ],
  "source_inputs": [
    "tools/builders/build_adiscord_party_texticons.py",
    "tools/assets/source/party_texticons/IVN_roar_of_freedom_source.png",
    "tools/assets/source/party_texticons/IVN_emergency_committee_source.png",
    "tools/assets/source/party_texticons/TVA_wartime_technocratic_worker_source.png",
    "tools/assets/source/party_texticons/VAD_vorkerland_imperial_source.png",
    "tools/assets/source/party_texticons/ZAO_independent_party_source.png",
    "tools/assets/source/party_texticons/PWR_independent_party_source.png",
    "tools/assets/source/party_texticons/VLA_independent_party_source.png",
    "tools/assets/source/party_texticons/ROM_independent_party_source.png",
    "tools/assets/source/party_texticons/SOL_independent_party_source.png",
    "tools/assets/source/party_texticons/TRU_independent_party_source.png"
  ],
  "check_command": ["{python}", "-B", "-m", "tools.builders.build_adiscord_party_texticons"],
  "apply_command": ["{python}", "-B", "-m", "tools.builders.build_adiscord_party_texticons", "--apply"],
  "may_delete_outputs": false,
  "ownership_mode": "exclusive"
}
```

- [ ] **Step 7: Run the focused builder and ownership tests**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_party_texticons tools.tests.test_generated_output_ownership -v
```

Expected: all tests pass.

- [ ] **Step 8: Present the ten visual results for approval**

Open every source master and every 25×25 runtime output with `view_image`. Present the ten runtime icons to the user with absolute image paths, grouped as IVN, civil-war VAD/TVA, and the six other successors. If an emblem loses its silhouette at native size, revise that source with imagegen and repeat Steps 5 and 7 before asking for approval.

- [ ] **Step 9: Record the Task 1 change without capturing user-owned hunks**

Run `git diff -- tools/data/generated_output_owners.json tools/tests/test_generated_output_ownership.py` and compare it to the pre-task baseline. Stage only Task 1 hunks if they are separable, then verify `git diff --cached --name-only` and `git diff --cached --check`. If either shared file would bring pre-existing work into the index, leave Task 1 unstaged and report that safety decision; do not force a commit.

---

### Task 2: Declare Sprites and Russian Party Identities

**Files:**
- Create: `tools/tests/test_adiscord_party_texticons.py`
- Modify: `interface/parties_texticons.gfx:1-27`
- Modify: `localisation/russian/parties_l_russian.yml:288-302,396-520`
- Modify: `localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml:182-188`

**Interfaces:**
- Consumes: the ten output paths from `build_adiscord_party_texticons.ASSETS`.
- Produces: ten `GFX_*_party_texticon` sprite identifiers.
- Produces: static IVN/TVA keys plus dependency and independence helper keys consumed by `ADISCORD_vorkerland_sync_party_identity` in Task 3.

- [ ] **Step 1: Write the failing sprite and localisation contract tests**

Create `tools/tests/test_adiscord_party_texticons.py` with `read(relative)` using `encoding="utf-8-sig"`, then add these constants and tests:

```python
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPRITES = {
    "GFX_IVN_roar_of_freedom_party_texticon": "gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png",
    "GFX_IVN_emergency_committee_party_texticon": "gfx/texticons/adiscord/parties/IVN/IVN_emergency_committee_party.png",
    "GFX_TVA_wartime_technocratic_worker_party_texticon": "gfx/texticons/adiscord/parties/TVA/TVA_wartime_technocratic_worker_party.png",
    "GFX_VAD_vorkerland_imperial_party_texticon": "gfx/texticons/adiscord/parties/VAD/VAD_vorkerland_imperial_party.png",
    "GFX_ZAO_independent_party_texticon": "gfx/texticons/adiscord/parties/ZAO/ZAO_independent_party.png",
    "GFX_PWR_independent_party_texticon": "gfx/texticons/adiscord/parties/PWR/PWR_independent_party.png",
    "GFX_VLA_independent_party_texticon": "gfx/texticons/adiscord/parties/VLA/VLA_independent_party.png",
    "GFX_ROM_independent_party_texticon": "gfx/texticons/adiscord/parties/ROM/ROM_independent_party.png",
    "GFX_SOL_independent_party_texticon": "gfx/texticons/adiscord/parties/SOL/SOL_independent_party.png",
    "GFX_TRU_independent_party_texticon": "gfx/texticons/adiscord/parties/TRU/TRU_independent_party.png",
}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class PartyTexticonContractTests(unittest.TestCase):
    def test_all_new_sprites_resolve_to_generated_icons(self) -> None:
        gfx = read("interface/parties_texticons.gfx")
        for sprite, texture in SPRITES.items():
            with self.subTest(sprite=sprite):
                block = re.search(
                    rf'(?s)spriteType\s*=\s*\{{(?:(?!spriteType).)*name\s*=\s*"{sprite}"(?:(?!spriteType).)*\}}',
                    gfx,
                )
                self.assertIsNotNone(block)
                self.assertIn(f'texturefile = "{texture}"', block.group(0))
                self.assertIn("legacy_lazy_load = no", block.group(0))
                self.assertTrue((ROOT / texture).is_file())

    def test_requested_ivn_and_tva_names_have_unique_icons(self) -> None:
        parties = read("localisation/russian/parties_l_russian.yml")
        collapse = read("localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml")
        self.assertIn('IVN_humanism_party: "£GFX_IVN_roar_of_freedom_party_texticon Рёв свободы"', parties)
        self.assertIn('IVN_etatism_party: "£GFX_IVN_emergency_committee_party_texticon Чрезвычайный комитет Иторы"', parties)
        self.assertIn('TVA_technocracy_party: "£GFX_TVA_wartime_technocratic_worker_party_texticon Технократическо-утилитарная рабочая партия свободного Воркерланда"', collapse)
        self.assertIn('TVA_technocracy_party_long: "£GFX_TVA_wartime_technocratic_worker_party_texticon Технократическо-утилитарная рабочая партия свободного Воркерланда"', collapse)

    def test_successor_helper_keys_cover_dependency_and_independence(self) -> None:
        parties = read("localisation/russian/parties_l_russian.yml")
        for tag in ("VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU"):
            self.assertIn(f"{tag}_pragmatism_party_independent:", parties)
        for key in (
            "VAD_vorkerland_imperial_party",
            "VAD_vorkerland_imperial_party_wrk_subject",
            "PWR_technocracy_party_wrk_subject",
            "ROM_etatism_party_wrk_subject",
            "TRU_chauvinism_party_wrk_subject",
        ):
            self.assertIn(f"{key}:", parties)
        for key in (
            "VAD_pragmatism_party",
            "ZAO_pragmatism_party",
            "PWR_pragmatism_party",
            "VLA_pragmatism_party",
            "ROM_pragmatism_party",
            "SOL_pragmatism_party",
            "TRU_pragmatism_party",
        ):
            line = next(line for line in parties.splitlines() if line.strip().startswith(f"{key}:"))
            self.assertIn("£GFX_WRK_worker_revolutionary_party_texticon", line)

    def test_russian_localisation_files_keep_utf8_bom(self) -> None:
        for relative in (
            "localisation/russian/parties_l_russian.yml",
            "localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml",
        ):
            self.assertTrue((ROOT / relative).read_bytes().startswith(b"\xef\xbb\xbf"), relative)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused contract test and verify the expected failure**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_party_texticons -v
```

Expected: failures for missing sprite declarations and missing or incorrect localisation keys.

- [ ] **Step 3: Declare the ten sprites**

Append these blocks inside `spriteTypes` in `interface/parties_texticons.gfx`:

```text
spriteType = { name = "GFX_IVN_roar_of_freedom_party_texticon" texturefile = "gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png" legacy_lazy_load = no }
spriteType = { name = "GFX_IVN_emergency_committee_party_texticon" texturefile = "gfx/texticons/adiscord/parties/IVN/IVN_emergency_committee_party.png" legacy_lazy_load = no }
spriteType = { name = "GFX_TVA_wartime_technocratic_worker_party_texticon" texturefile = "gfx/texticons/adiscord/parties/TVA/TVA_wartime_technocratic_worker_party.png" legacy_lazy_load = no }
spriteType = { name = "GFX_VAD_vorkerland_imperial_party_texticon" texturefile = "gfx/texticons/adiscord/parties/VAD/VAD_vorkerland_imperial_party.png" legacy_lazy_load = no }
spriteType = { name = "GFX_ZAO_independent_party_texticon" texturefile = "gfx/texticons/adiscord/parties/ZAO/ZAO_independent_party.png" legacy_lazy_load = no }
spriteType = { name = "GFX_PWR_independent_party_texticon" texturefile = "gfx/texticons/adiscord/parties/PWR/PWR_independent_party.png" legacy_lazy_load = no }
spriteType = { name = "GFX_VLA_independent_party_texticon" texturefile = "gfx/texticons/adiscord/parties/VLA/VLA_independent_party.png" legacy_lazy_load = no }
spriteType = { name = "GFX_ROM_independent_party_texticon" texturefile = "gfx/texticons/adiscord/parties/ROM/ROM_independent_party.png" legacy_lazy_load = no }
spriteType = { name = "GFX_SOL_independent_party_texticon" texturefile = "gfx/texticons/adiscord/parties/SOL/SOL_independent_party.png" legacy_lazy_load = no }
spriteType = { name = "GFX_TRU_independent_party_texticon" texturefile = "gfx/texticons/adiscord/parties/TRU/TRU_independent_party.png" legacy_lazy_load = no }
```

Format them as the existing multiline `spriteType` blocks before final verification.

- [ ] **Step 4: Patch the BOM-preserving Russian localisation**

Use the following exact values. Every `_long` helper repeats its matching short icon and uses the current authored long text unless an explicit new party name was requested:

```yaml
IVN_humanism_party: "£GFX_IVN_roar_of_freedom_party_texticon Рёв свободы"
IVN_humanism_party_long: "£GFX_IVN_roar_of_freedom_party_texticon Рёв свободы"
IVN_etatism_party: "£GFX_IVN_emergency_committee_party_texticon Чрезвычайный комитет Иторы"
IVN_etatism_party_long: "£GFX_IVN_emergency_committee_party_texticon Чрезвычайный комитет Иторы"

VAD_pragmatism_party: "£GFX_WRK_worker_revolutionary_party_texticon Окружная администрация Центра"
VAD_pragmatism_party_long: "£GFX_WRK_worker_revolutionary_party_texticon Окружная администрация Центрального округа Конфедерации Воркерланда"
VAD_pragmatism_party_independent: "£GFX_VAD_vorkerland_imperial_party_texticon Окружная администрация Центра"
VAD_pragmatism_party_independent_long: "£GFX_VAD_vorkerland_imperial_party_texticon Окружная администрация Центрального округа Конфедерации Воркерланда"
VAD_vorkerland_imperial_party: "£GFX_VAD_vorkerland_imperial_party_texticon Воркерландская имперская партия"
VAD_vorkerland_imperial_party_long: "£GFX_VAD_vorkerland_imperial_party_texticon Воркерландская имперская партия"
VAD_vorkerland_imperial_party_wrk_subject: "£GFX_WRK_worker_revolutionary_party_texticon Воркерландская имперская партия"
VAD_vorkerland_imperial_party_wrk_subject_long: "£GFX_WRK_worker_revolutionary_party_texticon Воркерландская имперская партия"

ZAO_pragmatism_party: "£GFX_WRK_worker_revolutionary_party_texticon Окружная администрация Запада"
ZAO_pragmatism_party_long: "£GFX_WRK_worker_revolutionary_party_texticon Окружная администрация Западного округа Конфедерации Воркерланда"
ZAO_pragmatism_party_independent: "£GFX_ZAO_independent_party_texticon Окружная администрация Запада"
ZAO_pragmatism_party_independent_long: "£GFX_ZAO_independent_party_texticon Окружная администрация Западного округа Конфедерации Воркерланда"

PWR_pragmatism_party: "£GFX_WRK_worker_revolutionary_party_texticon Дирекция восстановительных подрядов"
PWR_pragmatism_party_long: "£GFX_WRK_worker_revolutionary_party_texticon Дирекция восстановления Западной зоны Конфедерации Воркерланда"
PWR_pragmatism_party_independent: "£GFX_PWR_independent_party_texticon Дирекция восстановительных подрядов"
PWR_pragmatism_party_independent_long: "£GFX_PWR_independent_party_texticon Дирекция восстановления Западной зоны Конфедерации Воркерланда"
PWR_technocracy_party: "£GFX_PWR_independent_party_texticon Корпус инженеров восстановления"
PWR_technocracy_party_long: "£GFX_PWR_independent_party_texticon Корпус инженеров восстановления"
PWR_technocracy_party_wrk_subject: "£GFX_WRK_worker_revolutionary_party_texticon Корпус инженеров восстановления"
PWR_technocracy_party_wrk_subject_long: "£GFX_WRK_worker_revolutionary_party_texticon Корпус инженеров восстановления"

VLA_pragmatism_party: "£GFX_WRK_worker_revolutionary_party_texticon Администрация Восточного округа"
VLA_pragmatism_party_long: "£GFX_WRK_worker_revolutionary_party_texticon Администрация Восточного военного округа Конфедерации Воркерланда"
VLA_pragmatism_party_independent: "£GFX_VLA_independent_party_texticon Администрация Восточного округа"
VLA_pragmatism_party_independent_long: "£GFX_VLA_independent_party_texticon Администрация Восточного военного округа Конфедерации Воркерланда"

ROM_pragmatism_party: "£GFX_WRK_worker_revolutionary_party_texticon Блок сотрудничества Фреалора"
ROM_pragmatism_party_long: "£GFX_WRK_worker_revolutionary_party_texticon Блок сотрудничества Республики Фреалор с Конфедерацией Воркерланда"
ROM_pragmatism_party_independent: "£GFX_ROM_independent_party_texticon Блок сотрудничества Фреалора"
ROM_pragmatism_party_independent_long: "£GFX_ROM_independent_party_texticon Блок сотрудничества Республики Фреалор с Конфедерацией Воркерланда"
ROM_etatism_party: "£GFX_ROM_independent_party_texticon Автономная Директория Фреалора"
ROM_etatism_party_long: "£GFX_ROM_independent_party_texticon Автономная Директория Фреалора"
ROM_etatism_party_wrk_subject: "£GFX_WRK_worker_revolutionary_party_texticon Автономная Директория Фреалора"
ROM_etatism_party_wrk_subject_long: "£GFX_WRK_worker_revolutionary_party_texticon Автономная Директория Фреалора"

SOL_pragmatism_party: "£GFX_WRK_worker_revolutionary_party_texticon Блок сотрудничества Солярино"
SOL_pragmatism_party_long: "£GFX_WRK_worker_revolutionary_party_texticon Блок сотрудничества Республики Солярино с Конфедерацией Воркерланда"
SOL_pragmatism_party_independent: "£GFX_SOL_independent_party_texticon Блок сотрудничества Солярино"
SOL_pragmatism_party_independent_long: "£GFX_SOL_independent_party_texticon Блок сотрудничества Республики Солярино с Конфедерацией Воркерланда"

TRU_pragmatism_party: "£GFX_WRK_worker_revolutionary_party_texticon Блок сотрудничества Золоторевска"
TRU_pragmatism_party_long: "£GFX_WRK_worker_revolutionary_party_texticon Блок сотрудничества Республики Золоторевск с Конфедерацией Воркерланда"
TRU_pragmatism_party_independent: "£GFX_TRU_independent_party_texticon Блок сотрудничества Золоторевска"
TRU_pragmatism_party_independent_long: "£GFX_TRU_independent_party_texticon Блок сотрудничества Республики Золоторевск с Конфедерацией Воркерланда"
TRU_chauvinism_party: "£GFX_TRU_independent_party_texticon Золоторевский Фронт"
TRU_chauvinism_party_long: "£GFX_TRU_independent_party_texticon Золоторевский Фронт"
TRU_chauvinism_party_wrk_subject: "£GFX_WRK_worker_revolutionary_party_texticon Золоторевский Фронт"
TRU_chauvinism_party_wrk_subject_long: "£GFX_WRK_worker_revolutionary_party_texticon Золоторевский Фронт"
```

Add these TVA keys to the collapse localisation file:

```yaml
TVA_technocracy_party: "£GFX_TVA_wartime_technocratic_worker_party_texticon Технократическо-утилитарная рабочая партия свободного Воркерланда"
TVA_technocracy_party_long: "£GFX_TVA_wartime_technocratic_worker_party_texticon Технократическо-утилитарная рабочая партия свободного Воркерланда"
```

- [ ] **Step 5: Verify localisation encoding and pass the focused test**

Run:

```powershell
$paths = @('localisation/russian/parties_l_russian.yml','localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml')
foreach ($path in $paths) { $bytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $path)); if ($bytes.Length -lt 3 -or $bytes[0] -ne 0xEF -or $bytes[1] -ne 0xBB -or $bytes[2] -ne 0xBF) { throw "Missing UTF-8 BOM: $path" } }
python -B -m unittest tools.tests.test_adiscord_party_texticons -v
```

Expected: BOM check is silent and all tests pass.

- [ ] **Step 6: Commit only if the exact Task 2 paths are cleanly owned**

Inspect `git diff --` for the four Task 2 paths, stage only those paths, run `git diff --cached --check`, and commit with `feat: add Vorkerland party texticons`. If any path gained unrelated edits after the baseline, leave it unstaged and do not create a partial commit that depends on missing assets or localisation.

---

### Task 3: Implement the Event-Driven Party Identity State Machine

**Files:**
- Create: `common/scripted_effects/ADISCORD_vorkerland_party_identity_effects.txt`
- Create: `common/on_actions/05_ADISCORD_vorkerland_party_identity_on_actions.txt`
- Modify: `history/countries/WRK - WorkerLand.txt:68-109`
- Modify: `events/ADISCORD_vorkerland_collapse_events.txt:118-127`
- Modify: `tools/tests/test_adiscord_party_texticons.py`

**Interfaces:**
- Consumes: the localisation helper keys from Task 2.
- Produces: `ADISCORD_vorkerland_sync_party_identity = yes`, valid only in a VAD/ZAO/PWR/VLA/ROM/SOL/TRU country scope.
- Produces: `ADISCORD_vorkerland_sync_all_party_identities = yes`, callable from any country scope.
- Produces: bounded calls from fresh history setup, collapse setup, and the three autonomy on-actions.

- [ ] **Step 1: Add failing lifecycle tests**

Extend `tools/tests/test_adiscord_party_texticons.py` with a brace-aware `named_block` helper and these tests:

```python
def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block {name}")
    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start():index + 1]
    raise AssertionError(f"unclosed block {name}")


class PartyIdentityLifecycleTests(unittest.TestCase):
    def test_sync_effect_covers_exact_successors_and_never_changes_politics(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_party_identity_effects.txt")
        sync = named_block(effects, "ADISCORD_vorkerland_sync_party_identity")
        self.assertEqual(set(re.findall(r"\btag\s*=\s*([A-Z]{3})", sync)), {"VAD", "ZAO", "PWR", "VLA", "ROM", "SOL", "TRU"})
        self.assertIn("OR = { is_subject_of = WRK is_subject_of = WKR }", sync)
        self.assertIn("has_global_flag = ADISCORD_vorkerland_collapse_started", sync)
        for ideology in ("pragmatism", "technocracy", "etatism", "chauvinism"):
            self.assertIn(f"ideology = {ideology}", sync)
        for forbidden in ("set_politics", "set_popularities", "add_popularity", "elections_allowed", "promote_character", "country_leader"):
            self.assertNotIn(forbidden, sync)
        self.assertNotIn("tag = NAM", sync)
        self.assertNotIn("tag = DAN", sync)

    def test_fresh_collapse_and_autonomy_entry_points_are_bounded(self) -> None:
        history = read("history/countries/WRK - WorkerLand.txt")
        events = read("events/ADISCORD_vorkerland_collapse_events.txt")
        on_actions = read("common/on_actions/05_ADISCORD_vorkerland_party_identity_on_actions.txt")
        self.assertIn("ADISCORD_vorkerland_sync_all_party_identities = yes", history)
        apply_cosmetics = events.index("ADISCORD_vorkerland_apply_claimant_cosmetics = yes")
        sync_parties = events.index("ADISCORD_vorkerland_sync_all_party_identities = yes", apply_cosmetics)
        repair_identities = events.index("ADISCORD_vorkerland_repair_claimant_identities = yes", apply_cosmetics)
        self.assertLess(apply_cosmetics, sync_parties)
        self.assertLess(sync_parties, repair_identities)
        for hook in ("on_puppet", "on_release_as_puppet", "on_release_as_free"):
            block = named_block(on_actions, hook)
            self.assertIn("ADISCORD_vorkerland_sync_party_identity = yes", block)
        for recurring in ("on_daily", "on_weekly", "on_monthly"):
            self.assertNotIn(recurring, on_actions)
```

- [ ] **Step 2: Run the lifecycle tests and verify the expected failure**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_party_texticons.PartyIdentityLifecycleTests -v
```

Expected: failures because the scripted effects and on-action file do not exist and the two entry-point calls are absent.

- [ ] **Step 3: Create the party identity scripted effects**

Create `common/scripted_effects/ADISCORD_vorkerland_party_identity_effects.txt`. Use the following complete state machine; format each `set_party_name` as a multiline block in the final file:

```text
ADISCORD_vorkerland_sync_party_identity = {
    if = {
        limit = { tag = VAD }
        if = {
            limit = { OR = { is_subject_of = WRK is_subject_of = WKR } }
            if = {
                limit = { has_global_flag = ADISCORD_vorkerland_collapse_started }
                set_party_name = { ideology = pragmatism name = VAD_vorkerland_imperial_party_wrk_subject long_name = VAD_vorkerland_imperial_party_wrk_subject_long }
            }
            else = { set_party_name = { ideology = pragmatism name = VAD_pragmatism_party long_name = VAD_pragmatism_party_long } }
        }
        else_if = {
            limit = { has_global_flag = ADISCORD_vorkerland_collapse_started }
            set_party_name = { ideology = pragmatism name = VAD_vorkerland_imperial_party long_name = VAD_vorkerland_imperial_party_long }
        }
        else = { set_party_name = { ideology = pragmatism name = VAD_pragmatism_party_independent long_name = VAD_pragmatism_party_independent_long } }
    }
    else_if = {
        limit = { tag = ZAO }
        if = {
            limit = { OR = { is_subject_of = WRK is_subject_of = WKR } }
            set_party_name = { ideology = pragmatism name = ZAO_pragmatism_party long_name = ZAO_pragmatism_party_long }
        }
        else = { set_party_name = { ideology = pragmatism name = ZAO_pragmatism_party_independent long_name = ZAO_pragmatism_party_independent_long } }
    }
    else_if = {
        limit = { tag = PWR }
        if = {
            limit = { OR = { is_subject_of = WRK is_subject_of = WKR } }
            set_party_name = { ideology = pragmatism name = PWR_pragmatism_party long_name = PWR_pragmatism_party_long }
            set_party_name = { ideology = technocracy name = PWR_technocracy_party_wrk_subject long_name = PWR_technocracy_party_wrk_subject_long }
        }
        else = {
            set_party_name = { ideology = pragmatism name = PWR_pragmatism_party_independent long_name = PWR_pragmatism_party_independent_long }
            set_party_name = { ideology = technocracy name = PWR_technocracy_party long_name = PWR_technocracy_party_long }
        }
    }
    else_if = {
        limit = { tag = VLA }
        if = {
            limit = { OR = { is_subject_of = WRK is_subject_of = WKR } }
            set_party_name = { ideology = pragmatism name = VLA_pragmatism_party long_name = VLA_pragmatism_party_long }
        }
        else = { set_party_name = { ideology = pragmatism name = VLA_pragmatism_party_independent long_name = VLA_pragmatism_party_independent_long } }
    }
    else_if = {
        limit = { tag = ROM }
        if = {
            limit = { OR = { is_subject_of = WRK is_subject_of = WKR } }
            set_party_name = { ideology = pragmatism name = ROM_pragmatism_party long_name = ROM_pragmatism_party_long }
            set_party_name = { ideology = etatism name = ROM_etatism_party_wrk_subject long_name = ROM_etatism_party_wrk_subject_long }
        }
        else = {
            set_party_name = { ideology = pragmatism name = ROM_pragmatism_party_independent long_name = ROM_pragmatism_party_independent_long }
            set_party_name = { ideology = etatism name = ROM_etatism_party long_name = ROM_etatism_party_long }
        }
    }
    else_if = {
        limit = { tag = SOL }
        if = {
            limit = { OR = { is_subject_of = WRK is_subject_of = WKR } }
            set_party_name = { ideology = pragmatism name = SOL_pragmatism_party long_name = SOL_pragmatism_party_long }
        }
        else = { set_party_name = { ideology = pragmatism name = SOL_pragmatism_party_independent long_name = SOL_pragmatism_party_independent_long } }
    }
    else_if = {
        limit = { tag = TRU }
        if = {
            limit = { OR = { is_subject_of = WRK is_subject_of = WKR } }
            set_party_name = { ideology = pragmatism name = TRU_pragmatism_party long_name = TRU_pragmatism_party_long }
            set_party_name = { ideology = chauvinism name = TRU_chauvinism_party_wrk_subject long_name = TRU_chauvinism_party_wrk_subject_long }
        }
        else = {
            set_party_name = { ideology = pragmatism name = TRU_pragmatism_party_independent long_name = TRU_pragmatism_party_independent_long }
            set_party_name = { ideology = chauvinism name = TRU_chauvinism_party long_name = TRU_chauvinism_party_long }
        }
    }
}

ADISCORD_vorkerland_sync_all_party_identities = {
    VAD = { ADISCORD_vorkerland_sync_party_identity = yes }
    ZAO = { ADISCORD_vorkerland_sync_party_identity = yes }
    PWR = { ADISCORD_vorkerland_sync_party_identity = yes }
    VLA = { ADISCORD_vorkerland_sync_party_identity = yes }
    ROM = { ADISCORD_vorkerland_sync_party_identity = yes }
    SOL = { ADISCORD_vorkerland_sync_party_identity = yes }
    TRU = { ADISCORD_vorkerland_sync_party_identity = yes }
}
```

- [ ] **Step 4: Add the three bounded autonomy callbacks**

Create `common/on_actions/05_ADISCORD_vorkerland_party_identity_on_actions.txt`:

```text
on_actions = {
    on_puppet = {
        effect = {
            if = {
                limit = { OR = { tag = VAD tag = ZAO tag = PWR tag = VLA tag = ROM tag = SOL tag = TRU } }
                ADISCORD_vorkerland_sync_party_identity = yes
            }
        }
    }
    on_release_as_puppet = {
        effect = {
            if = {
                limit = { OR = { tag = VAD tag = ZAO tag = PWR tag = VLA tag = ROM tag = SOL tag = TRU } }
                ADISCORD_vorkerland_sync_party_identity = yes
            }
        }
    }
    on_release_as_free = {
        effect = {
            if = {
                limit = { OR = { tag = VAD tag = ZAO tag = PWR tag = VLA tag = ROM tag = SOL tag = TRU } }
                ADISCORD_vorkerland_sync_party_identity = yes
            }
        }
    }
}
```

This file adds only party identity reactions. It does not copy the claimant, cosmetic, diplomacy, or premature-WRK cleanup from the existing on-action files.

- [ ] **Step 5: Wire fresh-campaign and collapse initialization**

In `history/countries/WRK - WorkerLand.txt`, add this immediately after all starting `set_autonomy` blocks and before `set_convoys`:

```text
# Party texticons are initialized only while country history creates a fresh campaign.
ADISCORD_vorkerland_sync_all_party_identities = yes
```

In `events/ADISCORD_vorkerland_collapse_events.txt`, add this between claimant cosmetics and claimant identity repair:

```text
ADISCORD_vorkerland_apply_claimant_cosmetics = yes
ADISCORD_vorkerland_sync_all_party_identities = yes
ADISCORD_vorkerland_repair_claimant_identities = yes
```

The event already sets `ADISCORD_vorkerland_collapse_started` before this point, so VAD receives the imperial party name in the same collapse tick.

- [ ] **Step 6: Pass the lifecycle, collapse, and no-polling tests**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_party_texticons -v
python -B -m unittest tools.tests.test_validate_adiscord_vorkerland_collapse -v
python -B tools/validate_adiscord_vorkerland_collapse.py
```

Expected: all tests pass and the validator prints `Vorkerland collapse validation passed.`

- [ ] **Step 7: Commit only a complete, ownership-safe state-machine change**

Inspect every Task 3 path against the pre-task baseline. Stage the two new files and the exact clean history/event hunks only if doing so produces a self-contained state machine. Run `git diff --cached --check` and inspect the full cached diff. If any dependency remains unstaged or any user-owned hunk would enter the commit, leave Task 3 unstaged and report it instead of committing an incomplete change.

---

### Task 4: Run Static Release Gates and Prepare the Runtime Check

**Files:**
- Verify only; no source file is created or modified by this task.

**Interfaces:**
- Consumes: all Task 1-3 outputs.
- Produces: static verification evidence and a fresh-campaign runtime checklist.

- [ ] **Step 1: Verify generator drift, dimensions, alpha, and idempotence**

Run:

```powershell
python -B -m tools.builders.build_adiscord_party_texticons --check
python -B -m unittest tools.tests.test_build_adiscord_party_texticons -v
```

Expected: builder reports current outputs and all ten asset tests pass.

- [ ] **Step 2: Run the complete focused contract suite**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_party_texticons tools.tests.test_wrk_party_icon tools.tests.test_validate_adiscord_vorkerland_collapse -v
python -B tools/validate_adiscord_vorkerland_collapse.py
```

Expected: all tests pass and the collapse validator passes.

- [ ] **Step 3: Run repository-wide static gates**

Run:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Expected: validator exits zero and both diff checks emit no errors. If `validate_tc.py` reports a failure in an unrelated dirty subsystem, rerun the focused gates, record the exact unrelated failure, and do not claim the repository-wide gate passed.

- [ ] **Step 4: Recheck Russian BOMs and scoped ownership**

Run:

```powershell
$paths = @('localisation/russian/parties_l_russian.yml','localisation/russian/ADISCORD_vorkerland_collapse_l_russian.yml')
foreach ($path in $paths) { $bytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $path)); if ($bytes[0] -ne 0xEF -or $bytes[1] -ne 0xBB -or $bytes[2] -ne 0xBF) { throw "Missing UTF-8 BOM: $path" } }
git status --short
```

Expected: both BOM checks pass. Compare the final status with the initial baseline and report only paths changed by this feature.

- [ ] **Step 5: Present the runtime smoke checklist without claiming it ran**

Unless the user explicitly authorizes launching HOI4, report static completion and provide this fresh-campaign checklist:

1. Start a fresh campaign after a full HOI4 restart.
2. Confirm VAD, ZAO, PWR, VLA, ROM, SOL, and TRU show the exact WRK emblem while subject to WRK.
3. Confirm IVN humanism displays `Рёв свободы` with its lion-and-broken-chain emblem.
4. Trigger the IVN defeat coup and confirm etatism displays `Чрезвычайный комитет Иторы` with its emergency seal.
5. Start the Vorkerland collapse and confirm VAD displays `Воркерландская имперская партия` and TVA displays `Технократическо-утилитарная рабочая партия свободного Воркерланда` with their unique emblems.
6. Release one of the seven successors as free and confirm its own emblem appears immediately.
7. Puppet it under WRK or WKR and confirm the exact WRK emblem returns immediately.
8. Puppet it under a non-WRK country and confirm its independent emblem remains.

Do not use an old save as evidence.

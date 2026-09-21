# Event illustrations

Production images are built by `tools/builders/build_adiscord_event_pictures.py`.
Do not edit `../standard/` or `interface/ADISCORD_event_art.gfx` by hand.

- COUNTRY: 507 x 184 pixels, matching the approved military-headquarters sample.
- NEWS: 396 x 153 pixels, matching the separate newspaper window.
- Cropping preserves aspect ratio. No stretching, decorative overlays, or tinting.
- The old explosion's embedded frame is cropped out; its source stays untouched.
- Files and sprites describe the scene. The NEWS prefix distinguishes its smaller format.
- Event scripts own scene assignments; the builder never rewrites gameplay.

Run from the repository root:

```powershell
python -B -m tools.builders.build_adiscord_event_pictures --check
python -B -m tools.builders.build_adiscord_event_pictures --apply
python -B -m tools.builders.build_adiscord_event_pictures --check
python -B -m unittest tools.tests.test_adiscord_event_ui -q
```

The generated contact sheet is
`gfx/interface/events/preview/ADISCORD_event_art_contact_sheet.png`.
Automated coverage resolves every visible COUNTRY/NEWS event to an opaque image
with its exact window dimensions. This does not replace a fresh game restart and
inspection of short/long events, options, and the NEWS overlay.

## Sources

Three new photographs were generated with the built-in image generation tool on
2026-09-07 (not the API/CLI). Full-size originals and exact prompts are below.
The other illustrations preserve existing mod art or the game's existing news
photos; names below identify provenance, not new historical claims about the mod.

| Local source | Original |
| --- | --- |
| `news/city_in_civil_war.png` | Mod `country/default/china_civil_war_1.png`, preserved before source consolidation |
| `news/army_formation.dds` | HOI4 `news_event_generic_army.dds` |
| `news/treaty_signing.dds` | HOI4 `news_event_generic_sign_treaty1.dds` |
| `news/peace_negotiations.dds` | HOI4 `news_event_generic_sign_treaty2.dds` |
| `news/military_planning.dds` | HOI4 `news_event_military_planning.dds` |
| `news/urban_resistance.dds` | HOI4 `news_event_polish_resistance_warsaw.dds` |
| `news/troops_marching.dds` | HOI4 `news_event_soldiers_marching.dds` |
| `news/armed_uprising.dds` | HOI4 `news_event_spr_spanish_civil_war2.dds` |

The builder also reads the existing mod sources `event_vorkerland_explosion.png`,
`event_vorkerland_civilwar_is_over.png`, and `event_adiscord_ui_test.png` one level
up. The last remains owned by the event-UI builder for compatibility; production
events use the descriptive `military_headquarters` sprite, not the QA name.

## Generated photographs: exact prompts

### `parliament_chamber.png`

Create one restrained photorealistic editorial photograph for a political strategy game's default internal-politics event illustration. Ultra-wide landscape 2.75:1 aspect ratio. An ordinary austere government meeting chamber, rows of empty worn wooden seats and a modest lectern, overcast daylight from tall side windows. Contemporary but old institutional building, fictional country. Muted grey-brown colors, subtle photographic grain, believable mundane room. Compose the meaningful scene across the central horizontal strip so it reads at 507x184 pixels. No people, no flags, no emblems, no text, no decorative frame, no teal-orange grading, no dramatic beams, no fog, no sci-fi, no fantasy, no glossy concept art. Simple documentary photograph, quiet and functional.

### `negotiation_table.png`

One photorealistic documentary photograph, ultra-wide 2.75:1 landscape, for a strategy game's default diplomacy event. An unoccupied modest conference table with two simple closed paper folders and two chairs facing each other in an old civic office. Side window with overcast daylight, worn wood, muted brown-grey palette, understated natural photographic texture. Frame the table at eye level from a little distance, objects grouped through the middle horizontal band; legible at 507x184 pixels. Fictional country, contemporary low-tech institutional setting. No people, no flags, no emblems, no writing, no gold embellishments, no watermarks or borders. No cinematic fog or light shafts or teal-orange colors. Quiet matter-of-fact composition.

### `nectar_of_the_gods.png`

One understated photorealistic documentary still life for a fictional strategy game's event titled Nectar of the Gods, about an officially tolerated recreational drink. Ultra-wide 2.75:1 landscape. A small plain brown glass bottle without a label and a plain tumbler on a worn wooden windowsill of an ordinary apartment, distant apartment blocks softly visible beyond the window, subdued overcast afternoon daylight. Bottle and glass fully inside the middle horizontal band and modest in size; readable at 507x184. Muted neutral colors, unpolished everyday photography. No people, no text, no brands, no symbols, no magical glow, no neon, no dramatic effects, no frame, no product-advertising gloss.

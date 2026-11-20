# Event illustrations

Production images are built by `tools/builders/build_adiscord_event_pictures.py`.
The four finished plates in `gfx/event_pictures/standard/news/` are
`kefreyt_address.png`, `military_formation.png`, `parliament_chamber.png`
and `vorkerland_world_empire_news.png`. Edit these plates in place. The builder
writes their `*_print.png` game textures and `interface/ADISCORD_event_art.gfx`.

Native-size COUNTRY plates in `FINISHED_COUNTRY` are edited at their original
paths in `gfx/event_pictures/standard/country/`. Plates with their own print
texture are used directly. For the others, the builder exports a separate
`*_print.png` and binds it to the same event sprite.

- COUNTRY: 507 x 184 pixels, matching the approved military-headquarters sample.
- NEWS uses 396 x 153 pixels for photographs. Finished 499 x 176 plates scale
  proportionally to 396 x 140 so the full composition fits the newspaper.
- Clean photographs receive the `event_news_pic_overlay` layer from
  `tools/assets/source/news_picture.psd` after cropping. The layer uses its
  original position, opacity and transparent canvas edge. The preprinted
  source lists cover photographs which already carry print lines; applying
  the layer again would darken them. All finished NEWS plates carry the print.
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

Use `--apply --preview` to write the development contact sheet to
`docs/development/previews/ADISCORD_event_art_contact_sheet.png`.
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
| `factory_workshop.dds` | HOI4 `news_event_generic_factory.dds`, formatted for COUNTRY events |
| `news/city_in_civil_war.png` | Mod `country/default/china_civil_war_1.png`, preserved before source consolidation |
| `news/army_formation.dds` | HOI4 `news_event_generic_army.dds` |
| `news/treaty_signing.dds` | HOI4 `news_event_generic_sign_treaty1.dds` |
| `news/peace_negotiations.dds` | HOI4 `news_event_generic_sign_treaty2.dds` |
| `news/military_planning.dds` | HOI4 `news_event_military_planning.dds` |
| `news/urban_resistance.dds` | HOI4 `news_event_polish_resistance_warsaw.dds` |
| `news/troops_marching.dds` | HOI4 `news_event_soldiers_marching.dds` |
| `news/armed_uprising.dds` | HOI4 `news_event_spr_spanish_civil_war2.dds` |

The military-headquarters scene uses the event-UI builder's rendering of
`event_adiscord_ui_test_source.png` directly. Production events use the
descriptive `military_headquarters` sprite.

`military_planning_color.png` and `factory_workshop_color.png` are colorized
COUNTRY sources produced with the built-in image tool. The monochrome originals
remain in `news/military_planning.dds` and `factory_workshop.dds`. Exact editing
prompts are stored in `colorization_prompts.json`. The independently authored
NEWS military-planning picture keeps its own source.

The supplied COUNTRY illustrations retain their original 507 x 184 pixels:

| Source | Event |
| --- | --- |
| `perimeter_checkpoint.png` | `ADISCORD_rus_campaign.14` |
| `expedition_camp.png` | `ADISCORD_rus_campaign.19` |
| `administrative_office.png` | `ADISCORD_rus_campaign.15` |
| `school_classroom.png` | `ADISCORD_rus_campaign.26`, `ADISCORD_rus_campaign.27` |

## Generated photographs: exact prompts

### NAM corporate board plates

Use a muted 1930s-40s documentary photograph in the style of `ledger_handover.png`, with fine horizontal scanlines. Export as an opaque 507x184 RGB PNG. No readable markings, real insignia, borders or watermarks. Use the named character's existing NAM portrait as the identity reference.

For the six company scenes, place the head in the final image's right third. Limit the photograph to the right 338 pixels and use the left 169 pixels for the flat company field. Centre the matching native 50x36 frame from `gfx/interface/NAM_basin/board_company_marks.png`; do not generate a mark. Frame order and field colours: Loren oxblood, Ferrant steel blue-grey, Navis dark teal, Arktur dark sand-khaki, Smenkom warm brown, Reidbank bottle green.

| Scene | Composition prompt |
| --- | --- |
| `nam_board_loren` | Aristarkh Vyazemtsev in a dark frock coat and oxblood waistcoat stands by a tall window in a panelled office. Island tank farms and an oil derrick show through the glass against orange dusk. |
| `nam_board_ferrant` | Taisiya Valts in steel-grey workwear and wire glasses overlooks a glowing billet and workers from a gantry on the right. For the composited plate, crop `nam_ferrant_steel.png` without altering it. |
| `nam_board_navis` | Saveliy Kruze in dark navy wool stands on a wet quay at night. Moored coasters and cargo nets recede into teal harbour light. |
| `nam_board_arktur` | Rodion Kalyonov in a plain khaki stand-collar tunic stands between stacked rifle crates in an arsenal shed. Guards inspect crate markings from an angle that keeps them unreadable. |
| `nam_board_smenkom` | Nazar Guryev in a tight brown suit and loosened amber tie leans on the hiring counter. Workers queue with caps in hand under amber lamps. |
| `nam_board_reidbank` | Lidiya Velyaminova with a starched white collar stands at a green-baize desk before an open vault door. Clerks carry ledgers past marble columns. |
| `nam_board_session` | View the long council table from its foot. Six delegations in subdued house colours sit along its sides, with the high-backed seat at the far end. Every face is small and indistinct. |
| `nam_board_chair_falls` | In the same hall, the empty high-backed chair is pulled out. A man walks away in backlight while another person's hand rests on the chair back. No identifiable faces. |
| `nam_judas_committees` | Dockers vote by raising their hands in a warehouse among cranes and bales. Yaroslav Weber speaks from a crate at mid-distance. |
| `nam_judas_officers` | Officers in dark greatcoats sit around a wardroom table at a patrol-boat base. Rostislav Karamyshev sits at the head; a grey cutter is visible through the porthole. |

### `parliament_chamber.png`

Create one restrained photorealistic editorial photograph for a political strategy game's default internal-politics event illustration. Ultra-wide landscape 2.75:1 aspect ratio. An ordinary austere government meeting chamber, rows of empty worn wooden seats and a modest lectern, overcast daylight from tall side windows. Contemporary but old institutional building, fictional country. Muted grey-brown colors, subtle photographic grain, believable mundane room. Compose the meaningful scene across the central horizontal strip so it reads at 507x184 pixels. No people, no flags, no emblems, no text, no decorative frame, no teal-orange grading, no dramatic beams, no fog, no sci-fi, no fantasy, no glossy concept art. Simple documentary photograph, quiet and functional.

### `negotiation_table.png`

One photorealistic documentary photograph, ultra-wide 2.75:1 landscape, for a strategy game's default diplomacy event. An unoccupied modest conference table with two simple closed paper folders and two chairs facing each other in an old civic office. Side window with overcast daylight, worn wood, muted brown-grey palette, understated natural photographic texture. Frame the table at eye level from a little distance, objects grouped through the middle horizontal band; legible at 507x184 pixels. Fictional country, contemporary low-tech institutional setting. No people, no flags, no emblems, no writing, no gold embellishments, no watermarks or borders. No cinematic fog or light shafts or teal-orange colors. Quiet matter-of-fact composition.

### `nectar_of_the_gods.png`

One understated photorealistic documentary still life for a fictional strategy game's event titled Nectar of the Gods, about an officially tolerated recreational drink. Ultra-wide 2.75:1 landscape. A small plain brown glass bottle without a label and a plain tumbler on a worn wooden windowsill of an ordinary apartment, distant apartment blocks softly visible beyond the window, subdued overcast afternoon daylight. Bottle and glass fully inside the middle horizontal band and modest in size; readable at 507x184. Muted neutral colors, unpolished everyday photography. No people, no text, no brands, no symbols, no magical glow, no neon, no dramatic effects, no frame, no product-advertising gloss.

# A-Discord 32 px Party Texticon Library Design

## Purpose

Build the visual library that will support the later global party-name cleanup:

- preserve the three user-authored legacy emblems exactly;
- standardize every other maintained party texticon on the accepted 32 by 32 pixel runtime format;
- add sixteen country-specific ruling-party emblems;
- add three reusable semantic emblems for each of the eight ideologies;
- keep the existing white-flag fallback available at 32 by 32 pixels;
- connect the sixteen country-specific emblems without yet performing the global party-name rewrite or generic assignment pass.

The accepted IVN `Roar of Freedom` pilot proves that a 32 by 32 canvas is readable in the politics interface. This design applies that result to the new library while retaining explicit exceptions requested by the user.

## Scope Split

This specification covers the first of two sequential features.

1. This feature builds, registers, validates, and selectively connects the 32 px visual library.
2. A later specification will review Russian party names across all 97 currently represented country tags and assign the 24 generic emblems semantically.

The split prevents a forty-image art review from being mixed with a roughly five-hundred-line localisation rewrite.

## Protected Legacy Assets

The following runtime PNGs remain byte-for-byte unchanged, including their current 25 by 25 canvases:

- `gfx/texticons/adiscord/parties/STP/STP_hedonist_party.png`
- `gfx/texticons/adiscord/parties/VAL/VAL_etatist_party.png`
- `gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png`

Their existing sprite identifiers and texture paths remain unchanged. Tests record and enforce their approved SHA-256 values so the expanded builder cannot silently resample or replace them.

`NOD_hedonism_party` and its long form continue to use `GFX_STP_hedonist_party_texticon`. No NOD-specific emblem is generated.

## Final Library Inventory

The registered runtime library contains 54 sprites:

- 3 protected legacy emblems: STP, VAL, and WRK;
- 10 existing builder-owned emblems: the two IVN identities, TVA, VAD, ZAO, PWR, VLA, ROM, SOL, and TRU;
- 16 new country-specific ruling-party emblems;
- 24 new generic ideological emblems;
- 1 white-flag fallback.

Of these, 51 assets are builder-owned. The three protected legacy PNGs remain external inputs verified but never rewritten by the builder.

The existing `IVN_roar_of_freedom_party.png` remains 32 by 32. The other nine existing builder-owned runtime PNGs move from 25 by 25 to 32 by 32 using their approved transparent masters.

## Country-Specific Emblems

The first wave covers these sixteen tags and their currently ruling parties:

| Tag | Ruling ideology | Current party identity | Emblem direction |
| --- | --- | --- | --- |
| BBV | chauvinism | Союз Копья Вашаита | spear, field shield, narrow banner |
| BCM | chauvinism | Межанский Стяг | fortified banner, river or bridge device |
| BGT | chauvinism | Крайтский Орден | order tower, closed helm, severe rays |
| BHG | chauvinism | Хачоевская Дружина | retinue shield, paired axes or horse device |
| BJK | chauvinism | Столичный Стяг Бежайска | capital gate, crown, city standard |
| BLD | chauvinism | Дворянский Щит Ландроса | noble shield, stag device, mantle |
| BTL | etatism | Республиканский Совет Порядка | civic fortress, scales, state wreath |
| COF | anarchism | Вольные Друиды | ancient tree, antlers, broken ring |
| DAN | etatism | military committee | expeditionary shield, compass, blade |
| EFL | chauvinism | Партия Единой Земли | joined landscape, rising land, binding ring |
| NAM | etatism | military committee | garrison tower, command batons, perimeter star |
| PIV | hedonism | ruling commercial elite | cane or crop device, mercantile sun, coin motif |
| RUS | anarchism | Вольные Аймаки | steppe tamga, horse device, open horizon |
| TFF | anarchism | Вольные Рейнджеры | frontier compass, trail star, field weapon silhouette |
| WIT | hedonism | ruling urban elite | night lantern, crescent, metropolitan frame |
| YPR | utilitarism | Юборский Комитет Производства | production gear, grain, disciplined rays |

The six Beshaysk-area emblems form one recognizable heraldic family without sharing the same shield, charge, or palette. Each must remain independently identifiable at runtime size.

NAM and DAN are represented specifically as military committees, not ordinary civilian state parties.

Only the short and long localisation entries for each listed ruling party receive the new country-specific sprite during this feature. Their other ideological parties retain the current white fallback until the later semantic assignment feature.

## Generic Ideological Library

Each ideology receives three semantic archetypes rather than three color variants of one mark.

| Ideology | Archetype 1 | Archetype 2 | Archetype 3 |
| --- | --- | --- | --- |
| humanism | civic or constitutional party | freedom and reform movement | social or municipal coalition |
| utilitarism | planning committee | productive union | public-benefit directorate |
| chauvinism | national front | martial league | traditionalist order |
| pragmatism | administrative coalition | commercial or contract bloc | regional establishment |
| anarchism | federation of communes | union of artels | insurgent or frontier movement |
| technocracy | scientific collegium | engineering directorate | systems or cybernetic bureau |
| etatism | state party | military committee | emergency administration |
| hedonism | aristocratic houses | mercantile-guild elite | urban cultural club |

All 24 sprites are registered in this feature but are not mass-assigned yet. The later naming feature will map each static party key to one archetype according to the cleaned party identity, not by tag rotation.

## Visual Language

The new work follows the density and political-emblem character of the WRK, VAD, and STP examples without copying their exact symbols.

- Each emblem uses two or three large motifs inside a badge, shield, seal, wreath, or standard.
- Strong dark contours and separated color masses must survive 32 px downscaling.
- No letters, abbreviations, slogans, microtext, watermarks, gradients that collapse into mud, or photographic backgrounds.
- Country-specific emblems derive their motif and palette from local identity rather than merely recoloring an ideology emblem.
- Generic emblems share an ideology-level palette family, but the three silhouettes within an ideology remain visibly different.
- Every generated master has a genuine transparent background and an isolated centered emblem.
- Runtime artwork fits within a maximum 30 by 30 area on a 32 by 32 transparent canvas.

## Image Generation and Review

Use the built-in image generation tool, not the CLI fallback. Generate one transparent master per distinct asset:

- 16 country-specific masters;
- 24 generic masters.

Existing approved masters are reused for the ten current builder-owned emblems. The white flag is reconstructed deterministically from its existing simple motif rather than creatively redesigned. The STP, VAL, and WRK PNGs are not supplied to image generation and are never edited.

Generated masters are saved under project-owned source directories before any runtime asset references them:

```text
tools/assets/source/party_texticons/countries/
tools/assets/source/party_texticons/generic/humanism/
tools/assets/source/party_texticons/generic/utilitarism/
tools/assets/source/party_texticons/generic/chauvinism/
tools/assets/source/party_texticons/generic/pragmatism/
tools/assets/source/party_texticons/generic/anarchism/
tools/assets/source/party_texticons/generic/technocracy/
tools/assets/source/party_texticons/generic/etatism/
tools/assets/source/party_texticons/generic/hedonism/
```

The review sequence is:

1. Generate and validate every transparent master.
2. Produce one country-specific contact sheet and one generic contact sheet organized into eight ideology rows.
3. Show both sheets to the user.
4. Regenerate individual rejected emblems with one targeted prompt change at a time.
5. Only after art approval, integrate the accepted masters into the runtime builder and localisation.

Raw built-in outputs that already contain valid RGBA transparency must retain their native alpha. No chroma-key helper may remove dark outlines from an already-transparent master.

## Source-of-Truth Architecture

Add a declarative catalog at `tools/data/adiscord_party_texticons.json`. It records:

- every builder-owned asset key;
- asset class: existing, country-specific, generic, or fallback;
- ideology and semantic archetype where applicable;
- source master path or deterministic fallback renderer;
- runtime output path;
- GFX sprite identifier;
- runtime canvas size;
- the sixteen ruling-party localisation assignments;
- the three protected legacy sprite paths and approved hashes.

`tools/builders/build_adiscord_party_texticons.py` consumes the catalog. It remains the exclusive owner of the 51 generated runtime PNGs and also renders the complete `interface/parties_texticons.gfx` registry in a stable order. The protected STP, VAL, and WRK sprite entries are emitted with their existing identifiers and paths, but their PNG bytes are read-only inputs.

The generated-output ownership registry is updated to list the catalog, all exact builder-owned output paths, the source masters, and the interface registry.

Russian localisation remains hand-authored outside generated blocks. The implementation changes only the icon prefix of the 32 short/long entries belonging to the sixteen selected ruling parties. It does not rename those parties. Tests consume the catalog assignments and verify the prefixes without making the localisation file a new generated output.

## Error Handling and Safety

- A missing master, opaque master, fully transparent master, duplicate asset key, duplicate sprite identifier, duplicate output path, or invalid runtime size is a hard builder error.
- A generated master smaller than the normal quality threshold is rejected. Explicitly approved legacy inputs may declare a lower threshold, but none of the three protected runtime PNGs may become a render source.
- The builder refuses to modify a protected legacy PNG and verifies its expected hash during both `--check` and `--apply`.
- A missing localisation assignment or an assignment to an undeclared sprite fails focused tests.
- If built-in image generation fails, stop and report it; do not silently switch to the API/CLI fallback.
- Main-checkout technology changes remain out of scope. Implementation and generation use an isolated worktree, and commits stage explicit paths only.

## Verification

Implementation follows test-driven development. The focused suite proves:

- the catalog contains exactly 51 builder-owned assets, 3 protected legacy assets, 16 country assignments, and 24 generic archetypes;
- all 40 new masters are project-local RGBA images with non-empty transparency;
- all builder-owned runtime outputs are 32 by 32 RGBA PNGs with transparent corners and non-empty artwork;
- IVN remains current and the other nine existing builder-owned emblems regenerate at 32 by 32;
- STP, VAL, and WRK retain their approved SHA-256 hashes and 25 by 25 canvases;
- NOD still uses the STP hedonist sprite and has no country-specific sprite;
- every catalog sprite resolves to exactly one runtime texture;
- every selected ruling-party short/long pair uses its declared country-specific sprite;
- the 24 generic sprites are registered but not yet required in ordinary party localisation;
- the white fallback exists at 32 by 32;
- the Russian localisation files retain UTF-8 BOMs;
- builder `--apply` followed by `--check` is current and a second apply is byte-identical;
- the generated-output ownership registry matches the builder exactly.

Run the focused builder, party-contract, and ownership tests, then:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

After static validation, fully restart HOI4 and use fresh campaigns. Inspect at minimum:

- one 32 px converted existing emblem;
- BJK or another new country-specific ruling-party emblem;
- NAM and DAN to verify their distinct military-committee identities;
- NOD to verify it still uses the unchanged STP emblem;
- fresh logs for missing sprite, texture, or localisation errors.

## Non-Goals

This feature does not:

- change the STP, VAL, or WRK PNGs;
- create a NOD-specific emblem;
- rewrite party names;
- assign the 24 generic sprites across the full party roster;
- alter ideology definitions, popularity, ruling parties, elections, puppet logic, or party-state transitions;
- change the established Vorkerland rule that WRK and WKR subjects use the WRK emblem until they become independent;
- repair old saves or use them as acceptance evidence.

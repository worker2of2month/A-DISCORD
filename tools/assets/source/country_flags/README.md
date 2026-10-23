# Country flag artwork

These source PNGs were created with the built-in imagegen tool. Their original palettes and field geometry are retained; the emblems reflect the countries' existing lore. Source images are inputs and must not be overwritten by exporters.

## Export and verification

Run the appropriate command with `--check` first, then `--apply`, then `--check` again:

```powershell
python -B -m tools.builders.build_adiscord_northern_countries --flags-only AUR LYS
python -B -m tools.builders.build_adiscord_inner_frontier_countries --flags-only LMN RLY
python -B -m tools.builders.build_adiscord_remainder_states --flags-only SFR PRR FLR
python -B -m tools.builders.build_adiscord_vorkerland_original_flags --tags MZR
python -B -m tools.builders.build_adiscord_island_administration_icon --check
```

Native sizes are 82x52, 41x26 and 10x7, opaque RGBA TGA. Runtime generators only resize and encode the authored artwork.

## Kefreyt Council

`tools.builders.build_adiscord_val_flags` owns the Council's three flag triplets.
`VAL_kefreyt_state` copies the existing `VAL` textures byte-for-byte.
`VAL_valden_republic` and `VAL_united_military_districts` use approved external
artwork supplied with repeatable `--import-flag TAG PATH` arguments. Use
`--flags-only VAL_kefreyt_state VAL_valden_republic VAL_united_military_districts`
to export only this choice set, first with `--check`, then `--apply`.

The import writes runtime textures only; high-resolution originals remain with
their owner. The 82x52 TGA becomes the runtime master for the two smaller sizes.
Subsequent `--check` and `--apply` runs need no import arguments. Replacing either
design requires its external original again. Map colours are defined in
`common/countries/cosmetic.txt`: Kefreyt State `127 15 2`, Valden Republic
`69 100 122`, United Military Districts `116 121 75`.

## Shared generation prompt

Use case: precise-object-edit / logo-brand. Redesign the supplied existing national flag for a fictional Hearts of Iron IV country. Input image is the edit target. Deliver ONE polished full-bleed rectangular flat flag artwork, landscape aspect ratio 82:52. Preserve its recognizable palette and primary field geometry, refine proportions and add the distinctive emblem described below. Crisp flat vector-like shapes, bold enough for 82x52 and 41x26 game textures. Maximum four flat colors. No cloth, no folds, no gradients, no lighting, no texture, no perspective, no borders or empty margins, no lettering, no slogans, no numerals, no watermark, no mockup. Restrained professional vexillology, not an ornate coat of arms. Important emblem should occupy roughly 60 percent of flag height with clean negative space.

## IVN and IVN_etatism

Itora's ordinary flag uses a silver lion breaking a gold chain. The emergency cabinet uses a gold eagle and ivory sword on a charcoal shield. Both retain the emerald field and two inset gold vertical bands. Symbolism references are `../party_texticons/IVN_roar_of_freedom_source.png` and `../party_texticons/IVN_emergency_committee_source.png`; those reference assets are not modified by flag export.

The native `IVN_etatism` filename selects the cabinet flag while the country has the `etatism` government. Other governments use `IVN`. The island administration's `IIA` triplet remains a byte-identical copy of ordinary `IVN`, independent of the overlord's government. The existing island-administration builder owns all three triplets and only resizes and encodes the source artwork.

Regular flag prompt: Create ONE final national flag artwork for fictional Itora, for a Hearts of Iron IV mod. Landscape aspect ratio 82:52. Full bleed perfectly flat flag; no cloth, folds, lighting, gradients, shadows, texture, perspective, lettering, watermark, borders or exterior margins. Refined heraldic vector-like flat shapes. Large confident emblem, readable at 82x52. Retain the current flag's deep emerald field and two narrow antique gold vertical stripes at x=12% and x=88%, with green outer edges. Between them one bold ivory rampant lion facing left, holding a broken gold chain with a few thick readable links; raised forepaws, curved tail, stylized angular mane. Emblem about 68% of flag height, no circle, wreath, shield, rifles or sunburst. Simplify the republican party symbol into clean heraldry. Use only deep emerald green, antique gold and ivory silver, strong negative space. Elegant restrained republican flag.

Emergency flag prompt: Create ONE final national flag artwork for fictional Itora under its emergency cabinet, for a Hearts of Iron IV mod. Landscape aspect ratio 82:52. Full bleed perfectly flat flag; no cloth, folds, lighting, gradients, shadows, texture, perspective, lettering, watermark, frame or exterior margins. Refined heraldic vector-like flat shapes, readable at 82x52. Retain deep emerald green field with narrow antique gold vertical stripes at x=12% and x=88%, green outer edges. Simplify the emergency cabinet's official emblem radically. In the center put one large angular charcoal shield outlined in gold, bearing a bold gold heraldic eagle with spread wings facing left. One simple ivory vertical sword lies along eagle's axis, point DOWN, hilt above eagle head. Eagle dominates, three broad feather shapes per wing, no tiny feather lines. Shield emblem about 72% flag height. Restrained stern state heraldry, distinct from a republican lion flag while sharing its gold-striped green field. Use only emerald, antique gold, ivory and charcoal. No gears, towers, wreaths, coins, stars, crossed rifles, extra emblems. The flag must be usable directly as game source artwork.

## IVC and IVN_chauvinism

Placeholder artwork until dedicated flags exist: the emergency cabinet flag with
its emerald field recoloured to deep crimson. `IVC` is the Marches Legion during
Itora's revolt; the native `IVN_chauvinism` filename shows the same flag while
Itora has the `chauvinism` government after the legion wins. Both are exported by
the island-administration builder with the other Itoran flags.

## SFR

Country: South Falor Directorate, disciplined coastal ports and supply service.

Design: Preserve the diagonal division ivory upper-left and charcoal-slate lower-right. Add one bold central lighthouse in a restrained heraldic design, charcoal where it crosses ivory and ivory where it crosses charcoal, a small warm brass lantern, two broad horizontal beacon rays. Clear architectural silhouette with broad solid tower and a strong base; no anchor, no shield, no tiny masonry.

Palette: ivory, charcoal slate, a tiny muted brass accent.

## PRR

Country: Perrin Free Ports, federation of exactly four island ports and independent maritime arbitration.

Design: Preserve warm ochre field and broad ivory saltire. Replace the central dark dot with a navy circular maritime badge containing one large ivory anchor. Exactly four separate simple navy lozenges placed at the four outer cardinal positions around the round badge represent four ports. Elegant merchant maritime flag, ample negative space, broad simple anchor.

Palette: warm ochre, ivory, deep navy.

## RLY

Country: Relay Republic, isolated self-sufficient engineering enclave with recycled water, heat and machinery.

Design: Preserve forest-green field and ivory saltire. Replace orange central dot with a large bold terracotta hexagonal hub, outlined ivory and forest green, containing an ivory angular closed-loop symbol made from three connected thick segments around a small green center. Geometric industrial relay motif, readable engineered heraldry, not radiation symbol. Saltire forms four substantial lines feeding the hub.

Palette: forest green, warm ivory, rust terracotta.

## MZR

Country: Mazar Water Syndicate, public wells and equitable water rations in an arid land.

Design: Preserve deep teal upper field and ochre bottom band, original ivory droplet/diamond identity. Improve with a large beautifully proportioned ivory water droplet centered in teal and extending slightly toward the ochre boundary. Inside droplet a simple teal three-way channel divides into three broad branches to represent common distribution. Two bold ivory horizontal ripples in ochre below. Spare confident hydraulic heraldry, no circle, no shield.

Palette: deep teal, sand ochre, ivory.

## LYS

Country: Lismar trading league, powerful merchant houses, bonded warehouses, coastal crossings and credit.

Design: Preserve rich purple field and gold-edged teal triangle projecting from the hoist. Add an elegant large antique-gold key horizontally in the purple fly, ring on left with a simple square hole and three bold architectural teeth on the right, signifying custody of warehouses and trade. Key must be strong and legible, no tiny details. Slim ivory accent on the key ring is acceptable. Noble austere merchant banner.

Palette: deep purple, antique gold, muted teal.

## LMN

Country: Leman Cordon, permanent quarantine, fortified checkpoints and controlled warehouses.

Design: Preserve dark charcoal-green field and ochre-edged brick-red hoist chevron. Add a bold warm ivory fortified gate emblem on the fly: two solid square towers joined by a thick lintel, closed dark passage crossed by one broad rust-red horizontal bar. Stark disciplined cordon heraldry, no biohazard sign, no text, no ornate shield, no masonry lines.

Palette: charcoal green, ochre, brick red, warm ivory.

## FLR

Country: Falor Union, agricultural valleys and district councils maintaining irrigation and roads.

Design: Preserve fresh muted green field and ivory-edged dark hoist triangle. Add a large golden three-ear wheat emblem on the green fly, thick stylized stems join above two broad ivory water-channel waves, signaling irrigated agriculture and unity. Only a few large grain shapes, not fine botanical detail. Distinct practical civic agrarian flag.

Palette: muted grass green, warm ivory, charcoal, harvest gold.

## AUR

Country: Aur civic republic, equal representation of mountain and coastal communities and negotiated peace.

Design: Preserve ochre-gold field and broad pale ivory saltire. Replace central slate dot with a strong slate-blue roundel with a narrow ivory edge. Within roundel a simple ivory mountain with two peaks over one ivory sea wave, above it a small gold sun disc. Bold balanced civic heraldry; mountain and coast receive equal visual weight, no wreath or crown, no tiny detail.

Palette: ochre gold, pale ivory, slate blue.

## Svetlogorye

`NAM_confederation` preserves the autonomy's original flag. The collapse removes
that cosmetic tag and reveals `NAM`, the independence flag. The authoritarian
ending selects `NAM_iron_ladder`, the Svetlogorye State flag. Each flag has opaque
RGBA TGA exports at 82x52, 41x26 and 10x7. High-resolution originals remain outside
the mod; these runtime exports have no builder. The republic ending selects
`NAM_service_republic`, with an orange rising sun on ivory above a navy band.
The federation ending selects `NAM_federation`, with linked ivory emblems on
an orange and navy diagonal field. The oil-workers' ending selects `NAM_oil_union`,
with an ivory oil droplet in an orange cogwheel between orange edge bands.
All five designs use built-in imagegen.

Union flag prompt: Use case: logo-brand. Create ONE finished flat national flag texture for fictional Svetlogorye Union, the Rule of the Oil Workers route in Hearts of Iron IV. Theme: oilfields jointly administered by workers and the state, common production and shared oil revenues. Landscape ratio 82:52, full bleed rectangular orthographic flat flag. Dark navy field, broad warm orange horizontal bands along top and bottom edges, each band 12 percent of flag height. At exact center ONE large orange industrial cogwheel with eight broad square teeth, dark navy circular interior, containing ONE bold ivory-white upright oil droplet. Cog outer diameter 64 percent of flag height; ivory droplet fills 68 percent of inner circle height, generous dark separation. Beautifully balanced bold industrial national heraldry, simple confident silhouette, no microdetail. Exactly three solid colors: warm orange, very dark navy, ivory. Readable at 82x52 and 41x26 pixels. Crisp flat vector-like shape edges. No stars anywhere, no sun, book, chain links, wreath, weapons, tower, text, lettering, numbers, extra emblems, gradients, fabric, folds, lighting, shadows, texture, perspective, external margins, mockup or watermark. One flag only.

Federation flag prompt: Use case: logo-brand. Create ONE finished flat national flag texture for fictional Svetlogorye Federation in Hearts of Iron IV. This is the District Self-Government political route: equal districts share authority through a federal compact. Landscape aspect ratio 82:52. Full bleed rectangular orthographic flag, crisp solid broad vector-like heraldic shapes, legible at 82x52 and 41x26 pixels. Background divided diagonally from bottom left to top right, warm orange upper-left and very dark navy lower-right, with a broad ivory diagonal stripe along that division. Centered large dark navy roundel edged with a strong ivory rim, diameter 65 percent of flag height. Inside roundel ONE bold ivory emblem of THREE interlocking rounded diamond-shaped chain links, arranged as a compact balanced triangular knot, each link equal in size. Use dark navy gaps at the overlaps to make the linked construction legible. Links must be broad, elegant and very simple, not thin linework. This is a union symbol, not a numerical map of districts. Strong visual balance, sober national vexillology, distinctive silhouette. Only warm orange, ivory and dark navy colors. No stars anywhere, no sun, book, letters, words, numerals, coats of arms, laurel, gear, arrows, weapon, extra decorations, gradient, fabric, folds, lighting, texture, perspective, exterior margin or watermark. Only one flag, no mockup.

Republic flag generation prompt: Use case: logo-brand. Create ONE final national flag texture for the fictional Svetlogorye Republic, the Civic Reforms route in Hearts of Iron IV. Landscape 82:52 ratio, full bleed rectangular flag, perfectly flat orthographic heraldic graphic, no mockup. Palette reference: attached independence flag only for warm orange, ivory and dark navy colors, and continuity of sun symbolism. New composition: ivory-white upper field occupying 72 percent of height; dark navy lower horizontal band 28 percent high with a thin orange dividing stripe. Centered on the ivory field a large dark navy open book, bold simple symmetrical silhouette, two ivory page insets and a central spine, no lettering or tiny lines. Behind the book rises a warm orange half-sun with five broad separated rectangular rays. Book overlaps and conceals lower half of sun. The combined book-and-sun emblem fills 60 percent of total flag height, with generous clear margins and no contact with canvas edges. Professional dignified civic state flag representing public law and accountable government, distinctive and readable at 82x52 and 41x26 pixels. Crisp solid shapes, flat colors only. No stars, wreath, seals, stamp, mountains, gears, weapons, text, numerals, cloth, folds, lighting, shadows, gradients, texture, border, perspective or watermark. ONE flag only.

Republic flag final edit prompt: Use case: precise-object-edit. Edit the attached Svetlogorye Republic flag. Remove the open book completely. Replace the combined book-and-sun emblem with ONE large warm orange rising sun: a perfect semicircular orange disk with a flat horizontal bottom and seven broad short clearly separated rectangular rays radiating upwards. Center this sun emblem in the ivory upper field, occupying about 55 percent of total flag height, with generous ivory margin below the sun. No dark shapes in the upper ivory field. Preserve the full-bleed rectangular 82:52 landscape flag, ivory upper field, dark navy bottom band and thin orange horizontal separator, preserving their exact colors and proportions. Flat solid colors, crisp professional heraldry readable at 82x52 pixels. No book, document, text, lettering, stars, mountain, seal, wreath, additional emblem, fabric, texture, gradients, shadows, perspective, border or watermark. One flat flag, no mockup.

Independence flag prompt: Use case: logo-brand. Asset: ONE finished flat national flag texture for independent Svetlogorye, a fictional country in Hearts of Iron IV just liberated from a collapsed empire, before any final political regime. Landscape aspect ratio 82:52. Full-bleed rectangular flag, orthographic flat graphic design with bold heraldic shapes readable at 82x52 pixels. Upper two thirds warm orange field, lower third very dark navy field with a narrow ivory stripe separating them. Centered large ivory heraldic mountain range of three broad connected peaks rises from the navy lower third into orange field; middle peak highest. A large dark navy rising sun disk behind the central peak with seven broad short rectangular rays fans upward into orange sky. The ivory mountain silhouette clearly overlaps and conceals lower half of the dark sun. Strong dignified state flag, original coherent composition, broad silhouettes, ample space around emblem. Palette only warm orange, ivory white, near-black navy; match these colors to the reference state flag, but no stamp, wreath, red hoist or other regime symbols from reference. No stars, text, lettering, numbers, tiny detail, folds, fabric, shadows, gradients, mockup, white margins, border or perspective. Reference image role: palette reference only, not edit target.

State flag prompt: Use case: logo-brand. Asset: one finished national flag texture for fictional Svetlogorye, Hearts of Iron IV. Landscape 82:52 ratio. Full bleed rectangular flat orthographic vector-like artwork, crisp broad shapes, solid colors. Interesting historically plausible vexillology, striking large silhouette readable at 82x52 pixels. Palette warm orange, ivory white, near-black navy, restrained deep red. No stars anywhere. No lettering, text, numbers, tiny ornament, mockup, cloth, folds, shading, texture, gradient, empty border or perspective. Authoritarian Svetlogorye of the Seals. Dark navy field, wide deep-red vertical panel at hoist bordered by narrow ivory line. Centered in remaining navy field a bold ivory heraldic emblem of an upright desk stamp with a rounded handle and wide rectangular base, standing over three ascending orange steps. Surround the stamp and steps by an open angular orange wreath of two laurel branches. Severe institutional heraldry. Emblem fills 70 percent of height, thick strokes, few details. Unequal hoist panel and centered emblem create a distinctive state banner.

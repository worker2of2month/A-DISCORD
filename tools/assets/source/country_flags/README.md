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

# Country flag artwork

These source PNGs were created with the built-in imagegen tool. Their original palettes and field geometry are retained; the emblems reflect the countries' existing lore. Source images are inputs and must not be overwritten by exporters.

## Export and verification

Run the appropriate command with `--check` first, then `--apply`, then `--check` again:

```powershell
python -B -m tools.builders.build_adiscord_northern_countries --flags-only AUR LYS
python -B -m tools.builders.build_adiscord_inner_frontier_countries --flags-only LMN RLY
python -B -m tools.builders.build_adiscord_remainder_states --flags-only SFR PRR FLR
python -B -m tools.builders.build_adiscord_vorkerland_original_flags --tags MZR
```

Native sizes are 82x52, 41x26 and 10x7, opaque RGBA TGA. Runtime generators only resize and encode the authored artwork.

## Shared generation prompt

Use case: precise-object-edit / logo-brand. Redesign the supplied existing national flag for a fictional Hearts of Iron IV country. Input image is the edit target. Deliver ONE polished full-bleed rectangular flat flag artwork, landscape aspect ratio 82:52. Preserve its recognizable palette and primary field geometry, refine proportions and add the distinctive emblem described below. Crisp flat vector-like shapes, bold enough for 82x52 and 41x26 game textures. Maximum four flat colors. No cloth, no folds, no gradients, no lighting, no texture, no perspective, no borders or empty margins, no lettering, no slogans, no numerals, no watermark, no mockup. Restrained professional vexillology, not an ornate coat of arms. Important emblem should occupy roughly 60 percent of flag height with clean negative space.

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

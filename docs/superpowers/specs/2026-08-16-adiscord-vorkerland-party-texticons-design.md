# A-Discord Vorkerland Party Texticons Design

**Date:** 2026-08-16

## Goal

Add readable, detailed party emblems before the relevant Russian party names for IVN, TVA, and the Vorkerland successor countries. The seven countries that begin as WRK dependencies must use the exact existing WRK party emblem while they are subjects of WRK or WKR, switch to their own emblem when independent, and switch back if WRK or WKR subjugates them again.

This is a fresh-campaign feature. It does not include old-save migration.

## Approved scope

### New unique emblems

Ten new transparent party texticons are required:

| Country | Ideology / phase | Party identity | Visual direction |
| --- | --- | --- | --- |
| IVN | Humanism, normal government | `Рёв свободы` | Silver heraldic lion or roaring beast, a broken gold chain, and green rays; energetic rather than military. |
| IVN | Etatism, defeat coup | `Чрезвычайный комитет Иторы` | Dark-green emergency seal with a fortified shield, upright steel blade, and restrained gold state ornament. |
| TVA | Technocracy, Vorkerland civil war | `Технократическо-утилитарная рабочая партия свободного Воркерланда` | Teal industrial cog enclosing a worker's hammer and a precise circuit or lightning motif, framed as a wartime technical order. |
| VAD | Pragmatism, Vorkerland civil war | `Воркерландская имперская партия` | Navy-and-gold imperial medallion derived from the VAD restoration flag: crown, disciplined radial wings or laurels, and a strong central state symbol. |
| ZAO | Independent identity | Existing authored party text | Red-and-gold western administrative crest with a tower or rail junction and a compact worker motif. |
| PWR | Independent identity | Existing authored party text | Red-and-gold reconstruction seal with crossed engineering tools, masonry or scaffolding, and a small industrial sun. |
| VLA | Independent identity | Existing authored party text | Blue, white, and gold eastern military crest with a winged blade or spear and a rising horizon. |
| ROM | Independent identity | Existing authored party text | Navy-and-crimson Frealor medallion built around a compass rose, coastal star, or anchor-like geometry. |
| SOL | Independent identity | Existing authored party text | Orange-and-white Solyarino seal with a layered solar disk, turbine blades, and a central diamond. |
| TRU | Independent identity | Existing authored party text | Purple-and-orange Zolotorevsk forge badge with a faceted diamond, metalworking tool, and red-hot core. |

The ZAO, PWR, VLA, ROM, SOL, and TRU text is not silently renamed in this pass. Their state-specific localisation keys may duplicate the current short and long names while changing the leading texticon. VAD, TVA, and both IVN identities use the explicitly requested names above.

### Shared WRK dependency identity

VAD, ZAO, PWR, VLA, ROM, SOL, and TRU use the existing `GFX_WRK_worker_revolutionary_party_texticon` while they are a subject specifically of WRK or WKR. No regional variants of the WRK emblem are generated.

Being a subject of any other country does not grant the WRK emblem. Such a country retains its independent emblem unless a separate content rule says otherwise.

NAM and DAN are excluded because their military committees are a separate identity family.

## Art requirements

- Final game assets are 25 by 25 pixel transparent PNGs, matching the existing party texticons.
- Each emblem must remain recognisable at native size, with one dominant silhouette, a strong outer contour, and no more than two small internal motifs.
- The finish should match the visual density of the existing WRK, STP, VAL, and military VAD emblems: layered metal, heraldic framing, highlights, shadows, and purposeful internal detail.
- Emblems must not contain letters, words, numbers, signatures, or watermarks.
- Country flag colours and motifs are references, not backgrounds; no icon should look like a rectangular miniature flag.
- The generated master should be square and isolated on a flat chroma-key background. Local processing removes that background, centres the opaque artwork with safe padding, downsamples it, and preserves a clean alpha channel.
- Every icon is inspected both enlarged for alpha defects and at native 25 by 25 size for silhouette and contrast. Detail that turns into noise at native size is simplified.

## Party slots covered

The dynamic identity synchronizer covers the ideology slots used by the starting dependency and the authored post-collapse government:

| Country | Slots that participate in dependency / independence switching |
| --- | --- |
| VAD | Pragmatism |
| ZAO | Pragmatism |
| PWR | Pragmatism and technocracy |
| VLA | Pragmatism |
| ROM | Pragmatism and etatism |
| SOL | Pragmatism |
| TRU | Pragmatism and chauvinism |

This keeps the requested lifecycle correct before the civil war, after a peaceful early release, during the collapse, and after a later re-puppeting. Other opposition-party slots remain outside scope and continue using their current icons.

IVN humanism and etatism are static party identities. The existing defeat-coup path continues to select etatism; this feature only corrects the associated names and icons. TVA receives its requested name and unique technocratic emblem when its civil-war setup runs.

## Runtime state model

One narrowly scoped scripted effect owns the seven-country party-identity synchronization:

1. Determine whether the current country is VAD, ZAO, PWR, VLA, ROM, SOL, or TRU.
2. If it is a subject of WRK or WKR, assign localisation keys that preserve the relevant party text and prepend the exact WRK texticon.
3. Otherwise, assign the corresponding independent localisation keys and prepend that country's unique emblem.
4. For VAD, the collapse-start flag selects the requested imperial party text; autonomy still independently determines whether the displayed emblem is VAD's or WRK's.

The effect uses HOI4's `set_party_name` with `ideology`, `name`, and `long_name`. It must not call `set_politics`, alter party popularity, change elections, or promote/replace a leader.

The synchronizer is called only at bounded lifecycle points:

- fresh-campaign initialization for the seven starting WRK dependencies;
- the existing Vorkerland collapse setup, in the same tick that claimant identities and cosmetics are applied;
- `on_puppet`;
- `on_release_as_puppet`;
- `on_release_as_free`.

The existing autonomy hooks and collapse cosmetic synchronizer are extended rather than duplicated. There is no daily, weekly, monthly, or global polling.

## Asset and localisation integration

- New PNGs live below `gfx/texticons/adiscord/parties/<TAG>/` with ASCII filenames.
- `interface/parties_texticons.gfx` declares one sprite for each new PNG.
- Russian localisation keeps its UTF-8 BOM.
- `localisation/russian/parties_l_russian.yml` owns the regular IVN and successor-party keys.
- The existing Vorkerland collapse localisation file owns the TVA wartime keys and any collapse-specific helper keys already grouped there.
- Dynamic helper keys use ASCII technical identifiers and Russian display text.
- Short and long party names both include the same leading `£GFX_..._party_texticon` token.

## Verification

Static verification must prove:

- all ten new PNGs are exactly 25 by 25 pixels and have a non-empty alpha channel;
- every new sprite points to an existing file and every new localisation texticon token resolves to a declared sprite;
- the IVN, TVA, VAD, and seven-country mapping matches this specification;
- the party synchronizer is present in initialization, collapse setup, and the three autonomy hooks;
- no party synchronizer is called from a recurring pulse;
- the effect uses `set_party_name` and does not change ideology, popularity, elections, or leaders;
- edited Russian localisation retains its UTF-8 BOM;
- the focused party-texticon tests and Vorkerland collapse validator pass;
- `python -B tools/validate_tc.py --limit 300` passes;
- both unstaged and, if staging is requested, cached `git diff --check` pass.

Because this changes loaded GFX, localisation, and visible scripted state, completion also requires a full HOI4 restart and a fresh campaign check before claiming runtime proof. The smoke test should inspect the seven starting dependencies, IVN before and after its coup, the VAD and TVA civil-war parties, one independence transition, and one WRK/WKR re-puppeting transition.

## Non-goals

- No changes to NAM or DAN military committees.
- No redesign of WRK, STP, VAL, or existing country flags and portraits.
- No new icons for every opposition party or ideology.
- No old-save repair or migration.
- No recurring polling.
- No changes to political balance, ideology, party popularity, elections, or leaders.

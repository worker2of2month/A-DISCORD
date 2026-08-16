# IVN Roar of Freedom 32 px Texticon Pilot

**Status:** approved for implementation on 2026-08-16.

## Goal

Test whether a larger party texticon improves readability in the Hearts of Iron IV politics interface without clipping, shifting the party-name baseline, or increasing the line height unacceptably.

The pilot changes only `IVN_roar_of_freedom_party.png` from 25x25 to 32x32. It reuses the existing approved transparent master `tools/assets/source/party_texticons/IVN_roar_of_freedom_source.png`; no new image generation or artistic revision is required.

The supplied `gfx/texticons/adiscord/parties/LDPR.png` is a visual reference only. Its actual bitmap size is 31x32, but the user explicitly selected a square 32x32 pilot. The reference file is not copied, registered, or modified by this work.

## Scope

- Extend the party-texticon builder so an individual `AssetSpec` can declare its runtime canvas size.
- Render `ivn_roar_of_freedom` to a 32x32 RGBA canvas with at least one transparent pixel of outer padding and a maximum 30x30 artwork area.
- Keep the other nine generated party texticons at 25x25 with their current maximum 23x23 artwork area.
- Regenerate only the drifted IVN runtime output through the owning builder.
- Update focused tests to enforce the mixed-size manifest and deterministic output.
- Fully restart HOI4 and inspect IVN in a fresh campaign after static verification.

## Builder Design

`tools/builders/build_adiscord_party_texticons.py` remains the exclusive owner of the runtime PNG. `AssetSpec` gains an immutable runtime-size field whose default is `(25, 25)`. Only `ivn_roar_of_freedom` overrides it with `(32, 32)`.

Rendering derives the artwork limit from the requested canvas instead of using fixed literals:

- 25x25 canvas -> maximum 23x23 artwork;
- 32x32 canvas -> maximum 30x30 artwork.

The renderer continues to crop by non-empty alpha, downscale with Lanczos, apply the existing light unsharp mask, center the artwork, preserve RGBA transparency, and encode deterministically. Existing source validation remains unchanged.

The runtime path and sprite identifier do not change, so `interface/parties_texticons.gfx` and Russian localisation require no edit.

## Test Contract

Focused tests must prove:

- the manifest still contains exactly the ten approved assets;
- `ivn_roar_of_freedom` declares and renders exactly 32x32 RGBA;
- every other generated runtime icon remains exactly 25x25 RGBA;
- all generated icons retain non-empty alpha and transparent outer corners;
- repeated rendering is byte-identical;
- the committed runtime output matches the builder;
- generated-output ownership still matches `ASSETS` exactly.

Static gates are the focused builder and party-texticon tests, the party ownership test, `python -B tools/validate_tc.py --limit 300`, BOM checks for the touched party-localisation dependencies even though they are not edited, and worktree/index diff checks.

## Runtime Smoke Test

After a full HOI4 restart, start a fresh campaign as IVN and open the politics interface. Verify the `Рёв свободы` row at normal UI scale and at the user's usual UI scale.

Acceptance requires:

- the icon is not cropped;
- the party name remains vertically aligned and fully readable;
- the line does not overlap neighbouring UI;
- the larger lion-and-chain emblem is materially clearer than the 25x25 version;
- no fresh `error.log` entry points to the sprite or texture.

If the 32x32 icon clips or harms layout, restore the manifest entry to 25x25 and regenerate through the builder. A 31x32 TFR-matching variant is a separate follow-up decision, not an automatic fallback.

## Non-goals and Follow-up

This pilot does not resize the emergency-committee icon, the other Vorkerland icons, or the WRK/STP/VAL icons. It does not rename parties or add new sprites.

Once the in-game result is accepted, the next design cycle resumes the already selected broader work:

- 17 country-specific ruling-party emblems beginning with NOD;
- three semantic generic emblems for each of the eight ideologies;
- restrained, politically realistic editing of all party names;
- a guaranteed texticon prefix for every short and long party-localisation key.

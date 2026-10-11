# Provisional administration flags

Editable raster sources for NOD, VAL, YPR and TFF under the STS hegemony.
`tools/builders/build_adiscord_stp_flags.py` exports each source to RGBA TGA
at 82x52, 41x26 and 10x7. Run the builder with `--check`, then `--apply`,
then `--check` again. Country names and base map colours remain unchanged.

The administration creation effects assign the cosmetic identity after
subordination. Subject lifecycle hooks remove only these identities when
the country leaves STS; another route's cosmetic identity is preserved.

## Artwork references

Local identities: `gfx/flags/NOD.tga`, `VAL.tga`, `YPR.tga`, `TFF.tga`.
Overlord emblem: `tools/assets/source/STS_hegemony_flag.png`.
The reference sheet is `docs/development/previews/stp-administration-flags-reference.png`.
The PNG sources are generated artwork, copied without further bitmap edits.

## Generation prompts

Shared prompt:

Create a NEW fictional national flag for the A-Discord strategy-game mod.
Flat print-ready rectangular flag, 82:52 aspect ratio, edge-to-edge artwork.
No flagpole, waving, folds, fabric, shadow, text, border or mockup.
Crisp simple vector-like shapes, solid colors, strong readability reduced
to 82x52 pixels. The reference sheet shows existing country flags; the
separate large reference is the overlord STS hegemony flag. Preserve local
identity but show dependent provisional government: a compact dark-navy
canton at upper hoist containing the same recognizable gold four-point
mountain-star of the overlord, with a thin cream separator. Do not reproduce
the whole sheet; output ONLY one new flag.

NOD:

Nodrul administration. Local palette royal-blue and deep crimson divided
diagonally from lower hoist to upper fly by a thin gold line, matching the
NOD reference. Keep a large white stylized sun toward the upper-middle fly
on blue. Simplify away all tiny decorative old text and ornaments. Navy
overlord canton occupies upper-left quarter and stays clearly distinct
from local royal-blue. Elegant heraldry.

VAL:

Kefreyt administration. Deep burgundy field matching VAL reference. A single
bold white laurel branch runs diagonally through the center-right,
recognizably related to the original white branch. Replace the original
assault-rifle emblem with two crossed simple white keys above the branch,
denoting civil administration. Upper-left navy overlord canton with gold
mountain-star. Only three main colors burgundy navy cream/gold, restrained
authoritative heraldry.

YPR:

Yubor administration. Pale sky-blue field and cream-white horizontal top band,
preserving YPR reference. Center-right large simple white heraldic chalice
with a small white equal-armed cross directly above, bold and simplified,
no tiny lettering. Upper-left navy overlord canton with gold mountain-star.
Distinct peaceful local identity, clear geometry.

TFF:

Frontier administration. Preserve TFF reference diagonal black lower-left
and muted burgundy upper-right fields. Toward center-right a large ivory
roundel contains a simple black mountain silhouette above a compact black
anvil. Upper-left navy overlord canton with gold mountain-star. Strong sparse
industrial mountain heraldry.

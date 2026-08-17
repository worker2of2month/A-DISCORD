# A-Discord 32 px Party Texticon Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and review a 54-sprite party-texticon library containing sixteen new country emblems, twenty-four generic ideological emblems, a 32 px fallback, and 32 px rebuilds of the existing builder-owned icons while leaving STP, VAL, WRK, and NOD's shared STP assignment unchanged.

**Architecture:** Generate forty transparent source masters with the built-in image tool, review them in two contact sheets, and then feed the approved masters to a catalog-driven deterministic Pillow builder. The builder owns 51 runtime PNGs, the party GFX registry, and the two report sheets; three protected legacy PNGs remain read-only inputs. A separate localisation task changes only the icon prefixes of sixteen ruling-party short/long pairs.

**Tech Stack:** Built-in image generation, Python 3, Pillow, JSON, `unittest`, HOI4 1.19.2 GFX/localisation, PowerShell, Git worktrees, and Codex computer-use for the fresh-campaign smoke test.

## Global Constraints

- Execute in `.worktrees/adiscord-party-texticon-library-32px` on branch `codex/adiscord-party-texticon-library-32px`, created with `superpowers:using-git-worktrees` from a clean commit containing design commit `141b91cb579e36b0f24a257d847342750ca97ca4`.
- Re-audit `main`, the target paths, and the fork point immediately before worktree creation. Preserve every unrelated technology change in the authoritative checkout.
- Use the built-in image generation tool once per distinct new master. Do not use the CLI/API fallback, do not create one image containing several source emblems, and do not use chroma-key cleanup on a valid RGBA result.
- Keep these runtime PNGs byte-for-byte unchanged at 25 by 25 pixels:
  - STP: `A0E2B87A270E50C91E568B9D915746367A4E81AD92F746E48E731530D8CC518F`
  - VAL: `F703BD763CD3E4BBF44B9D34B14256337E481333867E261127B7C11E7C74B552`
  - WRK: `5FDD08F8522281FF6948E43DD58DDC982A47100528216885A9A895B61084C76F`
- Keep `NOD_hedonism_party` and `NOD_hedonism_party_long` on `GFX_STP_hedonist_party_texticon`; create no NOD-specific source, runtime PNG, or sprite.
- Every builder-owned runtime PNG is 32 by 32 RGBA with non-empty artwork and transparent corners. Artwork fits within a maximum 30 by 30 area.
- Reuse the ten approved masters already under `tools/assets/source/party_texticons/`; do not regenerate them.
- Do not rename any party in this feature. For the sixteen selected ruling parties, change only the leading `£GFX_...` token.
- Preserve the UTF-8 BOM in every edited Russian localisation file.
- The established WRK/WKR subject and independence icon transitions remain unchanged.
- Never stage or commit the untracked pilot plan, the technology work, or any file not explicitly named by this plan.
- Runtime acceptance uses a full HOI4 restart and a fresh campaign. Never use an old save as evidence.

---

### Task 1: Create the Isolated Execution Worktree and Prove the Baseline

**Files:**
- Verify only; no repository file changes.

**Interfaces:**
- Consumes: design commit `141b91cb579e36b0f24a257d847342750ca97ca4` and the authoritative dirty `main` checkout.
- Produces: clean named worktree `.worktrees/adiscord-party-texticon-library-32px` on branch `codex/adiscord-party-texticon-library-32px`.

- [ ] **Step 1: Verify the main checkout, ignored worktree directory, and branch availability**

Run from the authoritative repository root:

```powershell
git rev-parse HEAD
git branch --show-current
git status --short
git merge-base --is-ancestor 141b91cb579e36b0f24a257d847342750ca97ca4 HEAD
if ($LASTEXITCODE -ne 0) { throw 'The approved design commit is not an ancestor of main.' }
git check-ignore -v .worktrees
if (-not $?) { throw '.worktrees is not ignored.' }
if (git branch --list 'codex/adiscord-party-texticon-library-32px') { throw 'Pilot branch already exists.' }
if (Test-Path -LiteralPath '.worktrees\adiscord-party-texticon-library-32px') { throw 'Pilot worktree already exists.' }
git status --short -- `
  'tools/builders/build_adiscord_party_texticons.py' `
  'tools/tests/test_build_adiscord_party_texticons.py' `
  'tools/tests/test_adiscord_party_texticons.py' `
  'tools/tests/test_generated_output_ownership.py' `
  'tools/data/generated_output_owners.json' `
  'interface/parties_texticons.gfx' `
  'localisation/russian/parties_l_russian.yml' `
  'gfx/texticons/adiscord/parties' `
  'tools/assets/source/party_texticons'
```

Expected: `main`; the design commit is an ancestor; `.worktrees` is ignored; no branch or worktree collision; every task-owned path is clean. Stop if a task-owned path has acquired unrelated edits.

- [ ] **Step 2: Create the worktree from the audited main commit**

```powershell
git worktree add '.worktrees/adiscord-party-texticon-library-32px' `
  -b 'codex/adiscord-party-texticon-library-32px' HEAD
git -C '.worktrees/adiscord-party-texticon-library-32px' status --short
git -C '.worktrees/adiscord-party-texticon-library-32px' branch --show-current
```

Expected: a clean worktree on the named branch.

- [ ] **Step 3: Run the baseline focused and total-conversion gates**

Run inside the worktree:

```powershell
python -B -m tools.builders.build_adiscord_party_texticons --check
python -B -m unittest `
  tools.tests.test_build_adiscord_party_texticons `
  tools.tests.test_adiscord_party_texticons `
  tools.tests.test_wrk_party_icon -v
python -B -m unittest `
  tools.tests.test_generated_output_ownership.GeneratedOutputOwnershipTests.test_party_texticon_registry_exactly_matches_assets_and_is_exclusive -v
python -B tools/validate_tc.py --limit 300
git diff --check
```

Expected: all commands exit zero and the worktree remains clean. If the baseline fails, stop before generating art.

---

### Task 2: Generate and Approve the Sixteen Country Masters

**Files:**
- Create: `tools/assets/source/party_texticons/countries/BBV_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/BCM_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/BGT_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/BHG_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/BJK_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/BLD_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/BTL_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/COF_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/DAN_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/EFL_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/NAM_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/PIV_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/RUS_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/TFF_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/WIT_primary_party_source.png`
- Create: `tools/assets/source/party_texticons/countries/YPR_primary_party_source.png`
- Temporary review only: `tmp/party-texticon-review/countries.png`

**Interfaces:**
- Consumes: built-in image generation and the approved country directions below.
- Produces: sixteen approved project-local RGBA masters, each at least 512 by 512 pixels.

- [ ] **Step 1: Create the source directory and record the exact prompt scaffold**

Create the directory with `New-Item -ItemType Directory` if absent. Use this exact shared content in every country call, followed by the asset-specific request and palette from the table:

```text
Use case: logo-brand
Asset type: source master for a Hearts of Iron IV political-party texticon rendered at 32x32
Style/medium: original dense political heraldry, illustrated enamel-and-metal badge, complexity comparable to the approved WRK, VAD, and STP emblems without copying their symbols
Composition/framing: one centered isolated emblem on a square canvas, two or three large readable motifs inside a shield, seal, wreath, or standard; generous transparent margin
Materials/textures: restrained enamel, aged metal, cloth, or carved relief appropriate to the subject
Constraints: genuine transparent background; strong near-black outer contour; separated color masses; readable after reduction to 32x32; no letters, numbers, slogans, microtext, watermark, photographic scene, modern corporate logo, swastika, SS rune, or real-world extremist symbol
Avoid: tiny decoration, muddy gradients, background rectangle, glow outside the silhouette, clipped edges
```

Use these exact asset-specific requests:

| File prefix | Primary request | Palette |
| --- | --- | --- |
| BBV | The independent Union of the Spear of Vashait: a vertical spear over a compact field shield, crossed by one narrow battle banner | dark navy, bronze, restrained crimson |
| BCM | The independent Mezhansk Banner: a fortified standard rising above a stylized river bridge, compact heraldic framing | river blue, silver, burgundy |
| BGT | The independent Krait Order: a severe order tower behind a closed helm, hard radial rays contained inside the badge | iron black, old gold, bone white |
| BHG | The independent Khachoev retinue: a retinue shield with paired axes and a simplified horse-head device | forest green, rust red, ivory |
| BJK | The capital standard of Bezhaysk: a monumental city gate beneath a small crown, framed by a vertical civic banner | deep red, gold, near black |
| BLD | The noble shield of Landros: a stag device on a broad aristocratic shield with a compact mantle | dark green, antique gold, cream |
| BTL | The Republican Council of Order: a civic fortress combined with balanced scales and a disciplined state wreath | steel blue, white enamel, dark red |
| COF | The Free Druids: an ancient spreading tree joined with antlers and an intentionally broken outer ring | forest green, umber, bone |
| DAN | An expeditionary military committee, not a civilian party: a field shield combining a compass rose, command blade, and small expedition star | khaki, navy, brass |
| EFL | The Party of the United Land: two joined landforms under a rising horizon, bound by one strong ring | ochre, dark green, black |
| NAM | A garrison military committee, not a civilian state party: a watchtower with crossed command batons inside a perimeter star | slate gray, olive, muted red |
| PIV | A ruling commercial agricultural elite: crossed cane stalks beneath a mercantile sun with one coin-like central seal | amber, teal, gold |
| RUS | The Free Aimags: an original steppe tamga combined with a horse-head silhouette and an open horizon arc | sky blue, black, muted red |
| TFF | The Free Rangers of the frontier: a rugged compass rose, trail star, and restrained long field-weapon silhouette | dust brown, faded blue, gunmetal |
| WIT | A ruling nocturnal urban elite: an ornate night lantern beneath a crescent inside a metropolitan iron frame | deep violet, warm gold, cold cyan accent |
| YPR | The Yuboran Production Committee: a heavy production gear joined with grain and disciplined rising rays | industrial red, steel gray, wheat gold |

- [ ] **Step 2: Generate one built-in image per row**

For each row, issue a separate built-in image generation call. Copy the returned final RGBA file to the exact source path for that row. Do not pass several parties in one prompt, do not use the CLI, and do not run transparency removal if the returned image already has alpha.

After each call, inspect the generated file with `view_image`. Reject immediately if it contains text, a rectangular background, clipped artwork, a missing dark contour, or a motif belonging to another row.

- [ ] **Step 3: Validate all sixteen country masters**

Run this exact validation from the worktree:

```powershell
@'
from pathlib import Path
from PIL import Image

root = Path("tools/assets/source/party_texticons/countries")
files = sorted(root.glob("*_primary_party_source.png"))
expected = {"BBV", "BCM", "BGT", "BHG", "BJK", "BLD", "BTL", "COF", "DAN", "EFL", "NAM", "PIV", "RUS", "TFF", "WIT", "YPR"}
actual = {path.name.split("_", 1)[0] for path in files}
assert actual == expected, (actual, expected)
assert len(files) == 16
for path in files:
    with Image.open(path) as image:
        assert image.mode == "RGBA", (path, image.mode)
        assert min(image.size) >= 512, (path, image.size)
        alpha = image.getchannel("A")
        assert alpha.getbbox() is not None, path
        assert alpha.getextrema()[0] < 255, path
        width, height = image.size
        assert all(image.getpixel(point)[3] == 0 for point in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))), path
print("COUNTRY_MASTER_VALIDATION_OK", len(files))
'@ | python -B -
```

Expected: `COUNTRY_MASTER_VALIDATION_OK 16`.

- [ ] **Step 4: Render a temporary 4 by 4 review sheet**

Create the temporary sheet with this exact script. It is not staged:

```powershell
New-Item -ItemType Directory -Force -Path 'tmp\party-texticon-review' | Out-Null
@'
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

source = Path("tools/assets/source/party_texticons/countries")
output = Path("tmp/party-texticon-review/countries.png")
files = sorted(source.glob("*_primary_party_source.png"))
assert len(files) == 16
canvas = Image.new("RGB", (1024, 1024), (34, 36, 40))
draw = ImageDraw.Draw(canvas)
font = ImageFont.load_default(size=18)
for index, path in enumerate(files):
    column, row = index % 4, index // 4
    cell_x, cell_y = column * 256, row * 256
    with Image.open(path) as image:
        icon = ImageOps.contain(image.convert("RGBA"), (192, 192), Image.Resampling.LANCZOS)
    icon_x = cell_x + (256 - icon.width) // 2
    icon_y = cell_y + 16 + (192 - icon.height) // 2
    canvas.paste(icon, (icon_x, icon_y), icon)
    label = path.name.split("_", 1)[0]
    box = draw.textbbox((0, 0), label, font=font)
    label_x = cell_x + (256 - (box[2] - box[0])) // 2
    draw.text((label_x, cell_y + 224), label, font=font, fill=(235, 235, 235))
canvas.save(output, format="PNG", optimize=False, compress_level=9)
print(output.resolve())
'@ | python -B -
```

Open the sheet with `view_image` and show it to the user. Pause until the user explicitly approves the sheet or names individual emblems to regenerate. For a rejected emblem, repeat one built-in call with the full original prompt plus one targeted correction, overwrite only its source master, rerun validation, and rebuild the sheet.

- [ ] **Step 5: Commit only the approved country masters**

```powershell
git add -- 'tools/assets/source/party_texticons/countries'
$staged = @(git diff --cached --name-only)
$unexpected = @($staged | Where-Object { $_ -notmatch '^tools/assets/source/party_texticons/countries/[A-Z]{3}_primary_party_source\.png$' })
if ($staged.Count -ne 16 -or $unexpected.Count -ne 0) {
    $staged
    throw 'Unexpected country-master staged scope.'
}
git diff --cached --check
git commit -m 'art: add country party emblem masters'
```

Expected: one commit containing exactly sixteen approved source PNGs. Keep the temporary sheet for Task 3 but do not stage it.

---

### Task 3: Generate and Approve the Twenty-Four Generic Masters

**Files:**
- Create under `tools/assets/source/party_texticons/generic/humanism/`: `humanism_civic_source.png`, `humanism_reform_source.png`, `humanism_solidarity_source.png`
- Create under `tools/assets/source/party_texticons/generic/utilitarism/`: `utilitarism_planning_source.png`, `utilitarism_productive_union_source.png`, `utilitarism_public_benefit_source.png`
- Create under `tools/assets/source/party_texticons/generic/chauvinism/`: `chauvinism_national_front_source.png`, `chauvinism_martial_league_source.png`, `chauvinism_traditional_order_source.png`
- Create under `tools/assets/source/party_texticons/generic/pragmatism/`: `pragmatism_administrative_coalition_source.png`, `pragmatism_commercial_bloc_source.png`, `pragmatism_regional_establishment_source.png`
- Create under `tools/assets/source/party_texticons/generic/anarchism/`: `anarchism_communal_federation_source.png`, `anarchism_artel_union_source.png`, `anarchism_frontier_movement_source.png`
- Create under `tools/assets/source/party_texticons/generic/technocracy/`: `technocracy_scientific_collegium_source.png`, `technocracy_engineering_directorate_source.png`, `technocracy_systems_bureau_source.png`
- Create under `tools/assets/source/party_texticons/generic/etatism/`: `etatism_state_party_source.png`, `etatism_military_committee_source.png`, `etatism_emergency_administration_source.png`
- Create under `tools/assets/source/party_texticons/generic/hedonism/`: `hedonism_aristocratic_houses_source.png`, `hedonism_guild_elite_source.png`, `hedonism_cultural_club_source.png`
- Temporary review only: `tmp/party-texticon-review/generic.png`

**Interfaces:**
- Consumes: the same shared image-generation scaffold from Task 2 and the exact semantic rows below.
- Produces: twenty-four approved project-local RGBA masters, each at least 512 by 512 pixels.

- [ ] **Step 1: Generate three distinct masters per ideology**

Use one built-in call for every row. Prepend the exact shared prompt scaffold from Task 2, then append the row's primary request and palette.

| Source filename | Primary request | Palette |
| --- | --- | --- |
| humanism_civic_source.png | A constitutional civic party: open civic hall, balanced charter tablet, restrained laurel | clear blue, white enamel, warm gold |
| humanism_reform_source.png | A freedom and reform movement: raised torch crossing a broken chain inside an open wreath | sky blue, vermilion accent, silver |
| humanism_solidarity_source.png | A social or municipal coalition: joined hands supporting a small bridge and rising sun | turquoise, cream, soft gold |
| utilitarism_planning_source.png | A planning committee: measured grid, abacus bars, and one balanced gear | dark teal, white, brass |
| utilitarism_productive_union_source.png | A productive union: heavy gear joined with grain and an upward industrial chevron | teal, steel, wheat gold |
| utilitarism_public_benefit_source.png | A public-benefit directorate: scales supporting a reservoir or public bowl beneath ordered rays | sea green, ivory, muted orange |
| chauvinism_national_front_source.png | A national front: upright standard, severe sun disk, closed defensive shield | black, deep red, antique gold |
| chauvinism_martial_league_source.png | A martial league: crossed command blades behind a compact eagle-like abstract winged shield, not a real national emblem | gunmetal, crimson, pale gold |
| chauvinism_traditional_order_source.png | A traditionalist order: fortress crown, ceremonial key, rigid laurel frame | dark burgundy, black, bronze |
| pragmatism_administrative_coalition_source.png | An administrative coalition: handshake over a ledger with one practical compass divider | gray blue, tan, muted red |
| pragmatism_commercial_bloc_source.png | A commercial or contract bloc: sealed contract scroll, key, and restrained coin device | brown, brass, deep blue |
| pragmatism_regional_establishment_source.png | A regional establishment: bridge, boundary stone, and compact civic wreath | slate, ochre, forest green |
| anarchism_communal_federation_source.png | A federation of communes: linked small houses around an intentionally open ring | black, warm red, cream |
| anarchism_artel_union_source.png | A union of artels: crossed hand tools, wheat, and a free-work knot | charcoal, rust, pale yellow |
| anarchism_frontier_movement_source.png | An insurgent or frontier movement: broken chain, trail flame, and open compass arc | black, orange red, dust tan |
| technocracy_scientific_collegium_source.png | A scientific collegium: orbital diagram, open technical book, and precision star | cobalt, cyan, silver |
| technocracy_engineering_directorate_source.png | An engineering directorate: gear, caliper, and angular factory tower | navy, bright cyan, steel |
| technocracy_systems_bureau_source.png | A systems or cybernetic bureau: circuit network, central lens, and hexagonal control frame | dark blue, electric cyan, white |
| etatism_state_party_source.png | A state party: monumental columned tower, sealed state disk, and closed wreath | dark red, black, gold |
| etatism_military_committee_source.png | A military committee: command star, crossed marshal batons, and armored shield | olive, dark red, brass |
| etatism_emergency_administration_source.png | An emergency administration: fortified decree tablet, warning rays, and enclosing authority ring | slate, orange, black |
| hedonism_aristocratic_houses_source.png | Aristocratic houses: goblet, small crown, and ornate house shield | royal purple, gold, wine red |
| hedonism_guild_elite_source.png | A mercantile-guild elite: jeweled key, coin seal, and folded guild ribbon | violet, emerald, warm gold |
| hedonism_cultural_club_source.png | An urban cultural club: theatrical mask, night lantern, and rose-like ornamental frame | magenta, deep violet, champagne gold |

Apply the same rejection rules as Task 2. Within one ideology the three emblems must have visibly different silhouettes, not merely different internal details.

- [ ] **Step 2: Validate all twenty-four generic masters**

```powershell
@'
from pathlib import Path
from PIL import Image

root = Path("tools/assets/source/party_texticons/generic")
expected = {
    "humanism": {"civic", "reform", "solidarity"},
    "utilitarism": {"planning", "productive_union", "public_benefit"},
    "chauvinism": {"national_front", "martial_league", "traditional_order"},
    "pragmatism": {"administrative_coalition", "commercial_bloc", "regional_establishment"},
    "anarchism": {"communal_federation", "artel_union", "frontier_movement"},
    "technocracy": {"scientific_collegium", "engineering_directorate", "systems_bureau"},
    "etatism": {"state_party", "military_committee", "emergency_administration"},
    "hedonism": {"aristocratic_houses", "guild_elite", "cultural_club"},
}
files = sorted(root.glob("*/*_source.png"))
assert len(files) == 24, len(files)
actual = {ideology: set() for ideology in expected}
for path in files:
    ideology = path.parent.name
    prefix = ideology + "_"
    assert path.name.startswith(prefix) and path.name.endswith("_source.png"), path
    actual[ideology].add(path.name[len(prefix):-len("_source.png")])
    with Image.open(path) as image:
        assert image.mode == "RGBA", (path, image.mode)
        assert min(image.size) >= 512, (path, image.size)
        alpha = image.getchannel("A")
        assert alpha.getbbox() is not None, path
        assert alpha.getextrema()[0] < 255, path
        width, height = image.size
        assert all(image.getpixel(point)[3] == 0 for point in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))), path
assert actual == expected, (actual, expected)
print("GENERIC_MASTER_VALIDATION_OK", len(files))
'@ | python -B -
```

Expected: `GENERIC_MASTER_VALIDATION_OK 24`.

- [ ] **Step 3: Render and review the eight-row generic sheet**

Render the sheet with this exact script:

```powershell
New-Item -ItemType Directory -Force -Path 'tmp\party-texticon-review' | Out-Null
@'
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

root = Path("tools/assets/source/party_texticons/generic")
output = Path("tmp/party-texticon-review/generic.png")
order = (
    ("humanism", ("civic", "reform", "solidarity")),
    ("utilitarism", ("planning", "productive_union", "public_benefit")),
    ("chauvinism", ("national_front", "martial_league", "traditional_order")),
    ("pragmatism", ("administrative_coalition", "commercial_bloc", "regional_establishment")),
    ("anarchism", ("communal_federation", "artel_union", "frontier_movement")),
    ("technocracy", ("scientific_collegium", "engineering_directorate", "systems_bureau")),
    ("etatism", ("state_party", "military_committee", "emergency_administration")),
    ("hedonism", ("aristocratic_houses", "guild_elite", "cultural_club")),
)
canvas = Image.new("RGB", (960, 2048), (34, 36, 40))
draw = ImageDraw.Draw(canvas)
font = ImageFont.load_default(size=16)
for row, (ideology, archetypes) in enumerate(order):
    for column, archetype in enumerate(archetypes):
        path = root / ideology / f"{ideology}_{archetype}_source.png"
        assert path.is_file(), path
        with Image.open(path) as image:
            icon = ImageOps.contain(image.convert("RGBA"), (192, 192), Image.Resampling.LANCZOS)
        cell_x, cell_y = column * 320, row * 256
        icon_x = cell_x + (320 - icon.width) // 2
        icon_y = cell_y + 12 + (192 - icon.height) // 2
        canvas.paste(icon, (icon_x, icon_y), icon)
        label = f"{ideology}/{archetype}"
        box = draw.textbbox((0, 0), label, font=font)
        label_x = cell_x + (320 - (box[2] - box[0])) // 2
        draw.text((label_x, cell_y + 224), label, font=font, fill=(235, 235, 235))
canvas.save(output, format="PNG", optimize=False, compress_level=9)
print(output.resolve())
'@ | python -B -
```

Open the sheet with `view_image` and show it to the user. Pause for explicit approval. Regenerate only named failures with one targeted correction, then rerun validation and rebuild the sheet.

- [ ] **Step 4: Commit only the approved generic masters**

```powershell
git add -- 'tools/assets/source/party_texticons/generic'
$staged = @(git diff --cached --name-only)
$unexpected = @($staged | Where-Object { $_ -notmatch '^tools/assets/source/party_texticons/generic/(humanism|utilitarism|chauvinism|pragmatism|anarchism|technocracy|etatism|hedonism)/[a-z_]+_source\.png$' })
if ($staged.Count -ne 24 -or $unexpected.Count -ne 0) {
    $staged
    throw 'Unexpected generic-master staged scope.'
}
git diff --cached --check
git commit -m 'art: add generic party emblem masters'
```

Expected: one commit containing exactly twenty-four approved source PNGs.

---

### Task 4: Build the Catalog-Driven Runtime Library and Registry

**Files:**
- Create: `tools/data/adiscord_party_texticons.json`
- Modify: `tools/builders/build_adiscord_party_texticons.py`
- Modify: `tools/tests/test_build_adiscord_party_texticons.py`
- Create: `tools/tests/test_adiscord_party_texticon_library.py`
- Modify: `tools/tests/test_generated_output_ownership.py`
- Modify: `tools/data/generated_output_owners.json`
- Regenerate: `interface/parties_texticons.gfx`
- Regenerate: the ten existing builder-owned runtime PNGs
- Create: sixteen `gfx/texticons/adiscord/parties/TAG/TAG_primary_party.png` files for the country tags from Task 2
- Create: twenty-four `gfx/texticons/adiscord/parties/generic/IDEOLOGY/IDEOLOGY_ARCHETYPE_party.png` files corresponding to Task 3
- Regenerate: `gfx/texticons/adiscord/parties/unknown_party.png`
- Create: `docs/superpowers/reports/2026-08-16-adiscord-party-country-emblems-contact-sheet.png`
- Create: `docs/superpowers/reports/2026-08-16-adiscord-party-generic-emblems-contact-sheet.png`

**Interfaces:**
- Produces: `Catalog`, `AssetSpec`, `ProtectedSpec`, `AssignmentSpec`, `load_catalog()`, `render_icon()`, `render_white_flag()`, `render_registry()`, `render_contact_sheets()`, `expected_outputs()`, `protected_issues()`, `drift()`, and `apply()`.
- Produces: exactly 51 builder-owned PNGs, 3 protected inputs, 54 GFX sprites, 16 country assignments, 24 generic assets, one generated interface file, and two generated report sheets.

- [ ] **Step 1: Write the failing catalog and protected-asset tests**

In `tools/tests/test_build_adiscord_party_texticons.py`, replace the ten-key constants with independent literal contracts:

```python
EXPECTED_EXISTING = {
    "ivn_roar_of_freedom", "ivn_emergency_committee",
    "tva_wartime_technocratic_worker", "vad_vorkerland_imperial",
    "zao_independent_party", "pwr_independent_party", "vla_independent_party",
    "rom_independent_party", "sol_independent_party", "tru_independent_party",
}
EXPECTED_COUNTRIES = {f"{tag.lower()}_primary_party" for tag in {
    "BBV", "BCM", "BGT", "BHG", "BJK", "BLD", "BTL", "COF",
    "DAN", "EFL", "NAM", "PIV", "RUS", "TFF", "WIT", "YPR",
}}
EXPECTED_GENERIC = {
    "humanism": {"civic", "reform", "solidarity"},
    "utilitarism": {"planning", "productive_union", "public_benefit"},
    "chauvinism": {"national_front", "martial_league", "traditional_order"},
    "pragmatism": {"administrative_coalition", "commercial_bloc", "regional_establishment"},
    "anarchism": {"communal_federation", "artel_union", "frontier_movement"},
    "technocracy": {"scientific_collegium", "engineering_directorate", "systems_bureau"},
    "etatism": {"state_party", "military_committee", "emergency_administration"},
    "hedonism": {"aristocratic_houses", "guild_elite", "cultural_club"},
}
EXPECTED_PROTECTED = {
    "gfx/texticons/adiscord/parties/STP/STP_hedonist_party.png": "a0e2b87a270e50c91e568b9d915746367a4e81ad92f746e48e731530d8cc518f",
    "gfx/texticons/adiscord/parties/VAL/VAL_etatist_party.png": "f703bd763cd3e4bbf44b9d34b14256337e481333867e261127b7c11e7c74b552",
    "gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png": "5fdd08f8522281ff6948e43dd58ddc982a47100528216885a9a895b61084c76f",
}
```

Add assertions that the catalog path exists; asset keys equal `EXPECTED_EXISTING | EXPECTED_COUNTRIES | all generic keys | {"unknown_party"}`; all 51 generated assets declare `[32, 32]`; the protected paths and hashes equal `EXPECTED_PROTECTED`; there are exactly 16 assignments; and no generated key, source, output, or sprite contains `NOD`.

Add a protected-byte test that opens each protected path, checks `(25, 25)`, computes SHA-256, and compares it with the literal hash.

- [ ] **Step 2: Run the tests and record the expected RED**

```powershell
python -B -m unittest tools.tests.test_build_adiscord_party_texticons -v
```

Expected: assertion failure because `tools/data/adiscord_party_texticons.json` does not exist and the builder still exposes the ten-entry tuple.

- [ ] **Step 3: Create the exact catalog**

Create JSON schema 1 with these top-level keys:

```json
{
  "schema": 1,
  "generated_assets": [],
  "protected_legacy": [],
  "country_assignments": []
}
```

Populate `generated_assets` with:

- the ten existing key/source/output mappings currently in the Python builder, changing every runtime size to `[32, 32]`;
- sixteen country entries using key `tag_lower_primary_party`, source `tools/assets/source/party_texticons/countries/TAG_primary_party_source.png`, output `gfx/texticons/adiscord/parties/TAG/TAG_primary_party.png`, sprite `GFX_TAG_primary_party_texticon`, class `country`, source kind `master`, and runtime size `[32, 32]`;
- twenty-four generic entries using key `generic_IDEOLOGY_ARCHETYPE`, the exact source files from Task 3, output `gfx/texticons/adiscord/parties/generic/IDEOLOGY/IDEOLOGY_ARCHETYPE_party.png`, sprite `GFX_generic_IDEOLOGY_ARCHETYPE_party_texticon`, class `generic`, source kind `master`, and runtime size `[32, 32]`;
- fallback key `unknown_party`, class `fallback`, source kind `procedural_white_flag`, output `gfx/texticons/adiscord/parties/unknown_party.png`, sprite `GFX_unknown_party_texticon`, and runtime size `[32, 32]`.

Populate `protected_legacy` with the three exact paths, hashes, sizes, and existing sprite identifiers:

```text
GFX_STP_hedonist_party_texticon -> gfx/texticons/adiscord/parties/STP/STP_hedonist_party.png
GFX_VAL_etatist_party_texticon -> gfx/texticons/adiscord/parties/VAL/VAL_etatist_party.png
GFX_WRK_worker_revolutionary_party_texticon -> gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png
```

Populate `country_assignments` with these exact base keys and sprites:

```text
BBV_chauvinism_party -> GFX_BBV_primary_party_texticon
BCM_chauvinism_party -> GFX_BCM_primary_party_texticon
BGT_chauvinism_party -> GFX_BGT_primary_party_texticon
BHG_chauvinism_party -> GFX_BHG_primary_party_texticon
BJK_chauvinism_party -> GFX_BJK_primary_party_texticon
BLD_chauvinism_party -> GFX_BLD_primary_party_texticon
BTL_etatism_party -> GFX_BTL_primary_party_texticon
COF_anarchism_party -> GFX_COF_primary_party_texticon
DAN_etatism_party -> GFX_DAN_primary_party_texticon
EFL_chauvinism_party -> GFX_EFL_primary_party_texticon
NAM_etatism_party -> GFX_NAM_primary_party_texticon
PIV_hedonism_party -> GFX_PIV_primary_party_texticon
RUS_anarchism_party -> GFX_RUS_primary_party_texticon
TFF_anarchism_party -> GFX_TFF_primary_party_texticon
WIT_hedonism_party -> GFX_WIT_primary_party_texticon
YPR_utilitarism_party -> GFX_YPR_primary_party_texticon
```

Use ideology order `humanism`, `utilitarism`, `chauvinism`, `pragmatism`, `anarchism`, `technocracy`, `etatism`, `hedonism`. Keep the existing builder-owned entries in their current GFX order, then country tags alphabetically, then generic entries in ideology/table order.

- [ ] **Step 4: Implement the catalog loader and validation**

Replace the hard-coded `ASSETS` tuple with these types:

```python
@dataclass(frozen=True)
class AssetSpec:
    key: str
    asset_class: str
    source_kind: str
    source: Path | None
    output: Path
    sprite: str
    runtime_size: tuple[int, int]
    ideology: str | None = None
    archetype: str | None = None

@dataclass(frozen=True)
class ProtectedSpec:
    key: str
    output: Path
    sprite: str
    sha256: str
    runtime_size: tuple[int, int]

@dataclass(frozen=True)
class AssignmentSpec:
    party_key: str
    sprite: str

@dataclass(frozen=True)
class Catalog:
    assets: tuple[AssetSpec, ...]
    protected: tuple[ProtectedSpec, ...]
    assignments: tuple[AssignmentSpec, ...]
```

Implement `load_catalog(root: Path = ROOT) -> Catalog`. Reject wrong schema, missing required fields, unknown classes/source kinds, a runtime size other than `(32, 32)` for generated assets, duplicate key/source/output/sprite, missing masters, missing protected files, invalid 64-character lowercase hashes, assignments to undeclared generated sprites, and any NOD-specific generated record.

Keep `ASSETS`, `PROTECTED`, and `ASSIGNMENTS` as module-level tuples loaded from the catalog for compatibility with ownership tests.

- [ ] **Step 5: Run the focused test and confirm catalog GREEN before renderer changes**

```powershell
python -B -m unittest tools.tests.test_build_adiscord_party_texticons -v
```

Expected: catalog/protected tests pass; output-current tests fail because the renderer and committed runtime set are not expanded yet.

- [ ] **Step 6: Add failing renderer, registry, and report tests**

Add tests that require:

- `render_white_flag((32, 32))` returns deterministic RGBA PNG bytes with a white cloth shape, dark pole/outline, non-empty alpha, and transparent corners;
- every master-backed `render_icon` output is `(32, 32)` with one transparent outer pixel;
- `render_registry()` returns 54 unique sprite definitions in the required order and includes `legacy_lazy_load = no` for each;
- `render_contact_sheets()` returns exactly the two report paths, with country sheet `(1024, 1024)` and generic sheet `(960, 2048)`;
- `expected_outputs()` contains 51 runtime PNGs plus the interface registry and two reports;
- protected PNG paths never appear in `expected_outputs()`.

Run the test and record assertion failures because these functions and outputs do not yet exist.

- [ ] **Step 7: Implement deterministic runtime, fallback, registry, and contact-sheet rendering**

Preserve the approved crop, Lanczos thumbnail, and mild unsharp-mask behavior for master-backed icons. Derive artwork size from `runtime_size - (2, 2)`.

Implement `render_white_flag()` procedurally on a transparent 32 px canvas: a dark three-pixel pole from approximately `(6, 4)` to `(6, 28)`, a light inner pole, and a black-outlined white rippling flag extending from the upper pole toward x 26 and returning near x 20. Keep the motif visually equivalent to the existing white flag and leave all four corners transparent.

Implement `render_registry(catalog: Catalog = CATALOG) -> bytes` with this order:

1. fallback;
2. WRK, STP, VAL protected sprites using their current identifiers and paths;
3. the ten existing builder-owned sprites in current order;
4. sixteen country sprites alphabetically;
5. twenty-four generic sprites in catalog ideology/archetype order.

Render the complete `spriteTypes` block as UTF-8 with stable `\n` line endings; do not leave any pre-existing or undeclared sprite outside the generated block.

Implement contact sheets with Pillow's default font and dark neutral backgrounds. Country sheet: 4 by 4 cells of 256 px, master art contained to 192 px, tag label. Generic sheet: 3 columns by 8 rows, 320 by 256 px cells, master art contained to 192 px, `ideology/archetype` label.

Implement the exact public signatures `expected_outputs(root: Path = ROOT) -> dict[Path, bytes]`, `protected_issues(root: Path = ROOT) -> list[str]`, `drift(root: Path = ROOT) -> list[str]`, and `apply(root: Path = ROOT) -> None`.

Both `--check` and `--apply` must call `protected_issues()` first and fail without writes on a protected hash/size mismatch. `apply()` writes only keys returned by `expected_outputs()`.

- [ ] **Step 8: Regenerate and prove deterministic output**

```powershell
python -B -m tools.builders.build_adiscord_party_texticons --apply
python -B -m tools.builders.build_adiscord_party_texticons --check
python -B -m unittest tools.tests.test_build_adiscord_party_texticons -v
$protectedBefore = Get-FileHash -Algorithm SHA256 `
  'gfx/texticons/adiscord/parties/STP/STP_hedonist_party.png', `
  'gfx/texticons/adiscord/parties/VAL/VAL_etatist_party.png', `
  'gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png'
$generatedPaths = @(
  Get-ChildItem -File -Recurse 'gfx/texticons/adiscord/parties' | Where-Object FullName -NotMatch '\\(STP|VAL|WRK)\\'
  Get-Item -LiteralPath 'interface/parties_texticons.gfx'
  Get-Item -LiteralPath 'docs/superpowers/reports/2026-08-16-adiscord-party-country-emblems-contact-sheet.png'
  Get-Item -LiteralPath 'docs/superpowers/reports/2026-08-16-adiscord-party-generic-emblems-contact-sheet.png'
) | Sort-Object FullName
$generatedBefore = $generatedPaths | Get-FileHash -Algorithm SHA256
python -B -m tools.builders.build_adiscord_party_texticons --apply
$protectedAfter = Get-FileHash -Algorithm SHA256 `
  'gfx/texticons/adiscord/parties/STP/STP_hedonist_party.png', `
  'gfx/texticons/adiscord/parties/VAL/VAL_etatist_party.png', `
  'gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png'
$generatedAfter = $generatedPaths | Get-FileHash -Algorithm SHA256
if (Compare-Object $protectedBefore.Hash $protectedAfter.Hash) { throw 'Protected PNG changed.' }
if (Compare-Object $generatedBefore.Hash $generatedAfter.Hash) { throw 'Generated runtime PNGs are not idempotent.' }
```

Expected: builder current, focused tests green, protected and generated hashes identical across the second apply.

- [ ] **Step 9: Update ownership tests and registry**

Change `test_party_texticon_registry_exactly_matches_assets_and_is_exclusive` so expected outputs are every path returned by `expected_outputs()`. Expected inputs are, in stable order:

1. `tools/builders/build_adiscord_party_texticons.py`;
2. `tools/data/adiscord_party_texticons.json`;
3. all non-null master source paths from `ASSETS`;
4. the three protected runtime PNG paths.

Update the `party_texticons` family in `tools/data/generated_output_owners.json` to those exact outputs and inputs. Keep `may_delete_outputs = false`, `ownership_mode = exclusive`, and one `party_texticons` entry in `apply_sequence`.

Run:

```powershell
python -B -m unittest `
  tools.tests.test_generated_output_ownership.GeneratedOutputOwnershipTests.test_party_texticon_registry_exactly_matches_assets_and_is_exclusive -v
```

Expected: PASS and every generated output has only the `party_texticons` owner.

- [ ] **Step 10: Add the complete library contract test**

In `tools/tests/test_adiscord_party_texticon_library.py`, test real files and catalog data:

- all 40 new masters satisfy the Task 2/3 alpha and size contract;
- all 51 generated runtime PNGs are `(32, 32)` RGBA with transparent corners;
- all 3 protected PNGs match exact hashes and `(25, 25)`;
- all 54 GFX sprites resolve once to the catalog texture paths;
- NOD uses `GFX_STP_hedonist_party_texticon` in both short/long entries and no NOD sprite exists;
- no generic sprite token appears in `localisation/russian/parties_l_russian.yml` yet;
- both generated contact sheets have exact dimensions.

Run the module and make it green without weakening these assertions.

- [ ] **Step 11: Review the builder-generated contact sheets**

Open both report paths with `view_image`. Compare them with the user-approved temporary sheets. Stop if any master is mismatched, clipped, too small, or visually muddy at the builder's presentation scale. Do not proceed to localisation until the user confirms the final generated sheets still represent the approved art.

- [ ] **Step 12: Commit the catalog-driven library**

Stage only:

- the catalog, builder, three test/registry paths named in this task;
- `interface/parties_texticons.gfx`;
- the 51 builder-owned runtime PNGs returned by `expected_outputs()`;
- the two generated contact sheets.

Do not stage the protected PNGs; their hashes prove they have no diff. Run `git diff --cached --check`, inspect `git diff --cached --stat`, and commit:

```powershell
git commit -m 'feat: build 32px party texticon library'
```

Expected: the commit contains no localisation and no STP, VAL, or WRK PNG change.

---

### Task 5: Connect the Sixteen Country-Specific Ruling Parties

**Files:**
- Modify: `tools/tests/test_adiscord_party_texticon_library.py`
- Modify: `localisation/russian/parties_l_russian.yml`

**Interfaces:**
- Consumes: the sixteen `country_assignments` from the catalog.
- Produces: exact leading sprite tokens on sixteen short/long ruling-party pairs without changing the Russian name payload.

- [ ] **Step 1: Write the failing assignment and no-rename tests**

Parse `parties_l_russian.yml` with `encoding="utf-8-sig"`. For each catalog assignment, require both `party_key` and `party_key + "_long"` to start with `£` plus the declared sprite plus one space.

Strip the leading `£GFX_... ` token from the 32 selected values, sort `key=value` lines, join with `\n`, hash the UTF-8 bytes, and assert this exact name-payload SHA-256:

```text
1b9fad7b7803437d0f228c8d95d2eb670822d2d657d0b45ff4173ef4c1c0b657
```

Also assert the file starts with UTF-8 BOM bytes `EF BB BF`.

- [ ] **Step 2: Run the library test and record the expected RED**

```powershell
python -B -m unittest tools.tests.test_adiscord_party_texticon_library -v
```

Expected: assignment-prefix failures because all sixteen pairs still use `GFX_unknown_party_texticon`; the no-rename hash and BOM checks pass.

- [ ] **Step 3: Change only the 32 icon prefixes**

Use `apply_patch` on `localisation/russian/parties_l_russian.yml`. For every assignment listed in Task 4, replace `£GFX_unknown_party_texticon` with the declared `£GFX_TAG_primary_party_texticon` on both the short and `_long` entry. Do not change any character after the first separating space.

Do not touch the Ainholm generated block or any Vorkerland dynamic helper key.

- [ ] **Step 4: Prove GREEN, BOM preservation, and exact text preservation**

```powershell
python -B -m unittest `
  tools.tests.test_adiscord_party_texticon_library `
  tools.tests.test_adiscord_party_texticons `
  tools.tests.test_wrk_party_icon -v
python -B -c "from pathlib import Path; p=Path('localisation/russian/parties_l_russian.yml'); assert p.read_bytes().startswith(bytes((0xEF,0xBB,0xBF))); print('PARTIES_BOM_OK')"
git diff --check -- 'localisation/russian/parties_l_russian.yml' 'tools/tests/test_adiscord_party_texticon_library.py'
```

Expected: all tests pass, the name-payload hash remains exact, and BOM validation prints `PARTIES_BOM_OK`.

- [ ] **Step 5: Commit the assignments**

```powershell
git add -- `
  'localisation/russian/parties_l_russian.yml' `
  'tools/tests/test_adiscord_party_texticon_library.py'
git diff --cached --check
$staged = @(git diff --cached --name-only)
if (Compare-Object @('localisation/russian/parties_l_russian.yml','tools/tests/test_adiscord_party_texticon_library.py') $staged) {
    $staged
    throw 'Unexpected assignment staged scope.'
}
git commit -m 'feat: assign country party texticons'
```

Expected: exactly the Russian localisation and its contract test.

---

### Task 6: Run Release Gates and Fresh-Campaign UI Validation

**Files:**
- Runtime evidence only; do not commit game logs or screenshots as game content.
- Create temporarily outside Git: `C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/mod/A-Discord-Party-Texticon-Library.mod`

**Interfaces:**
- Consumes: the complete feature branch and worktree.
- Produces: static release evidence, fresh-game UI screenshots, fresh log evidence, and the user's final visual acceptance.

- [ ] **Step 1: Run the complete static gate with fresh output**

```powershell
python -B -m tools.builders.build_adiscord_party_texticons --check
python -B -m unittest `
  tools.tests.test_build_adiscord_party_texticons `
  tools.tests.test_adiscord_party_texticon_library `
  tools.tests.test_adiscord_party_texticons `
  tools.tests.test_wrk_party_icon -v
python -B -m unittest `
  tools.tests.test_generated_output_ownership.GeneratedOutputOwnershipTests.test_party_texticon_registry_exactly_matches_assets_and_is_exclusive -v
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
if (git status --porcelain) { throw 'Feature worktree is not clean.' }
```

Expected: every command exits zero and the worktree is clean.

- [ ] **Step 2: Create a temporary launcher descriptor pointed at the worktree**

Copy `A-Discord.mod` to the exact temporary path. Record the original descriptor SHA-256 first. Use `apply_patch` on the copy to change only:

```text
name="A-Discord — Party Texticon Library"
path="C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/mod/A-Discord/.worktrees/adiscord-party-texticon-library-32px"
```

Verify the original hash is unchanged and the copied descriptor contains the exact worktree path.

- [ ] **Step 3: Load computer-use instructions and start a fresh campaign**

Use `computer-use:computer-use`. Through Steam and the Paradox Launcher, activate only `A-Discord — Party Texticon Library`, fully restart HOI4 1.19.2, and start a fresh non-Ironman campaign. Do not use Continue or an old save.

- [ ] **Step 4: Inspect the required party rows**

Capture the full politics-party rows at one unchanged resolution and UI scale for:

- BJK: new country-specific 32 px emblem;
- NAM: garrison military-committee identity;
- DAN: expeditionary military-committee identity, visibly distinct from NAM;
- NOD: unchanged STP emblem;
- IVN or VAD: converted existing 32 px emblem.

Use safe in-game country switching in the same fresh campaign if available; otherwise create fresh campaigns for the remaining tags. Verify no crop, overlap, baseline shift, or unacceptable line-height increase.

- [ ] **Step 5: Inspect fresh logs after fully exiting HOI4**

After complete exit, read the fresh `logs/error.log` and search case-insensitively for `party_texticon`, `unknown_party`, `GFX_BBJ`, each inspected tag, `texture`, `sprite`, and `localisation`. `GFX_BBJ` is intentionally nonexistent and must not appear; its inclusion catches accidental tag transposition from BJK. Separate pre-existing unrelated engine/DLC noise from any new task-owned error.

- [ ] **Step 6: Present the final sheets and runtime screenshots to the user**

Show both builder-generated contact sheets and the BJK, NAM, DAN, NOD, and converted-existing screenshots. Report exact fresh-log findings. Stop for user acceptance; do not merge while any requested emblem correction remains.

- [ ] **Step 7: Remove only the temporary descriptor**

After HOI4 and the launcher no longer use the entry, resolve the exact descriptor path, compare it with the expected full path, verify its unique name and worktree path, and remove that one file with `Remove-Item -LiteralPath`. Confirm the original `A-Discord.mod` hash remains unchanged.

- [ ] **Step 8: Finish the feature branch**

Use `superpowers:finishing-a-development-branch`. Present the standard integration options only after static checks, runtime evidence, and user art acceptance are all complete. Keep the branch and worktree if the user chooses later integration or requests more art changes.

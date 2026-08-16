# A-Discord Economic-System Icon Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and present three original, coherent economic-system law icon previews for visual approval at native 64x64 size.

**Architecture:** Use one built-in image-generation call per distinct medallion, guided by the same selected reference subset and a shared visual-language prompt. Save the high-resolution transparent results as auditable project sources, then mechanically produce 64x64 previews and a comparison sheet without changing active HOI4 GFX declarations.

**Tech Stack:** Built-in `image_gen`, PNG with alpha, PowerShell/.NET image inspection and deterministic thumbnail composition, Git path-scoped checks.

## Global Constraints

- Generate exactly three pilot concepts: mixed, planned-bureaucratic, and clan-oligarchic economy.
- Use an original circular dark-gunmetal medallion, recessed charcoal field, silver-grey embossed symbol, and one muted accent colour.
- Preserve a strong silhouette and broad forms that remain legible at 64x64.
- Use a genuinely transparent canvas.
- Do not include words, numbers, flags, national emblems, real-world corporate marks, watermarks, copied reference elements, clipped subjects, or opaque square backgrounds.
- Do not modify `interface/ADISCORD_ideas.gfx`, gameplay, localisation, law definitions, or unrelated dirty files during the pilot.
- Keep high-resolution source images under `tools/assets/source/economic_system_laws/` and review outputs under `docs/superpowers/reports/2026-08-16-adiscord-economic-system-icon-pilot/`.

---

### Task 1: Generate the three high-resolution medallion sources

**Files:**
- Create: `tools/assets/source/economic_system_laws/mixed_economy_medallion_source.png`
- Create: `tools/assets/source/economic_system_laws/planned_bureaucratic_economy_medallion_source.png`
- Create: `tools/assets/source/economic_system_laws/oligarchic_clan_economy_medallion_source.png`

**Interfaces:**
- Consumes: the approved design and the representative reference images `laws_economic_focus.png`, `laws_economic_focus3.png`, `laws_economic_common_prosperity.png`, `laws_interest_rates4.png`, and `GER_gunther_tax_law.png` as style references only.
- Produces: three transparent high-resolution PNG sources with one centred medallion each.

- [ ] **Step 1: Generate the mixed-economy source**

Use one built-in image-generation call with this exact production prompt:

```text
Use case: stylized-concept
Asset type: original source art for a 64x64 grand-strategy economic-law icon
Input images: supplied files are style and scale references only; do not copy their symbols, layout, or unique details
Primary request: create one circular embossed medallion for a mixed economy
Scene/backdrop: genuinely transparent canvas outside the medallion
Subject: a large balanced scale as the main silhouette; one pan carries a simple industrial gear and the other a plain coin disc; the scale pivot has a restrained oxidised-teal enamel accent
Style/medium: compact hand-painted strategy-game UI emblem, dark gunmetal rim, recessed charcoal field, silver-grey raised metal symbols, subtle wear and restrained highlights
Composition/framing: one centred front-facing medallion, symmetrical and isolated, broad forms, generous transparent margin, no element touching the canvas edge
Lighting/mood: controlled upper-left studio light, sober institutional mood, strong light-dark separation
Color palette: about eighty percent charcoal, gunmetal, and silver; muted oxidised teal as the only accent
Materials/textures: worn steel, dark enamel, shallow embossed relief
Constraints: the scale must remain the dominant readable silhouette after reduction to 64x64; one medallion only; no copied reference element
Avoid: text, letters, numbers, currency marks, flags, national emblems, logos, watermarks, photorealistic scene, people, extra props, thin line art, tiny detail, opaque square background, clipping
```

- [ ] **Step 2: Generate the planned-bureaucratic source**

Use one separate built-in image-generation call with this exact production prompt:

```text
Use case: stylized-concept
Asset type: original source art for a 64x64 grand-strategy economic-law icon
Input images: supplied files are style and scale references only; do not copy their symbols, layout, or unique details
Primary request: create one circular embossed medallion for a planned bureaucratic economy
Scene/backdrop: genuinely transparent canvas outside the medallion
Subject: a rigid administrative clipboard or ledger grid with three large blank geometric rows in front of two broad factory chimneys; the plan face carries a muted dark-red enamel accent
Style/medium: compact hand-painted strategy-game UI emblem, dark gunmetal rim, recessed charcoal field, silver-grey raised metal symbols, subtle wear and restrained highlights
Composition/framing: one centred front-facing medallion, vertically ordered and isolated, broad forms, generous transparent margin, no element touching the canvas edge
Lighting/mood: controlled upper-left studio light, severe organised mood, strong light-dark separation
Color palette: about eighty percent charcoal, gunmetal, and silver; muted dark red as the only accent
Materials/textures: worn steel, dark enamel, shallow embossed relief
Constraints: the clipboard and two chimneys must read as one bold silhouette after reduction to 64x64; blank geometric rows only; one medallion only; no copied reference element
Avoid: text, letters, numbers, handwriting, flags, national emblems, logos, watermarks, photorealistic scene, people, extra props, thin line art, tiny detail, opaque square background, clipping
```

- [ ] **Step 3: Generate the clan-oligarchic source**

Use one separate built-in image-generation call with this exact production prompt:

```text
Use case: stylized-concept
Asset type: original source art for a 64x64 grand-strategy economic-law icon
Input images: supplied files are style and scale references only; do not copy their symbols, layout, or unique details
Primary request: create one circular embossed medallion for a clan-oligarchic economy
Scene/backdrop: genuinely transparent canvas outside the medallion
Subject: three simplified dark formal sleeves converge radially and their silver-grey hands grip one central gold coin edged like a broad industrial gear; the shared grasp is the dominant symbol
Style/medium: compact hand-painted strategy-game UI emblem, dark gunmetal rim, recessed charcoal field, silver-grey raised metal, subtle wear and restrained highlights
Composition/framing: one centred front-facing medallion, compact radial symmetry, broad forms, generous transparent margin, no element touching the canvas edge
Lighting/mood: controlled upper-left studio light, secretive concentrated-power mood, strong light-dark separation
Color palette: charcoal, gunmetal, and silver with tarnished gold as the only accent
Materials/textures: worn steel, black fabric, aged gold, shallow embossed relief
Constraints: exactly three sleeves and one shared central coin-gear; the radial grasp must remain readable after reduction to 64x64; one medallion only; no copied reference element
Avoid: text, letters, numbers, currency marks, crowns, flags, national emblems, logos, watermarks, photorealistic scene, faces, extra hands, extra props, thin line art, tiny detail, opaque square background, clipping
```

- [ ] **Step 4: Inspect each generation before saving it into the project**

Render every generated result in the conversation and reject any result that violates transparency, count, clipping, or forbidden-content constraints. If one result fails, regenerate only that concept with one targeted correction while repeating the invariant constraints.

- [ ] **Step 5: Copy the accepted generated files into the three exact source paths**

Assign the three paths returned by the built-in image-generation calls to
`$mixedGeneratedPath`, `$plannedGeneratedPath`, and `$oligarchicGeneratedPath`,
then run:

```powershell
$sourceDir = 'tools/assets/source/economic_system_laws'
New-Item -ItemType Directory -Path $sourceDir -Force | Out-Null
$targets = @(
    @{ Source = $mixedGeneratedPath; Target = "$sourceDir/mixed_economy_medallion_source.png" },
    @{ Source = $plannedGeneratedPath; Target = "$sourceDir/planned_bureaucratic_economy_medallion_source.png" },
    @{ Source = $oligarchicGeneratedPath; Target = "$sourceDir/oligarchic_clan_economy_medallion_source.png" }
)
foreach ($item in $targets) {
    if (Test-Path -LiteralPath $item.Target) {
        throw "Refusing to overwrite existing pilot source: $($item.Target)"
    }
    Copy-Item -LiteralPath $item.Source -Destination $item.Target
}
```

### Task 2: Produce native-size previews and the comparison sheet

**Files:**
- Create: `docs/superpowers/reports/2026-08-16-adiscord-economic-system-icon-pilot/ADISCORD_economic_system_mixed_64.png`
- Create: `docs/superpowers/reports/2026-08-16-adiscord-economic-system-icon-pilot/ADISCORD_economic_system_planned_bureaucratic_64.png`
- Create: `docs/superpowers/reports/2026-08-16-adiscord-economic-system-icon-pilot/ADISCORD_economic_system_oligarchic_clan_64.png`
- Create: `docs/superpowers/reports/2026-08-16-adiscord-economic-system-icon-pilot/contact-sheet.png`

**Interfaces:**
- Consumes: the three accepted transparent source PNGs from Task 1.
- Produces: three exact 64x64 RGBA previews and one labelled side-by-side review sheet.

- [ ] **Step 1: Verify source alpha and bounds before resizing**

Read each PNG through `System.Drawing.Bitmap`. Record width, height, pixel format, and corner alpha. Expected: square high-resolution image, alpha-capable pixel format, and transparent corner pixels.

```powershell
Add-Type -AssemblyName System.Drawing
$sourceDir = 'tools/assets/source/economic_system_laws'
$sourcePaths = Get-ChildItem -LiteralPath $sourceDir -Filter '*_source.png'
foreach ($path in $sourcePaths) {
    $bitmap = [System.Drawing.Bitmap]::FromFile($path.FullName)
    $cornerAlpha = $bitmap.GetPixel(0, 0).A
    Write-Output "$($path.Name)|$($bitmap.Width)x$($bitmap.Height)|$($bitmap.PixelFormat)|corner-alpha=$cornerAlpha"
    if ($bitmap.Width -ne $bitmap.Height -or $cornerAlpha -ne 0) {
        $bitmap.Dispose()
        throw "Invalid transparent square source: $($path.FullName)"
    }
    $bitmap.Dispose()
}
```

- [ ] **Step 2: Create the report directory and 64x64 previews**

Use a deterministic high-quality bicubic resize onto a new 64x64 transparent ARGB bitmap. Save each derivative to its exact report path without changing the source image.

```powershell
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Drawing.Common -ErrorAction SilentlyContinue
$sourceDir = 'tools/assets/source/economic_system_laws'
$reportDir = 'docs/superpowers/reports/2026-08-16-adiscord-economic-system-icon-pilot'
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$mapping = @{
    'mixed_economy_medallion_source.png' = 'ADISCORD_economic_system_mixed_64.png'
    'planned_bureaucratic_economy_medallion_source.png' = 'ADISCORD_economic_system_planned_bureaucratic_64.png'
    'oligarchic_clan_economy_medallion_source.png' = 'ADISCORD_economic_system_oligarchic_clan_64.png'
}
foreach ($entry in $mapping.GetEnumerator()) {
    $source = [System.Drawing.Bitmap]::FromFile((Join-Path $sourceDir $entry.Key))
    $target = New-Object System.Drawing.Bitmap 64, 64, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [System.Drawing.Graphics]::FromImage($target)
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
    $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $graphics.DrawImage($source, 0, 0, 64, 64)
    $target.Save((Join-Path $reportDir $entry.Value), [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $target.Dispose()
    $source.Dispose()
}
```

- [ ] **Step 3: Create the comparison sheet**

Compose a neutral dark review sheet with three equal columns. For each column, place a large preview, the corresponding unscaled 64x64 icon, and an ASCII label: `MIXED`, `PLANNED-BUREAUCRATIC`, or `CLAN-OLIGARCHIC`. The labels belong only to the report sheet, never inside an icon.

```powershell
Add-Type -AssemblyName System.Drawing
$reportDir = 'docs/superpowers/reports/2026-08-16-adiscord-economic-system-icon-pilot'
$items = @(
    @{ File = 'ADISCORD_economic_system_mixed_64.png'; Label = 'MIXED' },
    @{ File = 'ADISCORD_economic_system_planned_bureaucratic_64.png'; Label = 'PLANNED-BUREAUCRATIC' },
    @{ File = 'ADISCORD_economic_system_oligarchic_clan_64.png'; Label = 'CLAN-OLIGARCHIC' }
)
$sheet = New-Object System.Drawing.Bitmap 900, 360, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($sheet)
$graphics.Clear([System.Drawing.Color]::FromArgb(255, 25, 28, 31))
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
$font = New-Object System.Drawing.Font 'Segoe UI', 15, ([System.Drawing.FontStyle]::Bold)
$brush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(235, 225, 225, 220))
for ($index = 0; $index -lt $items.Count; $index++) {
    $icon = [System.Drawing.Bitmap]::FromFile((Join-Path $reportDir $items[$index].File))
    $columnX = 18 + ($index * 294)
    $graphics.DrawImage($icon, $columnX + 51, 38, 192, 192)
    $graphics.DrawImageUnscaled($icon, $columnX + 115, 244)
    $labelSize = $graphics.MeasureString($items[$index].Label, $font)
    $labelX = $columnX + ((276 - $labelSize.Width) / 2)
    $graphics.DrawString($items[$index].Label, $font, $brush, $labelX, 316)
    $icon.Dispose()
}
$sheet.Save((Join-Path $reportDir 'contact-sheet.png'), [System.Drawing.Imaging.ImageFormat]::Png)
$brush.Dispose()
$font.Dispose()
$graphics.Dispose()
$sheet.Dispose()
```

- [ ] **Step 4: Verify derivative dimensions and transparency**

Read the three previews and sheet through `System.Drawing.Bitmap`. Expected: each preview is exactly `64x64`, each preview has transparent corner pixels, and the comparison sheet contains all three columns without clipping.

```powershell
Add-Type -AssemblyName System.Drawing
$reportDir = 'docs/superpowers/reports/2026-08-16-adiscord-economic-system-icon-pilot'
$previewPaths = Get-ChildItem -LiteralPath $reportDir -Filter '*_64.png'
if ($previewPaths.Count -ne 3) { throw "Expected three 64x64 previews" }
foreach ($path in $previewPaths) {
    $bitmap = [System.Drawing.Bitmap]::FromFile($path.FullName)
    $cornerAlpha = $bitmap.GetPixel(0, 0).A
    Write-Output "$($path.Name)|$($bitmap.Width)x$($bitmap.Height)|corner-alpha=$cornerAlpha"
    if ($bitmap.Width -ne 64 -or $bitmap.Height -ne 64 -or $cornerAlpha -ne 0) {
        $bitmap.Dispose()
        throw "Invalid native-size preview: $($path.FullName)"
    }
    $bitmap.Dispose()
}
$sheet = [System.Drawing.Bitmap]::FromFile((Join-Path $reportDir 'contact-sheet.png'))
if ($sheet.Width -ne 900 -or $sheet.Height -ne 360) {
    $sheet.Dispose()
    throw "Unexpected contact-sheet dimensions"
}
$sheet.Dispose()
```

- [ ] **Step 5: Inspect the 64x64 results visually**

Render the contact sheet and all three native-size previews in the conversation. Confirm that the mixed scale, planned ledger/factory, and oligarchic three-way grasp remain distinguishable without relying on the labels.

### Task 3: Review gate and repository hygiene

**Files:**
- Inspect: `tools/assets/source/economic_system_laws/*.png`
- Inspect: `docs/superpowers/reports/2026-08-16-adiscord-economic-system-icon-pilot/*.png`
- Do not modify: `interface/ADISCORD_ideas.gfx`

**Interfaces:**
- Consumes: the visual and metadata checks from Tasks 1 and 2.
- Produces: an uncommitted pilot ready for user visual approval and a precise handoff for the later integration phase.

- [ ] **Step 1: Check the exact working-tree scope**

Run `git status --short` and confirm that this pilot added only the three source PNGs, three native-size previews, and one contact sheet beyond the already committed specification and plan. Preserve all unrelated pre-existing changes.

- [ ] **Step 2: Run path-scoped whitespace and file checks**

Run `git diff --check -- tools/assets/source/economic_system_laws docs/superpowers/reports/2026-08-16-adiscord-economic-system-icon-pilot`. Binary files should introduce no textual diff errors.

- [ ] **Step 3: Present the pilot for approval**

Report the three final prompts, source paths, preview paths, and the comparison-sheet path. Explicitly state that active GFX bindings and DDS outputs were not changed. Do not stage or commit the generated art until the user accepts or requests revisions.

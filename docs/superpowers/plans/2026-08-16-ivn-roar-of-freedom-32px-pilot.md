# IVN Roar of Freedom 32 px Texticon Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild only `IVN_roar_of_freedom_party.png` as a deterministic 32x32 texticon from its existing approved master, then compare it against the current 25x25 version in fresh HOI4 campaigns.

**Architecture:** Extend the generated party-texticon manifest with a per-asset runtime canvas size that defaults to 25x25. Override only the IVN Roar of Freedom entry to 32x32, keep its sprite path stable, and use a temporary launcher descriptor pointed at an isolated worktree for the live A/B test.

**Tech Stack:** Python 3, Pillow, `unittest`, HOI4 1.19.2 Clausewitz GFX/localisation, PowerShell, Git worktrees, Codex computer-use for the launcher/game smoke test.

## Global Constraints

- Execute implementation in a dedicated worktree created with `superpowers:using-git-worktrees`; the authoritative `main` checkout contains unrelated dirty technology work.
- Use the committed base containing design commit `f0b24ecc3bac9283078e76e1195c39336edf3912`; re-audit `main` and the chosen base immediately before creating the worktree.
- Reuse `tools/assets/source/party_texticons/IVN_roar_of_freedom_source.png`; do not call image generation and do not edit the master.
- Change only `IVN_roar_of_freedom_party.png` to 32x32. Keep the emergency-committee icon and every other generated party texticon at 25x25.
- Preserve at least one transparent outer pixel: the 32x32 canvas admits at most 30x30 artwork; the 25x25 canvas remains at most 23x23 artwork.
- Keep `GFX_IVN_roar_of_freedom_party_texticon`, its runtime path, and all localisation unchanged.
- Treat `gfx/texticons/adiscord/parties/LDPR.png` as an untracked visual reference only; never stage, modify, register, or copy it.
- Update the owning builder and regenerate; never hand-edit the runtime PNG.
- Preserve all unrelated dirty files in the main checkout and stage only explicit pilot paths.
- A static pass does not prove HOI4 layout behavior. Runtime acceptance requires a full restart and fresh campaign; do not use an old save.
- Do not merge the pilot branch until the user has reviewed the A/B screenshots and accepted the 32x32 result.

---

### Task 1: Add Per-Asset Runtime Size and Rebuild the IVN Icon

**Files:**
- Modify: `tools/builders/build_adiscord_party_texticons.py:16-59`
- Modify: `tools/tests/test_build_adiscord_party_texticons.py:13-57`
- Regenerate: `gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png`

**Interfaces:**
- Produces: `AssetSpec.runtime_size: tuple[int, int]`, default `(25, 25)`.
- Produces: `render_icon(source: Path, runtime_size: tuple[int, int] = (25, 25)) -> bytes`.
- Preserves: `expected_outputs(root: Path = ROOT) -> dict[Path, bytes]`, now rendering each asset with its declared size.
- Preserves: the exact ten-entry `ASSETS` key/source/output manifest and exclusive ownership contract.

- [ ] **Step 1: Extend the focused tests with the mixed-size contract**

Add this constant immediately after `EXPECTED_KEYS`:

```python
EXPECTED_RUNTIME_SIZES = {key: (25, 25) for key in EXPECTED_KEYS}
EXPECTED_RUNTIME_SIZES["ivn_roar_of_freedom"] = (32, 32)
```

Extend `test_manifest_covers_exactly_the_ten_approved_icons`:

```python
self.assertEqual(
    {asset.key: asset.runtime_size for asset in builder.ASSETS},
    EXPECTED_RUNTIME_SIZES,
)
```

Replace the fixed-size renderer test with a two-size contract:

```python
def test_render_icon_is_deterministic_rgba_with_clear_padding(self) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "source.png"
        image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((72, 36, 440, 476), fill=(190, 30, 20, 255))
        image.save(source)

        for runtime_size in ((25, 25), (32, 32)):
            with self.subTest(runtime_size=runtime_size):
                first = builder.render_icon(source, runtime_size)
                second = builder.render_icon(source, runtime_size)
                self.assertEqual(first, second)
                with Image.open(io.BytesIO(first)) as rendered:
                    self.assertEqual(rendered.mode, "RGBA")
                    self.assertEqual(rendered.size, runtime_size)
                    self.assertIsNotNone(rendered.getchannel("A").getbbox())
                    width, height = runtime_size
                    for corner in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
                        self.assertEqual(rendered.getpixel(corner)[3], 0)
```

Update `test_runtime_outputs_are_current`:

```python
self.assertEqual(image.size, asset.runtime_size)
width, height = asset.runtime_size
for corner in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
    self.assertEqual(image.getpixel(corner)[3], 0)
```

- [ ] **Step 2: Run the focused test and record the expected RED**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_party_texticons -v
```

Expected: failure because `AssetSpec` has no `runtime_size` and `render_icon` does not accept the second argument. The committed runtime output is still 25x25.

- [ ] **Step 3: Implement the minimal mixed-size renderer**

Extend `AssetSpec`:

```python
@dataclass(frozen=True)
class AssetSpec:
    key: str
    source: Path
    output: Path
    runtime_size: tuple[int, int] = (25, 25)
```

Give only the first manifest entry an override:

```python
AssetSpec(
    "ivn_roar_of_freedom",
    Path("tools/assets/source/party_texticons/IVN_roar_of_freedom_source.png"),
    Path("gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png"),
    runtime_size=(32, 32),
),
```

Generalize the renderer without changing its image-processing choices:

```python
def render_icon(source: Path, runtime_size: tuple[int, int] = (25, 25)) -> bytes:
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        if min(rgba.size) < 512:
            raise RuntimeError(f"party texticon master must be at least 512px: {source}")
        alpha = rgba.getchannel("A")
        if alpha.getextrema() == (255, 255):
            raise RuntimeError(f"party texticon master lacks transparency: {source}")
        bbox = alpha.getbbox()
        if bbox is None:
            raise RuntimeError(f"party texticon master is fully transparent: {source}")
        artwork_size = (runtime_size[0] - 2, runtime_size[1] - 2)
        cropped = rgba.crop(bbox)
        cropped.thumbnail(artwork_size, Image.Resampling.LANCZOS)
        cropped = cropped.filter(ImageFilter.UnsharpMask(radius=0.55, percent=115, threshold=2))
        canvas = Image.new("RGBA", runtime_size, (0, 0, 0, 0))
        canvas.alpha_composite(
            cropped,
            ((runtime_size[0] - cropped.width) // 2, (runtime_size[1] - cropped.height) // 2),
        )
        output = io.BytesIO()
        canvas.save(output, format="PNG", optimize=False, compress_level=9)
        return output.getvalue()
```

Pass the manifest value through `expected_outputs`:

```python
def expected_outputs(root: Path = ROOT) -> dict[Path, bytes]:
    return {
        root / asset.output: render_icon(root / asset.source, asset.runtime_size)
        for asset in ASSETS
    }
```

- [ ] **Step 4: Run the focused test and confirm that only committed-output drift remains**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_party_texticons -v
```

Expected: the manifest and renderer tests pass; `test_runtime_outputs_are_current` fails only because the IVN Roar of Freedom runtime PNG has not been regenerated.

- [ ] **Step 5: Regenerate through the owning builder**

Run:

```powershell
python -B -m tools.builders.build_adiscord_party_texticons --apply
python -B -m tools.builders.build_adiscord_party_texticons --check
```

Expected: the check prints `Party texticons are current.` and Git reports only the IVN Roar of Freedom runtime PNG as a changed generated output.

- [ ] **Step 6: Prove output dimensions, transparency, and idempotence**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_party_texticons -v
$before = Get-ChildItem -LiteralPath 'gfx/texticons/adiscord/parties' -Filter '*.png' -File -Recurse | Sort-Object FullName | Get-FileHash -Algorithm SHA256
python -B -m tools.builders.build_adiscord_party_texticons --apply
$after = Get-ChildItem -LiteralPath 'gfx/texticons/adiscord/parties' -Filter '*.png' -File -Recurse | Sort-Object FullName | Get-FileHash -Algorithm SHA256
if (Compare-Object $before.Hash $after.Hash) { throw 'Party texticon builder is not idempotent.' }
```

Expected: all focused tests pass and the two hash lists are identical.

- [ ] **Step 7: Verify the exact task scope**

Run:

```powershell
$expected = @(
  'gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png',
  'tools/builders/build_adiscord_party_texticons.py',
  'tools/tests/test_build_adiscord_party_texticons.py'
) | Sort-Object
$actual = @(git status --short | ForEach-Object { $_.Substring(3).Replace('\', '/') }) | Sort-Object
if (Compare-Object $expected $actual) { throw "Unexpected pilot paths: $($actual -join ', ')" }
```

Expected: exactly the builder, its test, and the single runtime PNG.

- [ ] **Step 8: Run focused integration checks**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_party_texticons tools.tests.test_wrk_party_icon -v
python -B -m unittest tools.tests.test_generated_output_ownership.GeneratedOutputOwnershipTests.test_party_texticon_registry_exactly_matches_assets_and_is_exclusive -v
python -B tools/validate_tc.py --limit 300
git diff --check
```

Expected: all commands exit zero. Do not run or repair unrelated generated-output families.

- [ ] **Step 9: Commit the isolated pilot**

Run:

```powershell
git add -- 'tools/builders/build_adiscord_party_texticons.py' 'tools/tests/test_build_adiscord_party_texticons.py' 'gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png'
git diff --cached --check
git commit -m "test: pilot 32px IVN party texticon"
```

Expected: one commit containing exactly three paths; the implementation worktree is clean.

---

### Task 2: Run Static Release Gates and Prepare A/B Launchers

**Files:**
- Verify only in the repository.
- Create temporarily outside Git: `C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/mod/A-Discord-IVN-32px-Pilot.mod`

**Interfaces:**
- Consumes: the Task 1 commit and worktree path.
- Produces: a clean static-verification report and a launcher-visible pilot mod that points to the worktree.
- Preserves: the existing `A-Discord.mod` descriptor pointing to the main checkout for the 25x25 baseline.

- [ ] **Step 1: Run the complete pilot static gate**

Run:

```powershell
python -B -m tools.builders.build_adiscord_party_texticons --check
python -B -m unittest tools.tests.test_build_adiscord_party_texticons tools.tests.test_adiscord_party_texticons tools.tests.test_wrk_party_icon -v
python -B -m unittest tools.tests.test_generated_output_ownership.GeneratedOutputOwnershipTests.test_party_texticon_registry_exactly_matches_assets_and_is_exclusive -v
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Expected: all commands exit zero and the implementation worktree remains clean.

- [ ] **Step 2: Inspect the committed runtime PNG**

Open `gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png` with `view_image`, then run:

```powershell
python -B -c "from PIL import Image; p='gfx/texticons/adiscord/parties/IVN/IVN_roar_of_freedom_party.png'; im=Image.open(p); assert im.mode=='RGBA'; assert im.size==(32,32); a=im.getchannel('A'); assert a.getbbox(); assert all(im.getpixel(xy)[3]==0 for xy in ((0,0),(31,0),(0,31),(31,31))); print('IVN_32PX_PREFLIGHT_OK')"
```

Expected: the enlarged emblem retains its dark contour, non-empty artwork, and transparent corners.

- [ ] **Step 3: Create the temporary pilot descriptor without modifying the original**

Copy the existing external descriptor to the exact temporary path:

```powershell
$source = 'C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/mod/A-Discord.mod'
$pilot = 'C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/mod/A-Discord-IVN-32px-Pilot.mod'
if (Test-Path -LiteralPath $pilot) { throw "Pilot descriptor already exists: $pilot" }
Copy-Item -LiteralPath $source -Destination $pilot
```

Use `apply_patch` on the copied file to change only:

```text
name="A-Discord — IVN 32px Pilot"
path="C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/mod/A-Discord/.worktrees/ivn-roar-32px-pilot"
```

Verify that the original descriptor hash is unchanged, the pilot descriptor contains the unique name and exact worktree path, and neither descriptor is inside the Git worktree.

- [ ] **Step 4: Record the runtime checklist before launching**

The two runs must use identical game version, UI scale, resolution, country, and politics view. Each run must start after fully exiting HOI4, and each must use a fresh campaign as IVN.

Capture:

1. 25x25 baseline with only `A-Discord` active.
2. 32x32 pilot with only `A-Discord — IVN 32px Pilot` active.
3. The entire party-name row, not a crop of the icon alone.
4. Fresh `error.log` lines mentioning `IVN_roar_of_freedom`, `party_texticon`, `texture`, or `sprite`.

---

### Task 3: Perform the Fresh-Campaign HOI4 A/B Smoke Test

**Files:**
- Runtime evidence only: screenshots and fresh logs saved under the task report/evidence directory, not committed as game content.
- Delete after the test: `C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/mod/A-Discord-IVN-32px-Pilot.mod`.

**Interfaces:**
- Consumes: the original main-checkout mod as the 25x25 control and the temporary pilot mod as the 32x32 treatment.
- Produces: a user-reviewable A/B result and a pass/fail decision against the design acceptance criteria.

- [ ] **Step 1: Load the computer-use instructions and start the 25x25 control run**

Use the `computer-use:computer-use` skill. Through Steam/Paradox Launcher, activate only the original `A-Discord` mod, fully start HOI4 1.19.2, and create a fresh campaign as IVN. Do not use Continue or an old save.

- [ ] **Step 2: Capture the baseline politics view and fresh log evidence**

Open IVN's politics interface, capture the full `Рёв свободы` party row at the user's normal UI scale, and record resolution/UI scale. Exit HOI4 completely. Copy or timestamp the fresh log excerpt before the second launch.

- [ ] **Step 3: Start the 32x32 pilot run**

In the launcher, deactivate the original mod and activate only `A-Discord — IVN 32px Pilot`. Start HOI4 again and create another fresh campaign as IVN with the same settings.

- [ ] **Step 4: Capture the pilot politics view and fresh log evidence**

Capture the same full party row. Verify visibly:

- no crop at any edge;
- no overlap with the party name or neighbouring rows;
- no baseline shift or unacceptable line-height increase;
- materially clearer lion-and-broken-chain detail;
- no new sprite/texture error in the fresh log.

Exit HOI4 completely before cleanup.

- [ ] **Step 5: Present the A/B result to the user**

Show both screenshots together and report the fresh-log result. Ask the user to choose one of these outcomes:

1. Accept 32x32 as the target size for the forthcoming 17 country-specific and 24 generic emblems.
2. Keep new icons at 25x25.
3. Run a separate 31x32 TFR-matching pilot.

Do not merge the pilot branch before this choice.

- [ ] **Step 6: Remove only the temporary launcher descriptor**

After confirming HOI4 and the launcher no longer use the pilot entry, verify the resolved path equals the exact temporary file and delete it:

```powershell
$pilot = (Resolve-Path -LiteralPath 'C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/mod/A-Discord-IVN-32px-Pilot.mod').Path
$expected = [IO.Path]::GetFullPath('C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/mod/A-Discord-IVN-32px-Pilot.mod')
if ($pilot -ne $expected) { throw "Refusing to remove unexpected descriptor: $pilot" }
Remove-Item -LiteralPath $pilot
```

Keep the implementation worktree and branch until the user accepts or rejects the pilot and chooses the integration outcome.

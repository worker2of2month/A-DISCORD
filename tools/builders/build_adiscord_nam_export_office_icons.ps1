param([switch]$Apply, [switch]$Check)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$repo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$assetDir = Join-Path $repo 'gfx/interface/state_modifiers/adiscord'
$source = [System.Drawing.Bitmap]::new((Join-Path $assetDir 'company_quarters.png'))
$glyphs = @{
    I = @('111', '010', '010', '010', '010', '010', '111')
    V = @('10001', '10001', '10001', '01010', '01010', '00100', '00100')
}
$tiers = @('I', 'II', 'III', 'IV', 'V')
$changed = 0
try {
    if ($source.Width -ne 32 -or $source.Height -ne 32) { throw 'Expected the native 32x32 office icon.' }
    for ($tier = 0; $tier -lt $tiers.Count; $tier++) {
        $bitmap = $source.Clone()
        $points = [System.Collections.Generic.List[System.Drawing.Point]]::new()
        $width = -1
        foreach ($letter in $tiers[$tier].ToCharArray()) { $width += $glyphs[[string]$letter][0].Length + 1 }
        $cursor = 31 - $width
        foreach ($letter in $tiers[$tier].ToCharArray()) {
            $glyph = $glyphs[[string]$letter]
            for ($row = 0; $row -lt 7; $row++) {
                for ($column = 0; $column -lt $glyph[$row].Length; $column++) {
                    if ($glyph[$row][$column] -eq '1') {
                        $points.Add([System.Drawing.Point]::new($cursor + $column, 1 + $row))
                    }
                }
            }
            $cursor += $glyph[0].Length + 1
        }
        foreach ($point in $points) {
            for ($dx = -1; $dx -le 1; $dx++) {
                for ($dy = -1; $dy -le 1; $dy++) {
                    $bitmap.SetPixel($point.X + $dx, $point.Y + $dy, [System.Drawing.Color]::FromArgb(255, 24, 20, 15))
                }
            }
        }
        foreach ($point in $points) {
            $bitmap.SetPixel($point.X, $point.Y, [System.Drawing.Color]::FromArgb(255, 255, 231, 164))
        }
        $stream = [System.IO.MemoryStream]::new()
        $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
        $bytes = $stream.ToArray()
        $target = Join-Path $assetDir "nam_export_office_$($tier + 1).png"
        $different = -not (Test-Path -LiteralPath $target)
        if (-not $different) {
            $different = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($target)) -ne [Convert]::ToBase64String($bytes)
        }
        if ($different) {
            $changed++
            if ($Apply) { [System.IO.File]::WriteAllBytes($target, $bytes) }
        }
        $stream.Dispose()
        $bitmap.Dispose()
    }
}
finally { $source.Dispose() }
Write-Output "Office icons: $changed changed; apply=$Apply"
if ($Check -and $changed -gt 0) { exit 1 }

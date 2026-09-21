param(
    [string]$ModRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$descriptor = Join-Path $ModRoot "descriptor.mod"
if (-not (Test-Path -LiteralPath $descriptor)) {
    throw "descriptor.mod not found at: $descriptor"
}

$documents = [Environment]::GetFolderPath("MyDocuments")
$hoiModDir = Join-Path $documents "Paradox Interactive\Hearts of Iron IV\mod"
New-Item -ItemType Directory -Force -Path $hoiModDir | Out-Null

$externalDescriptor = Join-Path $hoiModDir "Abyss-of-Discord-Git.mod"

$lines = Get-Content -LiteralPath $descriptor -Encoding UTF8 |
    Where-Object { $_ -notmatch '^\s*remote_file_id\s*=' -and $_ -notmatch '^\s*path\s*=' }

$normalizedPath = $ModRoot.Replace("\", "/").Replace('"', '\\"')
$content = @(
    $lines
    "path=`"$normalizedPath`""
) -join [Environment]::NewLine

[System.IO.File]::WriteAllText(
    $externalDescriptor,
    $content + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Installed local Git descriptor:"
Write-Host "  $externalDescriptor"
Write-Host ""
Write-Host "Mod root:"
Write-Host "  $ModRoot"
Write-Host ""
Write-Host "In the HOI4 launcher, enable ONLY this local Git copy of Abyss of Discord."
Write-Host "Disable the Workshop copy and any older local A-Discord entries before comparing multiplayer checksums."

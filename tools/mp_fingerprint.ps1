param(
    [string]$ModRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$roots = @("common", "events", "history", "map")
$files = New-Object System.Collections.Generic.List[System.IO.FileInfo]
foreach ($root in $roots) {
    $full = Join-Path $ModRoot $root
    if (Test-Path -LiteralPath $full) {
        Get-ChildItem -LiteralPath $full -Recurse -File | ForEach-Object { $files.Add($_) }
    }
}

$descriptor = Join-Path $ModRoot "descriptor.mod"
if (Test-Path -LiteralPath $descriptor) {
    $files.Add((Get-Item -LiteralPath $descriptor))
}

$records = foreach ($file in $files | Sort-Object FullName) {
    $relative = [System.IO.Path]::GetRelativePath($ModRoot, $file.FullName).Replace("\", "/")
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    $relative + [char]9 + $hash
}

$payloadText = ($records -join [char]10) + [char]10
$payload = [System.Text.Encoding]::UTF8.GetBytes($payloadText)
$sha = [System.Security.Cryptography.SHA256]::HashData($payload)
$fingerprintValue = [Convert]::ToHexString($sha).ToLowerInvariant()

Write-Host "A-Discord gameplay fingerprint:"
Write-Host "  $fingerprintValue"
Write-Host "Files hashed: $($records.Count)"

if (Test-Path (Join-Path $ModRoot ".git")) {
    Push-Location $ModRoot
    try {
        $head = (git rev-parse HEAD).Trim()
        $dirty = git status --porcelain
        Write-Host "Git HEAD:"
        Write-Host "  $head"
        if ($dirty) {
            Write-Host "WARNING: working tree has local/untracked changes:"
            $dirty | ForEach-Object { Write-Host "  $_" }
        } else {
            Write-Host "Working tree: clean"
        }
    }
    finally {
        Pop-Location
    }
}

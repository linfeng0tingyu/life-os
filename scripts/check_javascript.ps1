$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot = Join-Path $projectRoot "src\life_os\static\js"
$files = Get-ChildItem -LiteralPath $sourceRoot -Recurse -File -Filter "*.js"
$failed = @()

foreach ($file in $files) {
    $output = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 |
        & node --check --input-type=module 2>&1
    if ($LASTEXITCODE -ne 0) {
        $failed += [PSCustomObject]@{
            File = $file.FullName.Substring($projectRoot.Length + 1)
            Output = ($output -join [Environment]::NewLine)
        }
    }
}

if ($failed.Count -gt 0) {
    foreach ($failure in $failed) {
        Write-Error ("JavaScript syntax error in {0}:{1}{2}" -f $failure.File, [Environment]::NewLine, $failure.Output)
    }
    exit 1
}

Write-Output ("JavaScript module syntax checks passed: {0}" -f $files.Count)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$sourceDatabaseUrl = if ($env:SOURCE_DATABASE_URL) {
    $env:SOURCE_DATABASE_URL
} else {
    "sqlite:///$((Join-Path $projectRoot 'data\\signal_flow.db').Replace('\', '/'))"
}

$targetDatabaseUrl = if ($env:TARGET_DATABASE_URL) {
    $env:TARGET_DATABASE_URL
} elseif ($env:DATABASE_URL) {
    $env:DATABASE_URL
} else {
    throw 'Set TARGET_DATABASE_URL or DATABASE_URL before running this script.'
}

& '.\.venv\Scripts\python.exe' -m app.db_migrate `
    --source-url $sourceDatabaseUrl `
    --target-url $targetDatabaseUrl `
    --reset-target

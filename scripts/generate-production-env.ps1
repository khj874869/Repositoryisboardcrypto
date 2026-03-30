param(
    [Parameter(Mandatory = $true)]
    [string]$Domain,

    [Parameter(Mandatory = $true)]
    [string]$DatabaseUrl,

    [string]$OutputPath = '.env.production',

    [string]$AndroidPackageName = '',

    [string]$AndroidSha256CertFingerprints = '',

    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$argsList = @(
    '-m', 'app.release_values',
    '--domain', $Domain,
    '--database-url', $DatabaseUrl,
    '--output', $OutputPath
)

if ($AndroidPackageName) {
    $argsList += @('--android-package-name', $AndroidPackageName)
}

if ($AndroidSha256CertFingerprints) {
    $argsList += @('--android-sha256-cert-fingerprints', $AndroidSha256CertFingerprints)
}

if ($Force) {
    $argsList += '--force'
}

& '.\.venv\Scripts\python.exe' @argsList

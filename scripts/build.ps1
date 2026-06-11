<#
.SYNOPSIS
    Vector Tracer Pro — PyInstaller Build Script (stub)

.DESCRIPTION
    Runs PyInstaller with the project spec file to produce a standalone EXE.
    Populate this script fully in Sprint 8 (Packaging & Release).
#>

[CmdletBinding()]
param(
    [string]$SpecFile = "packaging\pyinstaller\vector_tracer_pro.spec",
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Vector Tracer Pro — Build" -ForegroundColor Cyan
Write-Host "Spec file: $SpecFile" -ForegroundColor Cyan

if ($Clean) {
    Write-Host "Cleaning previous build artefacts..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "packaging\pyinstaller\dist"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "packaging\pyinstaller\build"
}

# TODO (Sprint 8): Implement full PyInstaller build logic
Write-Host "Build script not yet implemented. Placeholder for Sprint 8." -ForegroundColor Yellow

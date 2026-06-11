<#
.SYNOPSIS
    Vector Tracer Pro — External Dependency Checker

.DESCRIPTION
    Verifies that Potrace and Inkscape are available on PATH and meet
    the minimum version requirements. Exits with code 0 on success,
    or code 1 if any dependency is missing or incompatible.

.NOTES
    Run this script before launching the application or building the installer.
    Minimum versions: Potrace >= 1.16, Inkscape >= 1.0.0
#>

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
$MinPotraceVersion  = [Version]"1.16"
$MinInkscapeVersion = [Version]"1.0.0"
$PotraceDownloadUrl  = "http://potrace.sourceforge.net/#downloading"
$InkscapeDownloadUrl = "https://inkscape.org/release/"

$PassColor = "Green"
$FailColor = "Red"
$WarnColor = "Yellow"
$InfoColor = "Cyan"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

function Write-Status {
    param(
        [string]$Label,
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host ("  [{0,-8}] {1}" -f $Label, $Message) -ForegroundColor $Color
}

function Get-SemanticVersion {
    <#
    .SYNOPSIS
        Extracts the first X.Y.Z or X.Y version string from a text blob.
    #>
    param([string]$Text)

    if ($Text -match '(\d+\.\d+(?:\.\d+)?)') {
        try { return [Version]$Matches[1] } catch { }
    }
    return $null
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "  Vector Tracer Pro — Dependency Check" -ForegroundColor $InfoColor
Write-Host "  =====================================" -ForegroundColor $InfoColor
Write-Host ""

$allPassed = $true

# ---------------------------------------------------------------------------
# 1. Check Potrace
# ---------------------------------------------------------------------------
Write-Host "  Checking Potrace..." -ForegroundColor $InfoColor

$potraceCmd = Get-Command "potrace" -ErrorAction SilentlyContinue

if ($null -eq $potraceCmd) {
    Write-Status "MISSING" "potrace not found on PATH." $FailColor
    Write-Status "HELP" "Download: $PotraceDownloadUrl" $WarnColor
    Write-Status "HELP" "After installing, ensure the directory is on your PATH." $WarnColor
    $allPassed = $false
} else {
    $potraceExe = $potraceCmd.Source
    Write-Status "FOUND" "potrace at: $potraceExe" $PassColor

    try {
        $rawOutput  = & potrace --version 2>&1 | Out-String
        $detectedVer = Get-SemanticVersion $rawOutput

        if ($null -eq $detectedVer) {
            Write-Status "WARN" "Could not parse Potrace version from output." $WarnColor
            Write-Status "OUTPUT" $rawOutput.Trim() $WarnColor
        } elseif ($detectedVer -lt $MinPotraceVersion) {
            Write-Status "OLD" "Detected v$detectedVer — minimum required: v$MinPotraceVersion" $FailColor
            Write-Status "HELP" "Download a newer version: $PotraceDownloadUrl" $WarnColor
            $allPassed = $false
        } else {
            Write-Status "OK" "Version $detectedVer (>= $MinPotraceVersion)" $PassColor
        }
    } catch {
        Write-Status "ERROR" "Failed to run 'potrace --version': $_" $FailColor
        $allPassed = $false
    }
}

Write-Host ""

# ---------------------------------------------------------------------------
# 2. Check Inkscape
# ---------------------------------------------------------------------------
Write-Host "  Checking Inkscape..." -ForegroundColor $InfoColor

$inkscapeCmd = Get-Command "inkscape" -ErrorAction SilentlyContinue

if ($null -eq $inkscapeCmd) {
    Write-Status "MISSING" "inkscape not found on PATH." $FailColor
    Write-Status "HELP" "Download: $InkscapeDownloadUrl" $WarnColor
    Write-Status "HELP" "During installation, enable the 'Add to PATH' option." $WarnColor
    $allPassed = $false
} else {
    $inkscapeExe = $inkscapeCmd.Source
    Write-Status "FOUND" "inkscape at: $inkscapeExe" $PassColor

    try {
        $rawOutput   = & inkscape --version 2>&1 | Out-String
        $detectedVer = Get-SemanticVersion $rawOutput

        if ($null -eq $detectedVer) {
            Write-Status "WARN" "Could not parse Inkscape version from output." $WarnColor
            Write-Status "OUTPUT" $rawOutput.Trim() $WarnColor
        } elseif ($detectedVer -lt $MinInkscapeVersion) {
            Write-Status "OLD" "Detected v$detectedVer — minimum required: v$MinInkscapeVersion" $FailColor
            Write-Status "HELP" "Download a newer version: $InkscapeDownloadUrl" $WarnColor
            $allPassed = $false
        } else {
            Write-Status "OK" "Version $detectedVer (>= $MinInkscapeVersion)" $PassColor

            # Verify headless (--actions) support — required for multi-colour tracing
            $headlessTest = & inkscape --actions="quit" 2>&1 | Out-String
            if ($headlessTest -match "unrecognized option|unknown option|invalid") {
                Write-Status "WARN" "--actions flag not supported. Multi-colour tracing may fail." $WarnColor
            } else {
                Write-Status "OK" "Headless --actions flag is supported." $PassColor
            }
        }
    } catch {
        Write-Status "ERROR" "Failed to run 'inkscape --version': $_" $FailColor
        $allPassed = $false
    }
}

Write-Host ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
if ($allPassed) {
    Write-Host "  [PASS] All dependencies satisfied. Ready to run Vector Tracer Pro." `
        -ForegroundColor $PassColor
    Write-Host ""
    exit 0
} else {
    Write-Host "  [FAIL] One or more dependencies are missing or incompatible." `
        -ForegroundColor $FailColor
    Write-Host "         Please resolve the issues above and re-run this script." `
        -ForegroundColor $FailColor
    Write-Host ""
    exit 1
}

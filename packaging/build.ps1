<#
Builds Setup-TALeport.exe:
  1. production UI (frontend/dist) and the .ico if missing;
  2. PyInstaller one-folder app (dist/TALeport);
  3. optional code signing of TALeport.exe;
  4. Inno Setup installer (packaging/output/Setup-TALeport.exe).

Usage (from the repository root):
  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
  powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -SkipInstaller

Code signing (optional, none for now): set TALEPORT_SIGN_CERT to a .pfx path and
TALEPORT_SIGN_PASSWORD to its password; signtool.exe (Windows SDK) must be on PATH.
#>
param(
    [switch]$SkipInstaller,
    [string]$AppUrl = $env:TALEPORT_APP_URL
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"

function Step($text) { Write-Host "`n== $text ==" -ForegroundColor Cyan }

$version = (Select-String -Path (Join-Path $root "backend\taleport\__init__.py") `
    -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value
Write-Host "TALeport $version"

Step "UI"
Push-Location (Join-Path $root "frontend")
try {
    if (-not (Test-Path "node_modules")) { npm ci; if ($LASTEXITCODE) { throw "npm ci failed" } }
    if (-not (Test-Path (Join-Path $root "assets\brand\taleport.ico"))) {
        npm run icon; if ($LASTEXITCODE) { throw "icon build failed" }
    }
    npm run build; if ($LASTEXITCODE) { throw "UI build failed" }
} finally { Pop-Location }

Step "PyInstaller"
& $python -m pip install --quiet -e "$root\backend[build]"
if ($LASTEXITCODE) { throw "pip install failed" }
& $python -m PyInstaller --noconfirm --clean `
    --distpath (Join-Path $root "dist") --workpath (Join-Path $root "build") `
    (Join-Path $PSScriptRoot "taleport.spec")
if ($LASTEXITCODE) { throw "PyInstaller failed" }

$signArgs = @()
if ($env:TALEPORT_SIGN_CERT) {
    Step "Code signing"
    $sign = "signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 " +
            "/f `"$env:TALEPORT_SIGN_CERT`" /p `"$env:TALEPORT_SIGN_PASSWORD`""
    & cmd /c "$sign `"$root\dist\TALeport\TALeport.exe`""
    if ($LASTEXITCODE) { throw "signing failed" }
    $signArgs = @("/DSignTool=sign", "/Ssign=$sign `$f")
}

if ($SkipInstaller) { Write-Host "`nApp ready in dist\TALeport"; exit 0 }

Step "Inno Setup"
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found (winget install JRSoftware.InnoSetup)" }
$defines = @("/DAppVersion=$version")
if ($AppUrl) { $defines += "/DAppURL=$AppUrl" }
& $iscc @defines @signArgs (Join-Path $PSScriptRoot "taleport.iss")
if ($LASTEXITCODE) { throw "Inno Setup failed" }

$setup = Join-Path $PSScriptRoot "output\Setup-TALeport.exe"
Write-Host "`nInstaller: $setup ($([math]::Round((Get-Item $setup).Length / 1MB, 1)) MB)" -ForegroundColor Green

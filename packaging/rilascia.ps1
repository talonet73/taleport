# TALeport: tests, installer, commit + tag + push, GitHub Release - one double click.
# Uses the version in backend\taleport\__init__.py and its section of CHANGELOG.md.
# GitHub access comes from the credentials git already stores on this PC (never logged).
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot
Set-Location $root
$version = ([regex]::Match((Get-Content backend\taleport\__init__.py -Raw), '__version__ = "([^"]+)"')).Groups[1].Value
$out = Join-Path $root "packaging\output"
New-Item -ItemType Directory -Force $out | Out-Null
$log = Join-Path $out "rilascia-$version.log"
Set-Content -Path $log -Value "TALeport $version - $(Get-Date)" -Encoding UTF8
function Log($t) { Add-Content -Path $log -Value $t -Encoding UTF8; Write-Host $t }
function Step($name, [scriptblock]$block) {
    Log "== $name =="
    # Native tools write progress to stderr: in Windows PowerShell 5.1 that must not count
    # as a failure, only the exit code does.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $text = & $block 2>&1 | Out-String
    $ErrorActionPreference = $previous
    Add-Content -Path $log -Value $text -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "$name failed (exit $LASTEXITCODE)" }
}
try {
    $py = Join-Path $root "backend\.venv\Scripts\python.exe"
    Step "dependencies" { & $py -m pip install --disable-pip-version-check -q -e "backend[dev,build]" }
    Push-Location backend
    Step "backend tests" { & $py -m pytest -q -p no:cacheprovider }
    Pop-Location
    Push-Location frontend
    Step "typecheck" { cmd /c npm run typecheck }
    Step "frontend tests" { cmd /c npx vitest run }
    Pop-Location
    Step "installer" { powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build.ps1 }
    $exe = Join-Path $out "Setup-TALeport.exe"

    $msgFile = Join-Path $out "commit-$version.txt"
    if (-not (Test-Path $msgFile)) { Set-Content $msgFile "TALeport $version" -Encoding UTF8 }
    $who = @("-c", "user.name=ares", "-c", "user.email=178192068+talonet73@users.noreply.github.com")
    Step "commit" { git add -A; git @who commit -F $msgFile }
    Step "tag" { git @who tag -a "v$version" -m "TALeport $version" }
    Step "push" { git push origin main; git push origin "v$version" }

    Log "== release =="
    $cred = "protocol=https`nhost=github.com`n`n" | git credential fill
    $token = ($cred | Where-Object { $_ -like "password=*" }) -replace "^password=", ""
    if (-not $token) { throw "no stored GitHub credentials" }
    $repo = "talonet73/taleport"
    $headers = @{ Authorization = "Bearer $token"; Accept = "application/vnd.github+json"; "X-GitHub-Api-Version" = "2022-11-28"; "User-Agent" = "TALeport-release" }
    $changelog = [IO.File]::ReadAllText((Join-Path $root "CHANGELOG.md"), [Text.Encoding]::UTF8)
    $section = [regex]::Match($changelog, "(?s)## $([regex]::Escape($version)) [^\n]*\n(.*?)(?=\n## |\z)").Groups[1].Value.Trim()
    $notes = [string]($section + "`n`nThe installer is not code-signed yet: Windows SmartScreen may ask to confirm (""More info"" -> ""Run anyway"").")
    $body = @{ tag_name = "v$version"; name = "TALeport $version"; body = $notes; draft = $true } | ConvertTo-Json
    $rel = Invoke-RestMethod -Method Post -Uri "https://api.github.com/repos/$repo/releases" -Headers $headers -Body ([Text.Encoding]::UTF8.GetBytes($body)) -ContentType "application/json; charset=utf-8"
    Log "draft $($rel.id), uploading installer..."
    $asset = Invoke-RestMethod -Method Post -Uri "https://uploads.github.com/repos/$repo/releases/$($rel.id)/assets?name=Setup-TALeport.exe" -Headers $headers -InFile $exe -ContentType "application/octet-stream" -TimeoutSec 3600
    Log "uploaded $($asset.size) bytes"
    $pub = @{ draft = $false; make_latest = "true" } | ConvertTo-Json
    $rel = Invoke-RestMethod -Method Patch -Uri "https://api.github.com/repos/$repo/releases/$($rel.id)" -Headers $headers -Body $pub -ContentType "application/json"
    Log "published: $($rel.html_url)"
    Log "== DONE =="
} catch {
    Log "ERROR: $($_.Exception.Message)"
    if ($_.ErrorDetails.Message) { Log "DETAILS: $($_.ErrorDetails.Message)" }
}
Write-Host ""
Write-Host "Finito. Puoi chiudere questa finestra."
Read-Host

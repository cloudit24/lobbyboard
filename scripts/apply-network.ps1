# Applies the port saved in Admin > Network settings: writes it to .env and
# restarts the containers. Run from anywhere on the Windows server.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$port = (docker compose exec -T web python -c "import json;print(json.load(open('/data/network.json'))['port'])").Trim()
$lines = Get-Content .env
if ($lines -match '^PORT=') { $lines = $lines -replace '^PORT=.*', "PORT=$port" } else { $lines += "PORT=$port" }
[IO.File]::WriteAllLines((Resolve-Path .env), $lines)  # UTF-8 without BOM
docker compose up -d
Write-Host "Now listening on port $port"

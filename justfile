set shell := ["pwsh", "-NoProfile", "-Command"]

default: help

help:
    @just --list

# Add a package to the workspace venv (records in parent pyproject.toml)
add *args:
    uv --directory .. add {{args}}

# Run a script using the workspace venv
run *args:
    uv run {{args}}

# Run tests
test:
    uv run pytest

# Start all platform services (build images if needed)
up *args:
    docker compose -f infra/docker-compose.yml up --build -d {{args}}

# Stop and remove all platform containers
down:
    docker compose -f infra/docker-compose.yml down

# Show platform service status
ps:
    docker compose -f infra/docker-compose.yml ps

# Tail logs for a service (e.g. just logs idp)
logs *args:
    docker compose -f infra/docker-compose.yml logs --follow {{args}}

# Restart a single service (e.g. just restart caddy)
restart service:
    docker compose -f infra/docker-compose.yml restart {{service}}

# Smoke-test: verify all app hostnames reach the Harness /health endpoint
smoke:
    @$hosts = Get-Content infra/hosts.txt | Where-Object { $_ -match '^\d' } | ForEach-Object { ($_ -split '\s+')[1] } | Where-Object { $_ -ne 'idp.local' }; \
    $pass = 0; $fail = 0; \
    foreach ($h in $hosts) { \
        try { \
            $r = Invoke-WebRequest -Uri "http://$h/health" -TimeoutSec 3 -ErrorAction Stop; \
            if ($r.StatusCode -eq 200) { Write-Host "OK    $h"; $pass++ } \
            else { Write-Host "FAIL  $h  ($($r.StatusCode))"; $fail++ } \
        } catch { Write-Host "FAIL  $h  ($_)"; $fail++ } \
    }; \
    Write-Host ""; Write-Host "$pass passed, $fail failed"; \
    if ($fail -gt 0) { exit 1 }

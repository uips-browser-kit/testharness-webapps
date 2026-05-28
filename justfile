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
    @$hosts = @( \
        "harness.local", \
        "sf-dev.local","salesforce.company.com", \
        "org.crm.dynamics.com","dynamics.company.com", \
        "instance.service-now.com","servicedesk.company.com", \
        "erp-dev.company.com","erp.company.com", \
        "oracle-dev.company.com","finance.company.com", \
        "tenant.workday.com","hr.company.com", \
        "jira.company.atlassian.net","jira.company.com", \
        "confluence.company.atlassian.net","wiki.company.com", \
        "tenant.sharepoint.com","intranet.company.com", \
        "app.powerbi.com","analytics.company.com", \
        "server.tableau.com","tableau.company.com", \
        "apps.powerapps.com","apps.company.com" \
    ); \
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

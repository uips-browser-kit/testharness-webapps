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

# Run harness-cli inspection tool (route-match, view-data, challenge …)
cli *args:
    uv run harness-cli {{if args != "" {args} else {"--help"}}}

# Run integration tests against the live stack (requires: just up)
integration:
    uv run pytest -m integration -v

# Check host routing (phase 1) and HTTP reachability (phase 2)
check-hosts *args:
    pwsh -NoProfile -File scripts/check-hosts.ps1 {{args}}

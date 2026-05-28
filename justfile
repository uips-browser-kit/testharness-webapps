set windows-shell := ["pwsh", "-NoLogo", "-Command"]

# Add a package to the workspace venv (records in parent pyproject.toml)
add *args:
    uv --directory .. add {{args}}

# Run a script using the workspace venv
run *args:
    uv run {{args}}

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

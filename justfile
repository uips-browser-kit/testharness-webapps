# Add a package to the workspace venv (records in parent pyproject.toml)
add *args:
    uv --directory .. add {{args}}

# Run a script using the workspace venv
run *args:
    uv run {{args}}

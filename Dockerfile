FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
RUN uv pip install --system .
CMD ["uvicorn", "src.harness.app:app", "--host", "0.0.0.0", "--port", "8000"]

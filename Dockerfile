FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN pip install uv && uv pip install --system fastapi "uvicorn[standard]"
COPY src/ src/
CMD ["uvicorn", "src.harness.app:app", "--host", "0.0.0.0", "--port", "8000"]

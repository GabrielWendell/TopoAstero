FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /usr/local/bin/
WORKDIR /opt/topoastero
COPY . .
RUN uv sync --locked --group dev --extra astronomy
ENTRYPOINT ["uv", "run", "python", "workflows/run_stage12_hybrid.py"]

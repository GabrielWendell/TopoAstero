FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy
WORKDIR /workspace/TopoAstero
RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir uv==0.12.15
COPY . .
RUN uv sync --locked --group dev --extra astronomy
CMD ["uv", "run", "python", "workflows/validate_stage11.py", "--root", "."]

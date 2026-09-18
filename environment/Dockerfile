FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /workspace/TopoAstero

RUN python -m pip install --no-cache-dir uv==0.12.15

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --group dev --no-install-project

COPY . .
RUN uv sync --locked --group dev && \
    uv run topoastero smoke --config configs/smoke.yaml --output-dir /tmp/topoastero-smoke && \
    uv run topoastero validate-stage0 --root . && \
    uv run pytest

CMD ["uv", "run", "topoastero", "validate-stage0", "--root", "."]


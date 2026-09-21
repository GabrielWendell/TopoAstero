# Environments

`uv.lock` at repository root is authoritative. On any supported platform:

```bash
uv sync --locked --group dev
```

`environment.yml` creates a minimal conda bridge with Python and uv; run the command above after
activation. `Dockerfile` provides a clean Linux reproduction environment. Scientific backends added
in later stages must be locked and tested; do not maintain an independent ad hoc environment file.

Stage 3's numerical core is installed by the default locked environment. Reacquiring and reading
raw mission FITS uses the locked optional extra:

```bash
uv sync --locked --group dev --extra astronomy
```

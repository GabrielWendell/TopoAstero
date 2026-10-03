# Stage 11 MAST timeout repair

Copy `src/` and `tests/` over the repository root.

The repair changes the Stage 11 mission downloader from a single 60-second attempt to a bounded retry policy with atomic `.part` cleanup. The CLI gains:

- `--timeout` (default 240 s)
- `--retries` (default 4)
- `--retry-backoff` (default 2 s)

Recommended acquisition sequence:

```powershell
uv run python workflows/run_stage11_legacy.py acquire `
  --cache-dir .\data\caches\topoastero-mission-cache\ `
  --download `
  --role descriptive_benchmark `
  --timeout 300 `
  --retries 5

uv run python workflows/run_stage11_legacy.py acquire `
  --cache-dir .\data\caches\topoastero-mission-cache\ `
  --download `
  --role development `
  --timeout 300 `
  --retries 5

uv run python workflows/run_stage11_legacy.py acquire `
  --cache-dir .\data\caches\topoastero-mission-cache\ `
  --download `
  --role internal_validation `
  --timeout 300 `
  --retries 5

uv run python workflows/run_stage11_legacy.py acquire `
  --cache-dir .\data\caches\topoastero-mission-cache\ `
  --download `
  --role final_holdout `
  --timeout 300 `
  --retries 5
```

Completed files are reused and checksum-verified on subsequent runs. Failed partial transfers are deleted rather than promoted to the cache.

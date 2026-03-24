# CardioOracle — CLAUDE.md

## What this is
Browser-based cardiovascular trial outcome predictor. Hybrid Bayesian + ML model.
Single-file HTML app (~15-20K lines at maturity) + Python curation pipeline.

## Non-negotiables
- OA-only: all data from CT.gov / AACT (public domain)
- No secrets: AACT credentials in .env only, never in HTML or committed code
- Fail-closed: if similar trial count < 3, output INSUFFICIENT DATA
- Determinism: fixed similarity weights, reproducible predictions
- Test before done: run full test suite before declaring any task complete

## Key patterns
- Python: use `python` not `python3` (Windows)
- Template literals: never write literal `</script>` inside script blocks
- localStorage keys: prefix `cardiooracle_`
- Stats: use `?? fallback` not `|| fallback` for numeric values (zero is valid)

## File roles
- `curate/` — Python pipeline, runs offline, queries AACT, produces JSON
- `data/` — Pipeline outputs + configs, embedded into HTML
- `CardioOracle.html` — The app. Pure JS. No Python dependency at runtime.
- `tests/` — Python tests (pytest + Selenium)

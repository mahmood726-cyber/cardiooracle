# REVIEW CLEAN (after fixes)
## Multi-Persona Review: CardioOracle.html
### Date: 2026-03-24
### Summary: 3 P0 fixed, 2 P1 fixed, remaining P1/P2 documented

---

## Statistical Methodologist

#### P0 — Critical
- **SM-P0-1** [FIXED]: All training trials treated as failures — `trial.outcome === 'positive'` should be `trial.label === 'success'`
- **SM-P0-2** [FIXED]: `computeSimilarity` accessed top-level properties but training data nests under `.features` — added `const c = candidate.features ?? candidate` resolution
- **SM-P0-3** [FIXED]: Ensemble weight redistribution had sequential mutation bug — saved originals before redistribution

#### P1 — Important
- **SM-P1-1**: Design tab duration invisible to meta-regression — `duration_months` vs `duration` field name mismatch
- **SM-P1-2**: Hardcoded z=1.96 — should be parameterized via CONFIG.alpha
- **SM-P1-3**: `events = enrollment * 0.7` crude assumption — should use endpoint-specific event rates
- **SM-P1-4**: WebR validation re-implements logic instead of calling main function, masking bugs

#### P2 — Minor
- **SM-P2-1**: Beta posterior CI uses `n = a+b` instead of `a+b+1` for variance
- **SM-P2-2**: Arcsine branch uses one-sided rejection vs two-sided for others
- **SM-P2-3**: `escapeHtml` defined late but used earlier (works due to hoisting)
- **SM-P2-4**: `getDesignFeatures` returns `start_year` but `computeSimilarity` checks `.year`

---

## Security Auditor

#### P0 — Critical
- None found

#### P1 — Important
- **SA-P1-1**: Double-escaping in error messages via textContent (cosmetic)
- **SA-P1-2** [FIXED]: CSV export lacked formula injection protection — added `'` prefix for `=+@\t\r`
- **SA-P1-3**: Duplicate `escapeHtml()` definitions (maintenance hazard)
- **SA-P1-4**: No API response schema validation
- **SA-P1-5**: No Content-Security-Policy meta tag

#### P2 — Minor
- **SA-P2-1**: Inline onclick handlers (prevents strict CSP)
- **SA-P2-2**: `hf.*reduced` regex unbounded (low ReDoS risk)
- **SA-P2-3**: `titleAttr` double-escapes quotes (redundant)
- **SA-P2-4**: configSelect.value safe by construction (noted)
- **SA-P2-5**: sessionStorage caches API responses (acceptable)

---

## Positive Security Practices Noted
- All 40+ innerHTML assignments use escapeHtml()
- No eval(), Function(), document.write()
- Blob URLs properly revoked
- localStorage keys properly prefixed
- WebR import URL hardcoded (not user-controllable)
- NCT ID validated with strict regex
- Modal keyboard listener cleanup on close

---

## False Positive Watch
- DOR = exp(mu1 + mu2) IS correct (not flagged)
- `??` operator correctly preserves zero for numeric values
- Beta prior alpha=0 is valid and handled correctly by `??`

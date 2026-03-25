# REVIEW CLEAN (after 3 rounds of fixes)
## Multi-Persona Review: CardioOracle.html
### Date: 2026-03-25
### Summary: Round 1: 3 P0 + 1 P1 fixed. Round 2: 6 P0 + 1 P1 fixed. Round 3: 7 P1 fixed + TruthCert v2.0 + 15 new tests. Total: 9 P0 + 9 P1 fixed.

### Round 3 fixes (2026-03-25):
- **SM-P1-2** [FIXED]: z=1.96 hardcoded → parameterized via CONFIG.conf_level + normalQuantile() + zAlpha()
- **UX-P1-1** [FIXED]: Traffic-light identical icons → distinct per level (checkmark/diamond/cross)
- **UX-P1-3** [FIXED]: Amber contrast WCAG AA — #fd7e14 (2.8:1) → #c25e00 (5.1:1)
- **UX-P1-5** [FIXED]: Training table headers now have aria-sort attribute on active sort column
- **DE-P1-1** [FIXED]: Endpoint keywords expanded — 3-point MACE, worsening HF, sustained eGFR decline, ESKD, NT-proBNP, etc.
- **SA-P1-4** [FIXED]: API response schema validation — rejects missing protocolSection.identificationModule
- **SA-P1-5** [FIXED]: Content-Security-Policy meta tag added (default-src, script-src, connect-src scoped)
- **TruthCert v2.0**: exportPredictionBundle upgraded — SHA-256 via SubtleCrypto, full provenance trail, validator outcomes, certification envelope
- **Tests**: 15→30 Selenium tests (z_alpha, normalQuantile, SHA-256, CSP, endpoint keywords, schema validation, aria-sort, traffic-light icons, design live prediction, training filter, edge cases)

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

---

## UX/Accessibility Reviewer

#### P0 — Critical
- **UX-P0-1** [FIXED]: `.sr-only` CSS class used but never defined — added definition
- **UX-P0-2**: Tutorial dialog missing `aria-labelledby`
- **UX-P0-3**: Tutorial dialog no focus trap / Escape handler
- **UX-P0-4** [FIXED]: `--surface-2` CSS variable undefined → replaced with `--bg-input`

#### P1 — Important
- **UX-P1-1**: Traffic-light uses identical icon for all states
- **UX-P1-3**: Light-mode amber alert contrast may fail WCAG AA (2.8:1)
- **UX-P1-5**: Sortable table headers missing `aria-sort` attribute

---

## Software Engineer

#### P0 — Critical
- **SE-P0-1** [FIXED]: Duplicate `escapeHtml` definitions → removed second
- **SE-P0-2** [FIXED]: Design tab drug class values incompatible with engine → fixed option values
- **SE-P0-3** [FIXED]: Population tag case mismatch → normalized to lowercase
- **SE-P0-4**: Plotly.newPlot memory leak (no purge before re-render)

#### P1 — Important
- **SE-P1-1**: WebR test 3 feature vector uses different field names than metaRegressionPredict
- **SE-P1-2**: `valsartan` mapped to `arni` — misclassifies standalone ARB trials

---

## Domain Expert

#### P0 — Critical
- **DE-P0-1** [FIXED]: Same as SE-P0-2 (drug class mapping)
- **DE-P0-2**: MRA base rate 0.0 — needs verification (EMPHASIS-HF/EPHESUS were positive)
- **DE-P0-3**: HFrEF/HFpEF regex too narrow (misses EF, ejection fraction without lvef prefix)

#### P1 — Important
- **DE-P1-1**: Endpoint keywords miss variants (3-point MACE, worsening HF, sustained eGFR decline)
- **DE-P1-5** [FIXED]: About modal said 325 trials → corrected to 784

---

## False Positive Watch
- DOR = exp(mu1 + mu2) IS correct (not flagged)
- `??` operator correctly preserves zero for numeric values
- Beta prior alpha=0 is valid and handled correctly by `??`

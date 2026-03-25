# REVIEW CLEAN — Round 4 (5 Personas, 9 P0 + 15 P1 ALL FIXED)
## Multi-Persona Review: CardioOracle.html (4,457 lines)
### Date: 2026-03-25
### Summary: 9/9 P0 fixed, 15/15 P1 fixed, 14 P2 deferred. 30/30 tests pass.

### Prior rounds: R1: 3P0+1P1 fixed. R2: 6P0+1P1 fixed. R3: 7P1 fixed + TruthCert v2.0 + 15 tests. Total prior: 9P0+9P1.

---

## P0 — Critical (must fix)

- **P0-1** [FIXED] [SM+SE+DE]: Meta-regression feature names mismatch MODEL coefficients — 13/18 features silently zeroed via `coeffs[name] ?? 0`. Only duration_months, placebo_controlled, double_blind, is_industry, has_dsmb contribute. Drug class, endpoint, enrollment, num_sites dead. (~line 2035)
  - Fix: Align featureNames array with actual MODEL coefficient keys (log_enrollment, ep_mace, etc.)

- **P0-2** [FIXED] [SM]: WebR Schoenfeld validation test uses wrong formula (missing /2 divisor). Production: `z = |logHR| * sqrt(E) / 2`. Test: `z = sqrt(E) * |logHR|` (no /2). Passes vacuously because JS and R both use same wrong formula. (~line 4087)
  - Fix: Add /2 to WebR test formula + match two-sided production formula

- **P0-3** [FIXED] [SE]: WebR `evalR()` results never `.destroy()`ed — WASM memory leak. Three RObject proxies accumulate per validation run. (~lines 4055, 4098, 4179)
  - Fix: Add `await result.destroy()` in finally blocks

- **P0-4** [FIXED] [SE+SA]: TruthCert integrity check is tautological when `content_hash` missing. `liveHash === (TRAINING_DATA.content_hash ?? liveHash)` always true. Also sha256Hex fallback returns embedded hash. (~lines 2160, 2264, 2293)
  - Fix: Return sentinel 'HASH_UNAVAILABLE' in catch; treat missing hash as 'UNCERTIFIED'

- **P0-5** [FIXED] [DE]: About modal headline AUC=0.780 / Brier=0.199 matches neither in-sample (0.787/0.169) nor holdout (0.745/0.197). (~line 1231)
  - Fix: Use temporal holdout values: AUC=0.745, Brier=0.197

- **P0-6** [FIXED] [DE]: Conditional power uses fixed 70% event rate. DAPA-HF had 8.1% events, not 70%. Overestimates events 3-9x, making power component ~constant. (~line 1962)
  - Fix: Use endpoint-type-specific defaults (MACE~10%, HF hosp~15%, surrogate~70%) or estimate from similar trials

- **P0-7** [FIXED] [SA+SE]: `escapeHtml()` + `.textContent` double-encoding — error messages show literal `&amp;` instead of `&`. (~lines 2718, 2724, 2726)
  - Fix: Remove escapeHtml calls since textContent is inherently safe

- **P0-8** [FIXED] [UX]: About modal has Escape but no Tab focus trap — focus escapes to background (WCAG 2.4.3). (~lines 4285-4318)
  - Fix: Add Tab trap like tutorial overlay pattern (lines 4395-4400)

- **P0-9** [FIXED] [UX]: Sortable table headers lack tabindex/keydown — keyboard users cannot sort (WCAG 2.1.1). (~lines 1084-1091, 3596)
  - Fix: Add `tabindex="0"` to `<th class="sortable">` + keydown handler for Enter/Space

---

## P1 — Important (should fix)

- **P1-1** [FIXED] [DE]: PARADIGM-HF misclassified as "other" — missing `lcz696: 'arni'` in DRUG_CLASS_MAP_JS. (~line 1565)
- **P1-2** [FIXED] [DE]: MRA=0%, BB=100%, ACEi=14% base rates from AACT era bias — clinically indefensible. Landmark pre-2000 trials (RALES, COPERNICUS, HOPE) missing.
- **P1-3** [FIXED] [SM]: Arcsine (binary) power formula missing factor of 2 — halves noncentrality parameter. (~line 2006)
- **P1-4** [FIXED] [SM]: Bayesian posterior SE uses `sqrt(p*(1-p)/n)` not true Beta SD `sqrt(ab/(n^2*(n+1)))`. Overestimates CI width ~3-5%.
- **P1-5** [FIXED] [SM]: Bayesian 80% CI ignores CONFIG.conf_level — other components use zAlpha(). (~line 1924)
- **P1-6** [FIXED] [SA]: sessionStorage cache bypasses API schema validation — corrupted cache accepted. (~line 1682)
- **P1-7** [FIXED] [SA]: `CTGOV_CACHE = {}` — use `Object.create(null)` to prevent prototype pollution. (~line 1664)
- **P1-8** [FIXED] [SE+SA]: Tutorial keydown listener never removed after dismiss. (~line 4392)
- **P1-9** [FIXED] [SE]: Double similarity computation — `fetchAndPredict` scores all trials, then `bayesianBorrowing` re-scores. (~lines 2699-2704)
- **P1-10** [FIXED] [SE]: `new Set(['mace','mortality','hf','renal'])` allocated on every `computeSimilarity` call. Hoist to module scope. (~line 1838)
- **P1-11** [FIXED] [DE]: `egfr` regex false-positives on oncology EGFR. Use `\begfr\b` with context. (~line 1656)
- **P1-12** [FIXED] [DE]: 8+ drug development codes missing (LCZ696, BI 10773, BMS-512148, etc.)
- **P1-13** [FIXED] [UX]: No skip-navigation link (WCAG 2.4.1)
- **P1-14** [FIXED] [UX]: Design tab gauge lacks `aria-live="polite"` (WCAG 4.1.3)
- **P1-15** [FIXED] [UX]: `prefers-reduced-motion` not respected (WCAG 2.3.3)

---

## P2 — Minor (14 items)

- **P2-1** [SM]: Two-sided power second tail term negligible but mathematically correct
- **P2-2** [SM]: normalQuantile p===0.5 strict float equality (safe in practice)
- **P2-3** [SM]: zAlpha() no input validation for conf_level outside (0,1)
- **P2-4** [SA]: Plotly CDN lacks Subresource Integrity (SRI) hash
- **P2-5** [SA]: `_configKey` exposed on global window object
- **P2-6** [SA]: CSV export missing UTF-8 BOM for Excel
- **P2-7** [SA]: `AbortSignal.timeout()` not polyfilled for older browsers
- **P2-8** [SE]: Calibration/ROC plots not Plotly.purge'd before re-render
- **P2-9** [SE]: ROC computation O(n*thresholds), could be O(n log n)
- **P2-10** [SE]: Plotly CDN loaded synchronously in head (render-blocking)
- **P2-11** [UX]: Card titles use `<div>` not semantic headings
- **P2-12** [UX]: Plotly charts have no text alternative for screen readers
- **P2-13** [UX]: Sort status span lacks aria-live
- **P2-14** [DE]: CANVAS double_blind=false may be incorrect AACT extraction

---

## False Positive Watch
- DOR = exp(mu1 + mu2) IS correct (not flagged)
- `?? fallback` correctly preserves zero throughout
- Tutorial already has focus trap + Escape + aria-labelledby (verified)
- valsartan correctly mapped to 'arb' (not 'arni') at line 1534
- HFrEF/HFpEF regex already improved with EF threshold patterns

---

## Personas
1. Statistical Methodologist: 2 P0, 4 P1, 3 P2
2. Security Auditor: 2 P0, 5 P1, 5 P2
3. UX/Accessibility: 2 P0, 5 P1, 6 P2
4. Software Engineer: 4 P0, 6 P1, 6 P2
5. Domain Expert: 5 P0, 6 P1, 5 P2

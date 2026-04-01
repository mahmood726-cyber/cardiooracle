# Prospective Validation System — Design Spec

**Date:** 2026-04-01
**Target:** Lancet Digital Health (supplementary evidence for manuscript)
**Approach:** Full validation system integrated as 6th tab in CardioOracle.html
**Architecture:** Single-file HTML, localStorage + JSON export/import, TruthCert hash chain

---

## 1. Tab Structure & UI Layout

New **6th tab: "Prospective Validation"** in the existing tab bar, with three vertically stacked panels.

### Panel 1 — Cohort Management (top)
- **Auto-Discover button**: Queries CT.gov API v2 for recruiting Phase 2/3+ CV trials across 3 therapeutic areas (cardiorenal, CAD, AF). Returns candidates in a review queue.
- **Manual Add**: NCT ID text input + "Add" button — fetches trial details, shows preview.
- **Review Queue**: Table of candidate trials (NCT ID, title, drug class, endpoint, phase, enrollment). Each row has Approve / Reject buttons. On Approve → prediction runs, gets hash-locked with timestamp.
- **Locked Cohort Table**: All approved trials with prediction probabilities, lock timestamp, and status badge (Recruiting / Active / Completed / Has Results / Terminated).

### Panel 2 — Monitoring (middle)
- **"Check All Statuses" button**: Batch queries CT.gov for all tracked trials, updates status badges.
- **Resolution Queue**: Trials detected as Completed/Has Results/Terminated surface here with pre-filled outcome data from CT.gov. User confirms outcome before it counts.
- **Timeline**: Horizontal Plotly chart showing each trial's expected completion date vs today, color-coded by status.

### Panel 3 — Analysis Dashboard (bottom)
- Activates with ≥5 resolved trials.
- 7 metrics: scorecard table, AUC plot, calibration plot, Brier decomposition, decision curve, component comparison, temporal accuracy trend.
- Each chart is Plotly interactive with PNG export.

### Seed Behavior
On first load, if no localStorage cohort exists, auto-import the existing 25 predictions from embedded `prospective_predictions_20260325.json` data, preserving original timestamps and hashes.

---

## 2. TruthCert Hash Chain (Tamper-Evident Prediction Locking)

Every prediction entry gets a cryptographic lock using Web Crypto API (`crypto.subtle.digest('SHA-256', ...)`).

### Hash Formula
```
Entry N hash = SHA-256(
  nct_id + timestamp + p_ensemble + p_bayes + p_power + p_reg
  + drug_class + endpoint_type + enrollment + duration
  + model_coefficients_hash + training_data_hash
  + entry_(N-1)_hash    <- chain link
)
```

### Locked Entry Schema
```json
{
  "seq": 1,
  "nct_id": "NCT05887674",
  "locked_at": "2026-04-01T14:30:00.000Z",
  "prediction": {
    "p_ensemble": 0.648, "p_bayes": 0.712,
    "p_power": 0.581, "p_reg": 0.634,
    "confidence": "HIGH"
  },
  "trial_snapshot": {
    "title": "...", "drug_class": "sglt2i",
    "endpoint_type": "mace", "enrollment": 8000,
    "duration_months": 48, "phase": "PHASE3"
  },
  "model_version": "cardiooracle_v1.0",
  "training_hash": "sha256:a4f2c8...",
  "prev_hash": "sha256:9b1e3d...",
  "entry_hash": "sha256:7c4a0f..."
}
```

### Properties
- **Append-only**: Once hash-locked, entries cannot be modified without breaking the chain.
- **Verifiable**: Anyone with the exported JSON can recompute every hash and verify integrity.
- **Chain-linked**: Inserting, deleting, or reordering entries breaks all subsequent hashes.
- **Genesis block**: The 25 existing predictions (2026-03-25) form entries #1–25 with original timestamps. `prev_hash` of entry #1 is `null`.

### Resolution Records
Separate objects chained similarly:
```json
{
  "nct_id": "NCT05887674",
  "resolved_at": "2027-09-15T...",
  "outcome": "SUCCESS",
  "evidence": {
    "p_value": 0.003, "hr": 0.82,
    "ci_lower": 0.72, "ci_upper": 0.94,
    "source": "ct.gov_results"
  },
  "prediction_entry_hash": "sha256:7c4a0f...",
  "resolution_hash": "sha256:e5d1b2..."
}
```

### Verify Chain
A "Verify Chain" button recomputes all hashes and reports integrity status (all green / broken at entry N).

---

## 3. Auto-Discovery Engine

### Query Strategy — one API call per therapeutic area

| Area | CT.gov API v2 Query Filters |
|------|----------------------------|
| Cardiorenal | `condition.search`: heart failure OR chronic kidney disease OR cardiorenal; `intervention.search`: drug; `filter.overallStatus`: RECRUITING; `filter.phase`: PHASE2, PHASE3 |
| CAD | `condition.search`: coronary artery disease OR acute coronary syndrome OR myocardial infarction; same status/phase filters |
| AF | `condition.search`: atrial fibrillation OR atrial flutter; same status/phase filters |

### Deduplication
Skip any NCT ID already in the locked cohort or review queue.

### Candidate Scoring
- **Ready**: Has enough features for all 3 prediction components (drug class identifiable, endpoint classifiable, enrollment reported).
- **Partial**: Missing 1-2 features (will use available components only, lower confidence).
- **Skip**: Unclassifiable drug or endpoint, or Phase 1 that slipped through filters.

### Review Queue Display (sortable table)
| NCT ID | Title | Drug Class | Endpoint | Enrollment | Phase | Predictability | Action |
|--------|-------|------------|----------|------------|-------|----------------|--------|

### Rate Limiting
CT.gov API v2 requests capped with 1-second delays between areas. "Last checked" timestamp prevents redundant polling within 1 hour.

### Manual Add Flow
User enters NCT ID → app calls `https://clinicaltrials.gov/api/v2/studies/NCT...` → shows preview row → user approves or rejects. Invalid NCT IDs show inline error.

---

## 4. Monitoring & Outcome Resolution

### Status Polling
- "Check All Statuses" iterates through locked cohort, calling CT.gov API v2 for each trial's `overallStatus`.
- Rate-limited: 500ms delay between requests.
- Status badges with color coding:
  - Green: Recruiting / Active, not recruiting
  - Yellow: Completed (awaiting results)
  - Blue: Has Results (ready for resolution)
  - Red: Terminated / Withdrawn / Suspended
- **Change detection**: Status differs from last check → highlighted with "NEW" badge + summary notification.

### Auto-Fetch Results for Resolution
When a trial shows `hasResults: true`, fetch `resultsSection` from CT.gov API v2 and pre-fill:
1. Primary outcome p-value from `outcomeMeasuresModule`
2. Effect estimate (HR, OR, RR, mean difference)
3. Confidence interval
4. Outcome suggestion:
   - p < 0.05 on primary → "SUCCESS"
   - p >= 0.05 on primary → "FAILURE"
   - Terminated + safety reason → "SAFETY_FAILURE"
   - Insufficient data → "UNKNOWN" (require manual entry)

### Resolution Form
- Pre-filled fields (editable): outcome, p-value, effect estimate, CI
- Required: Outcome radio (Success / Failure / Safety Failure)
- Optional: Free-text evidence note, publication DOI
- **Confirm button**: Locks resolution into hash chain. Cannot be undone.

### Timeline Chart (Plotly)
- X-axis: calendar time (2026-2032)
- Y-axis: one row per trial (grouped by therapeutic area)
- Horizontal bars: prediction date to expected completion
- Markers: prediction locked (diamond), status changes (circles), resolution (star)
- Today line (vertical dashed red)

---

## 5. Analysis Dashboard

Activates when ≥5 trials are resolved. Before threshold: "N/M trials resolved — need 5+ for analysis."

### 5.1 Running Scorecard Table
| # | NCT ID | Area | Drug Class | Endpoint | P(success) | Actual | Correct? | Confidence |
|---|--------|------|------------|----------|-----------|--------|----------|------------|

- Color-coded: green = correct, red = incorrect.
- Classification threshold: P >= 0.50 → predicted success.
- Sortable by any column.

### 5.2 Discrimination — AUC with 95% CI
- Bootstrap AUC (n=2000 resamples, seeded xoshiro128** PRNG).
- Plotly ROC curve with diagonal reference.
- CI displayed as subtitle: "AUC = 0.78 (95% CI: 0.64-0.91)".
- Requires ≥5 resolved trials with both outcomes present.

### 5.3 Calibration Plot
- X-axis: predicted probability (quintile bins, or flexible if N < 25).
- Y-axis: observed success rate per bin.
- Perfect calibration diagonal (dashed).
- Calibration slope + intercept (logistic regression of outcome on logit(predicted)).
- Wilson confidence bands on observed proportions.

### 5.4 Brier Score (decomposed)
- Overall Brier score.
- Decomposition: Reliability + Resolution - Uncertainty.
- Small bar chart with three stacked components.

### 5.5 Decision Curve Analysis
- X-axis: threshold probability (0.1 to 0.9).
- Y-axis: net benefit.
- Three lines: CardioOracle, "Predict All Success", "Predict None".
- Shows threshold range where model adds value.

### 5.6 Component Comparison
- Three mini-AUCs: Bayesian alone, conditional power alone, meta-regression alone, vs ensemble.
- Bar chart with bootstrap CIs.

### 5.7 Temporal Tracking
- X-axis: resolution date (cumulative).
- Y-axis: running accuracy (%), running AUC.
- Two-line Plotly chart showing performance evolution.

### Chart Standards
- All use existing Plotly.js instance.
- Match CardioOracle dark/light theme.
- Each chart has PNG export button.

---

## 6. Data Persistence & Export/Import

### localStorage Schema — prefix `cardiooracle_pv_`

| Key | Contents |
|-----|----------|
| `cardiooracle_pv_cohort` | Array of locked prediction entries (hash chain) |
| `cardiooracle_pv_resolutions` | Array of resolution records (hash chain) |
| `cardiooracle_pv_queue` | Review queue candidates (not yet locked) |
| `cardiooracle_pv_last_discovery` | Timestamp of last auto-discovery run |
| `cardiooracle_pv_last_status_check` | Timestamp of last status poll |

### Export — "Export Validation Bundle"
```json
{
  "format": "cardiooracle_prospective_v1",
  "exported_at": "2026-04-01T...",
  "model_version": "cardiooracle_v1.0",
  "training_hash": "sha256:a4f2c8...",
  "predictions": [],
  "resolutions": [],
  "summary": {
    "total_tracked": 30,
    "resolved": 5,
    "accuracy": 0.80,
    "auc": 0.78
  },
  "bundle_hash": "sha256:..."
}
```
- `bundle_hash` = SHA-256 of serialized predictions + resolutions arrays.
- Downloaded as `cardiooracle_validation_YYYY-MM-DD.json`.
- Blob URL revoked after download.

### Import — "Import Validation Bundle"
1. User selects JSON file.
2. Verify `format` field matches `cardiooracle_prospective_v1`.
3. Recompute every hash in both chains — mismatch → error with broken entry, refuse import.
4. If valid, merge into localStorage (dedup by NCT ID; newer resolution wins).
5. Confirmation: "Imported N predictions, M resolutions. Chain integrity verified."

### Seed on First Load
- If `cardiooracle_pv_cohort` is empty, auto-import 25 existing predictions with original March 25 timestamps.
- Migration flag `cardiooracle_pv_seeded` prevents re-seeding.

### Storage Budget
~200KB estimated for 100 tracked trials — well within ~5MB localStorage limit.

---

## Implementation Constraints

- **Single-file**: All code goes into `CardioOracle.html` (currently 4,462 lines).
- **No `</script>` in JS**: Use `${'<'}/script>` pattern.
- **Seeded PRNG**: xoshiro128** for bootstrap resampling (no Math.random()).
- **`?? fallback`**: Never use `|| fallback` for numeric values.
- **Div balance**: Verify `<div>` vs `</div>` counts after structural edits.
- **ID uniqueness**: All new element IDs prefixed `pv-` to avoid collisions.
- **Event listener cleanup**: Modal/dialog close paths must remove keydown/keyup listeners.
- **Accessibility**: Keyboard-navigable tables, ARIA labels, focus management, skip-nav target.
- **Dark mode**: All new elements must respect existing dark mode CSS variables.
- **localStorage prefix**: `cardiooracle_pv_` for all new keys.
- **Rate limiting**: 500ms–1000ms delays between CT.gov API calls.
- **Error handling**: Network failures show inline error, never crash the app.
- **Blob cleanup**: `URL.revokeObjectURL()` after export downloads.

# CardioOracle: Cardiovascular Trial Outcome Predictor — Design Spec

**Date:** 2026-03-24
**Author:** Mahmood (design), Claude (spec documentation)
**Target journals:** Lancet Digital Health / JAMIA (tool paper), Scientific Data (dataset paper)
**Status:** Design approved, pending implementation plan

---

## 1. Core Concept

**CardioOracle** is the first open-access, browser-based tool that predicts whether a cardiovascular clinical trial will meet its primary endpoint — and lets users design hypothetical trials with live probability feedback.

**Tagline:** *"The first open-access tool that predicts whether a cardiovascular trial will succeed — and lets you design one that will."*

**Format:** Single-file HTML app (~15-20K lines at maturity), pure JavaScript computation engine, WebR for reviewer validation only.

**Config-driven therapeutic areas:** Launch with `cardiorenal` (HF + CKD + MRA/SGLT2i/finerenone). Extensible to `cad`, `arrhythmia`, `lipids` via `?config=` URL parameter (same pattern as CRES).

---

## 2. Architecture

```
+---------------------------------------------+
|  UI Layer (tabs, charts, sliders, Plotly)    |
+---------------------------------------------+
|  Prediction Engine (JS)                      |
|  +- BayesianBorrower: historical similarity  |
|  +- ConditionalPower: sample size adequacy   |
|  +- MetaRegressor: feature->P(success)       |
|  +- FeatureDecomposer: SHAP-like attribution |
+---------------------------------------------+
|  Data Layer                                  |
|  +- TRAINING_DATA: embedded curated trials   |
|  +- CT.gov API: live trial fetch             |
|  +- CONFIG: therapeutic area definitions     |
+---------------------------------------------+
```

### Data Pipeline

```
AACT PostgreSQL (aact-db.ctti-clinicaltrials.org)
  +-- Python curation script (one-time / periodic)
      +-- Query: outcome_analyses (p_values, CIs)
      +-- Query: designs (randomization, masking, enrollment)
      +-- Query: conditions, interventions, eligibility
      +-- Label: success/failure from primary endpoint
      +-- Export: training_data.json + model_coefficients.json
           +-- Embed into CardioOracle.html

CT.gov API v2 (live, at runtime)
  +-- Fetch recruiting trials for prediction targets
```

---

## 3. Prediction Model (Hybrid Bayesian + ML)

### Component 1: Bayesian Historical Borrowing (weight ~40%)

*"What happened to trials like this one?"*

For a target trial, compute a **weighted similarity score** against each training trial across 5 dimensions:

```
Similarity(target, candidate) = sum_d(w_d * match_d)
```

| Dimension | Weight (w_d) | Match function (match_d) |
|-----------|-------------|--------------------------|
| drug_class | 0.30 | 1.0 if exact match, 0.5 if same broader mechanism, 0.0 otherwise |
| endpoint_type | 0.25 | 1.0 if exact match, 0.3 if both are hard endpoints (MACE/death/HF), 0.0 otherwise |
| comparator_type | 0.15 | 1.0 if exact match (placebo vs placebo, active vs active), 0.0 otherwise |
| population | 0.15 | Jaccard similarity of parsed eligibility tags (HFrEF, HFpEF, diabetic, CKD, elderly) |
| era | 0.15 | exp(-|year_target - year_candidate| * ln(2) / 10) — exponential decay with 10-year half-life |

**K selection:** K = all trials with similarity > 0.3 (adaptive), clamped to [5, 30]. If fewer than 5 trials exceed threshold 0.3 but at least 3 exceed threshold 0.1, widen to those and flag as LOW_CONFIDENCE. If fewer than 3 trials exceed threshold 0.1, output INSUFFICIENT DATA (no prediction from this component).

**Posterior computation:** Similarity scores are used as pseudo-count weights, scaled by K so that more similar trials contribute proportionally more evidence:
```
effective_successes = sum(similarity_i * success_i)        // NOT normalized to sum=1
effective_failures  = sum(similarity_i * (1 - success_i))  // raw similarity weights
Posterior: Beta(a0 + effective_successes, b0 + effective_failures)
P_bayesian = mean of posterior = (a0 + eff_succ) / (a0 + b0 + eff_succ + eff_fail)
```

With K=20 similar trials at average similarity 0.5, effective data ≈ 10 pseudo-observations — comparable to the prior, giving roughly equal influence. With K=5 at low similarity (~0.3), effective data ≈ 1.5, and the prior appropriately dominates. This scaling ensures the posterior is not perpetually dominated by the prior regardless of evidence.

Prior `Beta(a0, b0)` set from therapeutic area base rate (e.g., cardiorenal Phase 3 success rate ~45% -> a0=4.5, b0=5.5, equivalent to ~10 pseudo-trials of prior information).

WebR validates posterior against R Beta-Binomial computation.

### Component 2: Conditional Power Analysis (weight ~35%)

*"Is this trial sized to detect a plausible effect?"*

From similar completed trials, estimate the expected effect size distribution (mean + SD of log-HR or log-OR). Given the target trial's sample size, duration, and endpoint type:
- Conditional power: P(rejecting H0 | true effect = historical median)
- Power curve: power vs. range of plausible effect sizes

**Power formula by endpoint type:**

| Endpoint type | Estimand | Power formula |
|--------------|----------|---------------|
| Time-to-event (MACE, CV death, HF hosp) | HR | Schoenfeld: events = (z_alpha + z_beta)^2 / (log(HR))^2; power = Phi(sqrt(events) * |log(HR)| - z_alpha) |
| Binary (response rate) | OR/RR | Arcsine: power from difference in arcsine-transformed proportions |
| Continuous (eGFR slope, BP change) | SMD | Two-sample t-test: power = Phi(|delta|*sqrt(N/4) - z_alpha) where delta = expected SMD |
| Composite | HR | Same as time-to-event; composite event rate estimated from component historical rates |

For time-to-event endpoints, expected number of events is estimated from enrollment, duration, and historical event rates in similar trials. If event rate data is unavailable, a conservative 70% information fraction is assumed.

Uses normalCDF, non-central chi-squared -- reuses existing stats-utils.js functions.

### Component 3: Design Feature Meta-Regression (weight ~25%)

*"Which design choices predict success or failure?"*

Logistic meta-regression:
```
logit(P_success) = b0 + b1*log(N) + b2*duration + b3*placebo_controlled
                 + b4*industry_sponsor + b5*multi_region + ...
```

~15 features from AACT structured fields. Coefficients pre-fitted during Python curation, embedded in JS. Feature decomposition chart shows each feature's contribution (analytically computed from linear model).

### Final Ensemble

```
P(success) = w1*P_bayesian + w2*P_power + w3*P_regression
```

- **Weight selection:** Fixed by design judgment, NOT optimized on data (to avoid overfitting on ~500 training trials). Rationale: Bayesian borrowing gets highest weight because it uses the most directly relevant information (similar trials); conditional power is second because power is the single strongest predictor of trial success in the literature; meta-regression gets lowest weight because it captures residual design factors after the first two components. These weights can be adjusted per-config if domain experts disagree.
- Display: traffic light (green >60%, amber 30-60%, red <30%) + exact probability + 80% credible interval
- **Acceptance criteria:** AUC >= 0.65, Brier score < 0.25, calibration slope 0.8-1.2. If any fails, Calibration tab displays a warning banner: "Model calibration below threshold — predictions should be interpreted with caution."
- Calibration: temporal split on **primary_completion_date** (train: primary_completion_date < 2020-01-01; test: >= 2020-01-01). Trials spanning the boundary are assigned by completion date, not start date, to prevent information leakage from future outcomes.

---

## 4. Training Data Curation

### Source
AACT PostgreSQL remote database (aact-db.ctti-clinicaltrials.org). User has existing connection scripts in `C:\Users\user\Downloads\Metaprojects\`.

### Inclusion Criteria
- Phase 3 (or Phase 2/3), interventional, randomized
- Cardiovascular condition (MeSH-mapped)
- Has posted results (has_results = true)
- Completed or terminated
- Enrollment >= 50

### Success/Failure Labeling Strategy

**Tier 1 — High confidence (automated):**
- Primary outcome p_value < 0.05 AND effect favors intervention -> SUCCESS
- Primary outcome p_value >= 0.05 -> FAILURE
- Terminated for futility/lack of efficacy -> FAILURE
- Terminated for safety/adverse events -> FAILURE (tagged separately)

**Tier 2 — Heuristic (automated with flag):**
- Multiple primary endpoints: success if >=1 hits significance (PARTIAL -> treated as success)
- p_value NULL but CI available: check if CI for HR/OR excludes 1.0
- Composite endpoints: labeled by composite result

**Tier 3 — Manual curation (~50-100 landmark trials):**
- Ambiguous AACT results
- Known landmark trials (DAPA-HF, EMPEROR-Reduced, PARADIGM-HF, FIDELIO, FIGARO, etc.)
- Gold standard anchor for training set

### Feature Extraction (~15 features)

| Feature | Source | Type |
|---------|--------|------|
| log(enrollment) | studies | continuous |
| duration_months | studies (start to primary_completion) | continuous |
| placebo_controlled | designs | binary |
| double_blind | designs (masking) | binary |
| industry_sponsor | studies (sponsor_type) | binary |
| num_sites | facilities (count) | continuous |
| multi_regional | facilities (distinct countries) | binary |
| endpoint_type | outcomes (mapped: MACE/HF/death/renal/surrogate) | categorical |
| drug_class | interventions (mapped via DRUG_CLASS_MAP) | categorical |
| comparator_type | interventions + designs | categorical |
| num_arms | designs | integer |
| has_dsmb | studies (oversight) | binary |
| historical_class_rate | derived (base rate for drug class) | continuous |
| era_bucket | studies (start_date bucketed: pre-2010, 2010-2017, 2018+) | categorical |

Note: The meta-regression uses `era_bucket` (categorical). The Bayesian similarity function uses raw `start_year` (continuous) with exponential decay. These are distinct representations of the same underlying concept — era_bucket is a coarser discretization for the linear model, while continuous year difference gives smoother similarity gradients.

Note: `prior_phase2_success` was removed — matching Phase 3 to Phase 2 trials by sponsor+drug is an entity resolution problem with high missingness and unreliable linkage. The `historical_class_rate` feature captures similar information more robustly.

### Drug Class Taxonomy (DRUG_CLASS_MAP)

Defined in `configs/cardiorenal.json` and embedded in the curation pipeline + HTML:

| Class ID | Label | Example drugs |
|----------|-------|---------------|
| sglt2i | SGLT2 inhibitor | empagliflozin, dapagliflozin, canagliflozin, ertugliflozin |
| mra | MRA (steroidal) | spironolactone, eplerenone |
| ns_mra | MRA (non-steroidal) | finerenone, esaxerenone |
| arni | ARNi | sacubitril/valsartan |
| arb | ARB | valsartan, losartan, candesartan, irbesartan |
| acei | ACEi | enalapril, ramipril, lisinopril |
| bb | Beta-blocker | carvedilol, bisoprolol, metoprolol |
| glp1ra | GLP-1 RA | semaglutide, liraglutide, dulaglutide |
| pcsk9i | PCSK9 inhibitor | evolocumab, alirocumab |
| statin | Statin | atorvastatin, rosuvastatin |
| anticoag | Anticoagulant | apixaban, rivaroxaban, edoxaban |
| antiplat | Antiplatelet | ticagrelor, prasugrel, clopidogrel |
| other | Other/novel | catch-all for unmatched interventions |

**Matching algorithm:** Normalize intervention name to lowercase, strip dosage/formulation text, match against drug list per class. If no match, assign `other`. At runtime (Predict tab), the same normalization applies to CT.gov API responses. The `other` class uses the broadest cardiovascular prior.

### Expected Training Set
- ~1,069 completed Phase 3 CV trials on CT.gov
- After filtering for posted results + successful labeling: ~600-800 usable
- **Fallback if usable trials < 300:** reduce feature count to ~8 core features (drop num_arms, has_dsmb, num_sites, multi_regional) and simplify regression component to avoid overfitting
- Temporal split: ~500 train (primary_completion_date < 2020-01-01) / ~150 test (>= 2020-01-01)

### Output Files
1. `training_data.json` — array of labeled trials with features
2. `model_coefficients.json` — pre-fitted logistic regression weights + priors + calibration metrics

---

## 5. UI Design (5 Tabs)

### Tab 1: "Predict" (Lookup Mode)
- Search bar: NCT ID or keyword search via CT.gov API
- Result card: traffic-light P(success), 80% CI, one-line verdict
- Three collapsible panels:
  - Historical Twins: table of K similar completed trials with outcomes and similarity scores
  - Power Assessment: power curve with historical median effect marked
  - Design Risk Factors: horizontal bar chart of feature contributions (green=favorable, red=unfavorable)

### Tab 2: "Design" (Trial Designer Mode)
- Left: interactive parameter panel (drug class, endpoint, comparator, sample size slider, duration slider, blinding, sponsor type, sites, multi-regional)
- Right: live prediction panel updating in real-time as sliders move
  - P(success) gauge
  - Power curve (dynamic)
  - Feature decomposition (dynamic)
- What-if comparison: snapshot current design, adjust, see side-by-side delta

### Tab 3: "Training Data"
- Sortable/filterable table of all embedded training trials
- Columns: NCT ID, name, success/fail, confidence tier, features
- Export as CSV
- Full transparency: every data point inspectable

### Tab 4: "Calibration"
- Temporal validation results on held-out test set
- Calibration plot (predicted vs. observed, binned)
- ROC curve with AUC
- Brier score
- Individual trial predictions table

### Tab 5: "WebR Validation"
- Standard pattern: button spins up WebR, runs Bayesian model in R
- Validates: Beta-Binomial posterior, conditional power, logistic regression coefficients
- JS vs. R side-by-side comparison with tolerance flags

### Accessibility
- Keyboard navigation: all tabs, sliders, collapsible panels, and buttons reachable via Tab/Enter/Space
- ARIA roles: `role="tablist"` / `role="tab"` / `role="tabpanel"` for tab navigation; `role="slider"` with `aria-valuemin`/`aria-valuemax`/`aria-valuenow` for Design mode sliders
- Traffic light: not color-only — includes text label ("HIGH" / "MODERATE" / "LOW") and `aria-live="polite"` for screen reader updates
- Dark mode: CSS custom properties with `data-theme` toggle, all combinations WCAG AA (4.5:1 contrast)
- Focus indicators: visible outline on all interactive elements

### CT.gov API Integration (Runtime)

**Predict tab — trial lookup:**
```
GET https://clinicaltrials.gov/api/v2/studies/{nctId}
Fields: protocolSection.identificationModule,
        protocolSection.designModule,
        protocolSection.eligibilityModule,
        protocolSection.conditionsModule,
        protocolSection.armsInterventionsModule,
        protocolSection.outcomesModule,
        protocolSection.sponsorCollaboratorsModule,
        protocolSection.contactsLocationsModule
```

**Feature mapping from API response:**
| Feature | API field path |
|---------|---------------|
| enrollment | designModule.enrollmentInfo.count |
| duration | (parse primaryCompletionDate - statusModule.startDateStruct.date) |
| placebo_controlled | armsInterventionsModule.armGroups[].type == "PLACEBO_COMPARATOR" |
| double_blind | designModule.maskingInfo.masking contains "DOUBLE" |
| industry_sponsor | sponsorCollaboratorsModule.leadSponsor.class == "INDUSTRY" |
| num_sites | contactsLocationsModule.locations.length |
| endpoint_type | outcomesModule.primaryOutcomes[0].measure (ENDPOINT_TYPE_MAP lookup) |
| drug_class | armsInterventionsModule.interventions[].name (DRUG_CLASS_MAP lookup) |

**ENDPOINT_TYPE_MAP** (keyword matching on primary outcome measure text):

| Endpoint type | Keywords (case-insensitive, any match) |
|--------------|----------------------------------------|
| mace | "MACE", "major adverse cardiovascular", "composite cardiovascular" |
| hf_hosp | "heart failure hospitalization", "HF hospitalization", "worsening heart failure" |
| cv_death | "cardiovascular death", "cardiac death", "CV death", "cardiovascular mortality" |
| acm | "all-cause mortality", "all cause mortality", "overall survival", "death from any cause" |
| renal | "eGFR", "kidney", "renal", "dialysis", "ESKD", "doubling of creatinine" |
| surrogate | "blood pressure", "LDL", "HbA1c", "NT-proBNP", "ejection fraction", "6-minute walk" |
| other | fallback if no keywords match |

Priority: if multiple categories match (e.g., "composite of CV death or HF hospitalization"), use the FIRST match in the priority order: mace > hf_hosp > cv_death > acm > renal > surrogate > other.

**Rate limits:** Cache responses in `sessionStorage` keyed by NCT ID. Fetch only on explicit user action. Show loading spinner during fetch. Retry once on timeout after 5 seconds.

### localStorage & State Management

**Key prefix:** `cardiooracle_`

| Key | Content | Version |
|-----|---------|---------|
| `cardiooracle_designer_state` | Last-used designer parameters (drug class, endpoint, sliders) | v1 |
| `cardiooracle_snapshots` | What-if comparison snapshots (max 5, FIFO) | v1 |
| `cardiooracle_recent_lookups` | Last 10 NCT IDs searched (for quick-access) | v1 |
| `cardiooracle_theme` | "light" or "dark" | v1 |
| `cardiooracle_schema_version` | Integer, currently 1 | - |

On load, check `schema_version`. If missing or < current, run migration function and update. All reads wrapped in try/catch for private browsing fallback.

### Performance Budget

- **Plotly.js:** CDN-loaded (plotly-2.x.min.js, ~3.5 MB) — not bundled, same pattern as existing apps
- **Training data:** Embedded inline as `const TRAINING_DATA = [...]`. At ~700 trials x 15 features, estimated ~200 KB of JSON — negligible
- **Model coefficients:** Inline, < 5 KB
- **Target first meaningful paint:** < 2 seconds (no API calls on load; training data + model are embedded)
- **Prediction computation:** < 100ms for single trial (similarity search is O(N*D) where N=700, D=5)

---

## 6. File Structure

```
C:\Models\CardioOracle\
+-- CardioOracle.html              # Main app
+-- curate/                        # Python curation pipeline
|   +-- extract_aact.py            # AACT PostgreSQL queries
|   +-- label_outcomes.py          # Tier 1/2/3 labeling
|   +-- fit_model.py               # Logistic regression + priors
|   +-- export_training.py         # Produce JSON files
|   +-- validate_labels.py         # Cross-check vs landmark trials
+-- data/
|   +-- training_data.json         # Embedded into HTML
|   +-- model_coefficients.json
|   +-- landmark_trials.json       # Manually curated ~80 trials
|   +-- configs/
|       +-- cardiorenal.json       # Launch config
|       +-- cad.json               # Future (stub)
+-- tests/
|   +-- test_prediction.py         # Selenium: lookup, designer, calibration
|   +-- test_webr.py               # WebR validation tests
|   +-- test_curation.py           # Unit tests for labeling pipeline
+-- paper/
|   +-- cardiooracle_manuscript.md # Lancet Digital Health / JAMIA
+-- PLAN.md
+-- CLAUDE.md
```

---

## 7. TruthCert Integration

Every prediction is a certified claim with:
- Evidence locators: NCT IDs of similar trials, AACT snapshot date, model version hash
- Content hash: SHA-256 of training_data.json
- Transformation steps: features extracted, model components, weights
- Validator outcomes: WebR pass/fail, calibration AUC, Brier score

Export Prediction Bundle -> JSON receipt with full provenance.

---

## 8. Publication Strategy

### Primary Paper: Lancet Digital Health / JAMIA
*"CardioOracle: An Open-Access Tool for Predicting Cardiovascular Trial Outcomes Using Bayesian Historical Borrowing and Design Feature Analysis"*

Selling points:
1. First of its kind — no open-access browser-based trial prediction tool
2. Practical utility — trial planners optimize designs before spending billions
3. Transparent — all training data, coefficients, predictions inspectable/exportable
4. Validated — temporal hold-out calibration + WebR cross-validation
5. Living — training set refreshable from AACT

### Secondary Paper: Scientific Data
*"A Curated Dataset of Cardiovascular Clinical Trial Outcomes from ClinicalTrials.gov"*

The labeled dataset (~700 trials) as a standalone data descriptor. Reusable by other researchers.

---

## 9. Development Phases

| Phase | Scope | Target Lines |
|-------|-------|-------------|
| Phase 1 (MVP) | Python curation pipeline + embedded training data + Predict tab | ~5K HTML + ~800 Python |
| Phase 2 | Design tab with interactive sliders + live prediction | ~10K HTML |
| Phase 3 | Calibration tab + Training Data explorer + WebR validation | ~15K HTML |
| Phase 4 | TruthCert bundles + additional configs + publication polish | ~18K HTML |

---

## 10. Error Handling & Degradation

| Scenario | Behavior |
|----------|----------|
| CT.gov API unreachable / timeout | Show "CT.gov is currently unavailable. Try again or enter trial details manually in the Design tab." Retry button. No silent failure. |
| CT.gov returns malformed/unexpected JSON | Show "Could not parse trial data. NCT ID may be invalid or trial record is incomplete." Log parse error to console. |
| NCT ID exists but has no useful data (no endpoints, no enrollment) | Show prediction with available components only; flag missing features with "N/A" and widen credible interval. If >50% features missing, show INSUFFICIENT DATA instead of a prediction. |
| Fewer than 5 similar trials with similarity > 0.3, but >= 3 with similarity > 0.1 | Include all with similarity > 0.1, flag: "LOW CONFIDENCE — few closely similar trials. Prediction relies more on prior and design features." |
| Fewer than 3 similar trials with similarity > 0.1 | Bayesian component outputs INSUFFICIENT DATA. Final prediction uses only conditional power + meta-regression (re-weighted to 0.55 / 0.45). Prominent banner: "Limited historical comparators — prediction based on design features only." |
| WebR fails to load (WASM blocked, OOM) | WebR tab shows "WebR could not be initialized. Validation unavailable. All predictions use the JS engine, which is the primary computation engine." Other tabs function normally. |
| Training data corrupted / empty | Fatal error banner on load: "Training data failed integrity check. App cannot make predictions." Show SHA-256 mismatch details. |
| sessionStorage full / unavailable | Degrade gracefully: no caching of API responses, no designer state persistence. App functions fully otherwise. |
| Browser compatibility | Target: Chrome 90+, Firefox 90+, Edge 90+, Safari 15+. No IE support. Feature-detect `fetch`, `BigInt`, `structuredClone`. |

---

## 11. Key Risks & Mitigations (see also Section 10 for error handling)

| Risk | Mitigation |
|------|------------|
| AACT results too messy for reliable labeling | Tier system + manual curation of landmarks + conservative exclusion |
| Model AUC too low (<0.60) | Conditional power component provides floor — even a weak Bayesian component adds value when combined with known power calculations |
| CT.gov API rate limits in browser | Cache API responses in sessionStorage; fetch only on explicit user action, not on page load |
| Training set too small for some drug classes | Fall back to broader cardiovascular prior when class-specific data is sparse; flag predictions with wide CIs |
| Temporal validation leakage | Split on primary_completion_date (not start_date); boundary trials assigned by completion |
| Training set smaller than expected (< 300) | Reduce to ~8 core features, simplify regression, widen all CIs, display warning |

---

## 12. Non-Negotiables (from CLAUDE.md)

- OA-only: all data from CT.gov / AACT (public domain)
- No secrets: AACT credentials never embedded in HTML
- Memory != evidence: predictions cite NCT IDs + model hash, never memory
- Fail-closed: if similar trial count < 3, output INSUFFICIENT DATA, not a guess
- Determinism: fixed similarity weights, reproducible predictions given same training data

# Prospective Validation System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 6th "Prospective Validation" tab to CardioOracle.html with cohort management, status monitoring, outcome resolution, and a 7-metric analysis dashboard — all backed by a TruthCert hash chain.

**Architecture:** Single-file HTML addition (~1,500 lines of JS + ~200 lines of HTML + ~100 lines of CSS). Reuses existing `fetchTrialFromCTGov()`, `extractFeatures()`, `bayesianBorrowing()`, `conditionalPower()`, `metaRegressionPredict()`, `ensemblePredict()`, `sha256Hex()`, and Plotly.js. New code organized into IIFE sections following existing patterns.

**Tech Stack:** Vanilla JS, Web Crypto API (SHA-256), CT.gov API v2, Plotly.js, localStorage, xoshiro128** PRNG.

**Spec:** `docs/superpowers/specs/2026-04-01-prospective-validation-design.md`

---

## File Map

All changes go into a single file:

- **Modify:** `C:\Models\CardioOracle\CardioOracle.html`
  - **CSS** (after line ~310, before closing `</style>`): Add ~100 lines of `.pv-*` prefixed styles
  - **HTML** (after line 1196, before `</main>`): Add ~200 lines for the 6th tab panel
  - **Tab bar** (after line 793): Add 1 new `<button>` for the tab
  - **JS** (before line 4458, before closing `</script>`): Add ~1,500 lines in IIFE sections

No new files created — single-file HTML pattern.

---

## Existing Functions to Reuse (DO NOT rewrite)

| Function | Line | Returns |
|----------|------|---------|
| `fetchTrialFromCTGov(nctId)` | 1681 | CT.gov study object |
| `extractFeatures(ctgovData)` | 1739 | `{enrollment, duration, drug_class, endpoint_type, ...}` |
| `computeSimilarity(target, candidate)` | 1826 | `number` 0..1 |
| `bayesianBorrowing(target, trainingTrials, scoredTrials)` | 1897 | `{p, confidence, twins}` |
| `conditionalPower(target, similarTrials)` | 1964 | `{power, method, z}` |
| `metaRegressionPredict(features)` | 2056 | `{p, contributions}` |
| `ensemblePredict(bayesian, power, regression)` | 2127 | `{p, level, levelLabel}` |
| `sha256Hex(text)` | 2176 | `Promise<string>` SHA-256 hex |
| `classifyDrugJS(drugNames)` | 1627 | `string` drug class |
| `classifyEndpointJS(text)` | 1644 | `string` endpoint type |

Global data: `TRAINING_DATA` (line 1339), `CONFIG` (loaded from `DATA_LIBRARY`).

---

## Seed Data

The file `prospective_predictions_20260325.json` contains 25 predictions with this per-trial schema:
```json
{
  "nct_id": "NCT06307652",
  "area": "cardiorenal",
  "title": "...",
  "features": {
    "enrollment": 4800, "duration_months": 38,
    "drug_class": "sglt2i", "endpoint_type": "mortality",
    "comparator_type": "active", "double_blind": false,
    "placebo_controlled": false, "is_industry": true,
    "num_sites": 842, "has_dsmb": true,
    "population_tags": ["diabetic","CKD","AF"], "year": 2024
  },
  "prediction": {
    "p_success": 0.887, "level": "high",
    "components": { "bayesian": 0.8, "power": 1, "regression": 0.8672 }
  },
  "outcome": null, "outcome_date": null, "outcome_source": null
}
```

This data must be embedded in the HTML as `SEED_PREDICTIONS` (const array) and used to populate the genesis block of the hash chain on first load.

---

## Task 1: Add CSS Styles for Prospective Validation Tab

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (CSS section, before `</style>` tag)

Find the closing `</style>` tag (search for it near line 710). Insert the new styles BEFORE it.

- [ ] **Step 1: Find the exact `</style>` line**

```bash
cd C:/Models/CardioOracle && grep -n '</style>' CardioOracle.html
```

- [ ] **Step 2: Insert PV CSS styles before `</style>`**

Insert this CSS block immediately before `</style>`:

```css
/* ═══ PROSPECTIVE VALIDATION TAB ═══════════════════════════════════ */
.pv-panels { display: flex; flex-direction: column; gap: 1.5rem; }
.pv-toolbar { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
.pv-toolbar .search-input { max-width: 200px; }
.pv-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; }
.pv-badge--recruiting { background: var(--green-bg); color: var(--success); }
.pv-badge--active { background: var(--green-bg); color: var(--success); }
.pv-badge--completed { background: var(--amber-bg); color: var(--warning); }
.pv-badge--results { background: #cfe2ff; color: #084298; }
[data-theme="dark"] .pv-badge--results { background: #031633; color: #6ea8fe; }
.pv-badge--terminated { background: var(--red-bg); color: var(--danger); }
.pv-badge--new { background: var(--tab-active); color: #fff; margin-left: 4px; font-size: 0.65rem; }
.pv-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.pv-table th, .pv-table td { padding: 6px 10px; text-align: left; border-bottom: 1px solid var(--border); }
.pv-table th { font-weight: 600; color: var(--text-muted); cursor: pointer; user-select: none; }
.pv-table th:hover { color: var(--text-accent); }
.pv-table tr.pv-correct { background: var(--green-bg); }
.pv-table tr.pv-incorrect { background: var(--red-bg); }
.pv-chain-ok { color: var(--success); font-weight: 600; }
.pv-chain-broken { color: var(--danger); font-weight: 600; }
.pv-progress-msg { text-align: center; padding: 2rem; color: var(--text-muted); font-size: 1.1rem; }
.pv-chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
@media (max-width: 900px) { .pv-chart-grid { grid-template-columns: 1fr; } }
.pv-chart-box { background: var(--bg-card); border-radius: var(--radius); padding: 1rem; border: 1px solid var(--border); }
.pv-chart-box h3 { margin: 0 0 0.5rem; font-size: 0.95rem; }
.pv-resolve-form { display: flex; flex-direction: column; gap: 0.5rem; padding: 0.75rem; background: var(--bg-input); border-radius: var(--radius); margin-top: 0.5rem; }
.pv-resolve-form label { font-weight: 500; font-size: 0.85rem; }
.pv-resolve-form input, .pv-resolve-form select, .pv-resolve-form textarea { font-size: 0.85rem; padding: 4px 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg-card); color: var(--text); }
.pv-resolve-form textarea { min-height: 50px; resize: vertical; }
.pv-timeline-chart { width: 100%; min-height: 300px; }
.pv-score-summary { display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
.pv-score-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius); padding: 0.75rem 1.25rem; text-align: center; min-width: 120px; }
.pv-score-card .pv-score-val { font-size: 1.5rem; font-weight: 700; color: var(--text-accent); }
.pv-score-card .pv-score-lbl { font-size: 0.75rem; color: var(--text-muted); }
.pv-empty-state { text-align: center; padding: 3rem 1rem; color: var(--text-muted); }
.pv-empty-state p { margin: 0.5rem 0; }
```

- [ ] **Step 3: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "style: add CSS for prospective validation tab"
```

---

## Task 2: Add Tab Button and HTML Panel Structure

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (tab bar ~line 793, panel area ~line 1196)

- [ ] **Step 1: Add tab button after WebR tab button (after line 793, before `</div>` closing the tab-bar)**

Find the closing `</div>` of the tab-bar (immediately after the WebR button). Insert:

```html
  <button
    class="tab-btn"
    role="tab"
    id="tab-validation"
    aria-selected="false"
    aria-controls="panel-validation"
    tabindex="-1"
    type="button"
  >Prospective Validation</button>
```

- [ ] **Step 2: Add panel section after WebR panel (after line 1196 `</section>`, before `</main>`)**

Insert this HTML block between the last `</section>` and `</main>`:

```html
  <!-- ── Prospective Validation Panel ─────────────────────────── -->
  <section
    id="panel-validation"
    class="tab-panel tab-content"
    role="tabpanel"
    aria-labelledby="tab-validation"
  >
    <div class="pv-panels">

      <!-- ── Panel 1: Cohort Management ──────────────────────── -->
      <div class="card">
        <h2 class="card-title">Cohort Management</h2>
        <div class="pv-toolbar">
          <input type="text" class="search-input pv-toolbar-input" id="pv-manualNctInput"
                 placeholder="NCT ID (e.g. NCT06307652)" aria-label="Enter NCT ID to add">
          <button class="search-btn" id="pv-addBtn" type="button">Add Trial</button>
          <button class="search-btn" id="pv-discoverBtn" type="button">Auto-Discover</button>
          <span id="pv-discoverStatus" style="font-size:0.8rem;color:var(--text-muted)" aria-live="polite"></span>
        </div>

        <!-- Review Queue -->
        <div id="pv-reviewSection" style="display:none;margin-top:1rem">
          <h3 style="font-size:0.95rem;margin-bottom:0.5rem">Review Queue
            <span id="pv-reviewCount" class="pv-badge pv-badge--results">0</span>
          </h3>
          <div style="overflow-x:auto">
            <table class="pv-table" id="pv-reviewTable">
              <thead>
                <tr>
                  <th>NCT ID</th><th>Title</th><th>Drug Class</th><th>Endpoint</th>
                  <th>Enrollment</th><th>Phase</th><th>Predictability</th><th>Action</th>
                </tr>
              </thead>
              <tbody id="pv-reviewTbody"></tbody>
            </table>
          </div>
        </div>

        <!-- Locked Cohort -->
        <div style="margin-top:1rem">
          <h3 style="font-size:0.95rem;margin-bottom:0.5rem">Locked Cohort
            <span id="pv-cohortCount" class="pv-badge pv-badge--recruiting">0</span>
          </h3>
          <div style="overflow-x:auto">
            <table class="pv-table" id="pv-cohortTable">
              <thead>
                <tr>
                  <th>Seq</th><th>NCT ID</th><th>Area</th><th>Drug</th><th>Endpoint</th>
                  <th>P(success)</th><th>Confidence</th><th>Locked</th><th>Status</th>
                </tr>
              </thead>
              <tbody id="pv-cohortTbody"></tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ── Panel 2: Monitoring ─────────────────────────────── -->
      <div class="card">
        <h2 class="card-title">Monitoring &amp; Resolution</h2>
        <div class="pv-toolbar">
          <button class="search-btn" id="pv-checkStatusBtn" type="button">Check All Statuses</button>
          <button class="search-btn" id="pv-verifyChainBtn" type="button">Verify Chain</button>
          <span id="pv-chainStatus" aria-live="polite"></span>
          <span id="pv-statusProgress" style="font-size:0.8rem;color:var(--text-muted)" aria-live="polite"></span>
        </div>

        <!-- Resolution Queue -->
        <div id="pv-resolveSection" style="display:none;margin-top:1rem">
          <h3 style="font-size:0.95rem;margin-bottom:0.5rem">Resolution Queue
            <span id="pv-resolveCount" class="pv-badge pv-badge--completed">0</span>
          </h3>
          <div id="pv-resolveList"></div>
        </div>

        <!-- Timeline Chart -->
        <div style="margin-top:1rem">
          <h3 style="font-size:0.95rem;margin-bottom:0.5rem">Trial Timeline</h3>
          <div id="pv-timelineChart" class="pv-timeline-chart"></div>
        </div>
      </div>

      <!-- ── Panel 3: Analysis Dashboard ─────────────────────── -->
      <div class="card">
        <h2 class="card-title">Analysis Dashboard</h2>
        <div id="pv-dashboardMsg" class="pv-progress-msg" aria-live="polite">
          0 / 0 trials resolved &mdash; need 5+ for analysis.
        </div>
        <div id="pv-dashboard" style="display:none">
          <!-- Score Summary Cards -->
          <div class="pv-score-summary" id="pv-scoreSummary"></div>

          <!-- Scorecard Table -->
          <div style="overflow-x:auto;margin-bottom:1.5rem">
            <table class="pv-table" id="pv-scorecardTable">
              <thead>
                <tr>
                  <th>#</th><th>NCT ID</th><th>Area</th><th>Drug</th><th>Endpoint</th>
                  <th>P(success)</th><th>Actual</th><th>Correct?</th><th>Confidence</th>
                </tr>
              </thead>
              <tbody id="pv-scorecardTbody"></tbody>
            </table>
          </div>

          <!-- Chart Grid -->
          <div class="pv-chart-grid">
            <div class="pv-chart-box"><h3>ROC Curve</h3><div id="pv-rocChart"></div></div>
            <div class="pv-chart-box"><h3>Calibration Plot</h3><div id="pv-calChart"></div></div>
            <div class="pv-chart-box"><h3>Brier Decomposition</h3><div id="pv-brierChart"></div></div>
            <div class="pv-chart-box"><h3>Decision Curve</h3><div id="pv-dcaChart"></div></div>
            <div class="pv-chart-box"><h3>Component Comparison</h3><div id="pv-compChart"></div></div>
            <div class="pv-chart-box"><h3>Temporal Tracking</h3><div id="pv-tempChart"></div></div>
          </div>
        </div>
      </div>

      <!-- ── Export / Import ─────────────────────────────────── -->
      <div class="card">
        <h2 class="card-title">Data Management</h2>
        <div class="pv-toolbar">
          <button class="search-btn" id="pv-exportBtn" type="button">Export Validation Bundle</button>
          <button class="search-btn" id="pv-importBtn" type="button">Import Validation Bundle</button>
          <input type="file" id="pv-importFile" accept=".json" style="display:none" aria-label="Select JSON file to import">
          <span id="pv-importStatus" style="font-size:0.8rem" aria-live="polite"></span>
        </div>
      </div>

    </div>
  </section>
```

- [ ] **Step 3: Verify div balance**

```bash
cd C:/Models/CardioOracle && grep -c '<div[\s>]' CardioOracle.html && grep -c '</div>' CardioOracle.html
```

Counts should match (within ±1 for regex inside `<script>`, which we verify manually).

- [ ] **Step 4: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "feat: add prospective validation tab HTML structure"
```

---

## Task 3: Embed Seed Predictions and localStorage Persistence Layer

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (JS section, insert before the final `})();` of the tutorial IIFE at ~line 4457)

All JS for the prospective validation tab goes into a new IIFE section. This task adds the data layer: seed data, localStorage read/write, and hash chain computation.

- [ ] **Step 1: Read the full prospective_predictions_20260325.json to extract the 25 trial objects**

```bash
cd C:/Models/CardioOracle && python -c "import json; d=json.load(open('prospective_predictions_20260325.json')); print(len(d['trials']), 'trials'); [print(t['nct_id'],t['area']) for t in d['trials']]"
```

- [ ] **Step 2: Insert the Prospective Validation IIFE with seed data + persistence**

Find the line containing the final `</script>` tag (line ~4459). Insert the following IIFE block BEFORE it. The seed data array `SEED_PREDICTIONS` should be populated from `prospective_predictions_20260325.json` — each entry mapped to the locked entry schema.

Insert before `</script>`:

```javascript
/* ════════════════════════════════════════════════════════════════════
   SECTION PV — PROSPECTIVE VALIDATION SYSTEM
   Hash-chain backed cohort tracking, monitoring, and analysis.
════════════════════════════════════════════════════════════════════ */
(function initProspectiveValidation() {
'use strict';

// ── PV Constants ──────────────────────────────────────────────────
const PV_KEYS = {
  cohort:       'cardiooracle_pv_cohort',
  resolutions:  'cardiooracle_pv_resolutions',
  queue:        'cardiooracle_pv_queue',
  lastDiscover: 'cardiooracle_pv_last_discovery',
  lastStatus:   'cardiooracle_pv_last_status_check',
  seeded:       'cardiooracle_pv_seeded'
};
const PV_MODEL_VERSION = 'cardiooracle_v1.0';

// ── Seed Data (25 predictions from 2026-03-25) ───────────────────
// Populated from prospective_predictions_20260325.json
// Each entry: { nct_id, area, title, features, prediction }
const SEED_PREDICTIONS = /* EMBED_HERE: paste the 25-trial array from prospective_predictions_20260325.json trials[] field. Each object keeps: nct_id, area, title, features (full object), prediction (full object). Strip meta_regression_detail, conditional_power_detail, bayesian_detail to save space. */[];

// ── Hash Chain Engine ─────────────────────────────────────────────

/**
 * Compute entry hash for a prediction chain entry.
 * @param {Object} entry - The entry (without entry_hash set)
 * @param {string|null} prevHash - Hash of previous entry (null for genesis)
 * @returns {Promise<string>}
 */
async function pvComputeEntryHash(entry, prevHash) {
  const parts = [
    entry.nct_id,
    entry.locked_at,
    String(entry.prediction.p_ensemble),
    String(entry.prediction.p_bayes),
    String(entry.prediction.p_power),
    String(entry.prediction.p_reg),
    entry.trial_snapshot.drug_class,
    entry.trial_snapshot.endpoint_type,
    String(entry.trial_snapshot.enrollment ?? 0),
    String(entry.trial_snapshot.duration_months ?? 0),
    entry.training_hash,
    prevHash ?? 'NULL'
  ];
  return sha256Hex(parts.join('|'));
}

/**
 * Compute resolution hash.
 * @param {Object} res - Resolution record
 * @returns {Promise<string>}
 */
async function pvComputeResolutionHash(res) {
  const parts = [
    res.nct_id,
    res.resolved_at,
    res.outcome,
    String(res.evidence.p_value ?? ''),
    String(res.evidence.hr ?? ''),
    res.prediction_entry_hash
  ];
  return sha256Hex(parts.join('|'));
}

/**
 * Verify entire prediction chain integrity.
 * @param {Array} chain
 * @returns {Promise<{valid: boolean, brokenAt: number|null}>}
 */
async function pvVerifyChain(chain) {
  let prevHash = null;
  for (let i = 0; i < chain.length; i++) {
    const entry = chain[i];
    const expected = await pvComputeEntryHash(entry, prevHash);
    if (expected !== entry.entry_hash) {
      return { valid: false, brokenAt: i };
    }
    prevHash = entry.entry_hash;
  }
  return { valid: true, brokenAt: null };
}

/**
 * Verify resolution chain integrity.
 * @param {Array} resolutions
 * @returns {Promise<{valid: boolean, brokenAt: number|null}>}
 */
async function pvVerifyResolutions(resolutions) {
  for (let i = 0; i < resolutions.length; i++) {
    const res = resolutions[i];
    const expected = await pvComputeResolutionHash(res);
    if (expected !== res.resolution_hash) {
      return { valid: false, brokenAt: i };
    }
  }
  return { valid: true, brokenAt: null };
}

// ── localStorage Persistence ──────────────────────────────────────

function pvLoad(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (_) { return null; }
}

function pvSave(key, data) {
  try {
    localStorage.setItem(key, JSON.stringify(data));
  } catch (e) {
    console.warn('PV localStorage save failed:', e);
  }
}

/** Get the locked prediction cohort (array). */
function pvGetCohort() { return pvLoad(PV_KEYS.cohort) ?? []; }
/** Save the locked prediction cohort. */
function pvSaveCohort(cohort) { pvSave(PV_KEYS.cohort, cohort); }
/** Get resolution records (array). */
function pvGetResolutions() { return pvLoad(PV_KEYS.resolutions) ?? []; }
/** Save resolution records. */
function pvSaveResolutions(res) { pvSave(PV_KEYS.resolutions, res); }
/** Get review queue (array). */
function pvGetQueue() { return pvLoad(PV_KEYS.queue) ?? []; }
/** Save review queue. */
function pvSaveQueue(q) { pvSave(PV_KEYS.queue, q); }

// ── Seed on First Load ───────────────────────────────────────────

async function pvSeedIfNeeded() {
  if (localStorage.getItem(PV_KEYS.seeded) === '1') return;
  if (pvGetCohort().length > 0) {
    localStorage.setItem(PV_KEYS.seeded, '1');
    return;
  }

  // Compute training data hash once
  const trainingJson = JSON.stringify((typeof TRAINING_DATA !== 'undefined' ? TRAINING_DATA.trials : null) ?? []);
  const trainingHash = await sha256Hex(trainingJson);

  const cohort = [];
  let prevHash = null;
  const seedTimestamp = '2026-03-25T10:43:16.485Z'; // Original prediction timestamp

  for (let i = 0; i < SEED_PREDICTIONS.length; i++) {
    const s = SEED_PREDICTIONS[i];
    const entry = {
      seq: i + 1,
      nct_id: s.nct_id,
      locked_at: seedTimestamp,
      prediction: {
        p_ensemble: s.prediction.p_success,
        p_bayes: s.prediction.components.bayesian,
        p_power: s.prediction.components.power,
        p_reg: s.prediction.components.regression,
        confidence: s.prediction.level.toUpperCase()
      },
      trial_snapshot: {
        title: s.title,
        drug_class: s.features.drug_class,
        endpoint_type: s.features.endpoint_type,
        enrollment: s.features.enrollment,
        duration_months: s.features.duration_months,
        phase: 'PHASE3',
        area: s.area
      },
      model_version: PV_MODEL_VERSION,
      training_hash: trainingHash,
      prev_hash: prevHash,
      status: 'RECRUITING',
      last_status_check: null,
      entry_hash: '' // computed below
    };
    entry.entry_hash = await pvComputeEntryHash(entry, prevHash);
    prevHash = entry.entry_hash;
    cohort.push(entry);
  }

  pvSaveCohort(cohort);
  localStorage.setItem(PV_KEYS.seeded, '1');
}
```

Note: The actual `SEED_PREDICTIONS` array must be populated by reading `prospective_predictions_20260325.json` and extracting the `.trials` array. Keep only `nct_id`, `area`, `title`, `features`, and `prediction` fields per trial. Remove `meta_regression_detail`, `conditional_power_detail`, `bayesian_detail` to save space.

- [ ] **Step 3: Verify no `</script>` literal inside the JS block**

```bash
cd C:/Models/CardioOracle && grep -n '</script>' CardioOracle.html
```

Should only find the legitimate closing tag at the end of the file.

- [ ] **Step 4: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "feat(pv): hash chain engine + localStorage persistence + seed data"
```

---

## Task 4: Cohort Management — Add Trial + Auto-Discover + Review Queue

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (continue inside the PV IIFE from Task 3)

This task adds the functions for manual trial addition, auto-discovery from CT.gov, and the review queue UI.

- [ ] **Step 1: Add the prediction-and-lock function**

Append inside the PV IIFE (before the closing `})();`):

```javascript
// ── Predict and Lock a Trial ──────────────────────────────────────

/**
 * Run full prediction on a trial and lock it into the hash chain.
 * @param {Object} ctgovData - Raw CT.gov API response
 * @param {string} area - 'cardiorenal' | 'cad' | 'af'
 * @returns {Promise<Object>} The locked entry
 */
async function pvPredictAndLock(ctgovData, area) {
  const features = extractFeatures(ctgovData);
  const trainingTrials = TRAINING_DATA.trials ?? [];
  const scoredTrials = trainingTrials.map(t => ({
    trial: t,
    sim: computeSimilarity(features, t)
  }));
  const bayesian   = bayesianBorrowing(features, trainingTrials, scoredTrials);
  const power      = conditionalPower(features, scoredTrials);
  const regression = metaRegressionPredict(features);
  const ensemble   = ensemblePredict(bayesian, power, regression);

  const nctId = ctgovData.protocolSection?.identificationModule?.nctId
             ?? ctgovData.identificationModule?.nctId ?? '';

  const trainingJson = JSON.stringify(trainingTrials);
  const trainingHash = await sha256Hex(trainingJson);

  const cohort = pvGetCohort();
  const prevHash = cohort.length > 0 ? cohort[cohort.length - 1].entry_hash : null;

  const entry = {
    seq: cohort.length + 1,
    nct_id: nctId,
    locked_at: new Date().toISOString(),
    prediction: {
      p_ensemble: ensemble.p,
      p_bayes: bayesian.p ?? null,
      p_power: power.power ?? null,
      p_reg: regression.p ?? null,
      confidence: ensemble.levelLabel?.toUpperCase() ?? 'MODERATE'
    },
    trial_snapshot: {
      title: features.title ?? nctId,
      drug_class: features.drug_class ?? 'unknown',
      endpoint_type: features.endpoint_type ?? 'unknown',
      enrollment: features.enrollment,
      duration_months: features.duration,
      phase: (ctgovData.protocolSection?.designModule?.phases ?? [''])[0] ?? '',
      area: area
    },
    model_version: PV_MODEL_VERSION,
    training_hash: trainingHash,
    prev_hash: prevHash,
    status: 'RECRUITING',
    last_status_check: null,
    entry_hash: ''
  };
  entry.entry_hash = await pvComputeEntryHash(entry, prevHash);

  cohort.push(entry);
  pvSaveCohort(cohort);
  return entry;
}
```

- [ ] **Step 2: Add the manual "Add Trial" handler**

```javascript
// ── Manual Add Handler ────────────────────────────────────────────

async function pvHandleAddTrial() {
  const input = document.getElementById('pv-manualNctInput');
  const nctId = (input.value ?? '').trim().toUpperCase();
  if (!nctId || !nctId.startsWith('NCT')) {
    pvShowStatus('pv-discoverStatus', 'Please enter a valid NCT ID.', 'var(--danger)');
    return;
  }

  // Check for duplicates
  const cohort = pvGetCohort();
  if (cohort.some(e => e.nct_id === nctId)) {
    pvShowStatus('pv-discoverStatus', nctId + ' is already in the cohort.', 'var(--warning)');
    return;
  }
  const queue = pvGetQueue();
  if (queue.some(e => e.nct_id === nctId)) {
    pvShowStatus('pv-discoverStatus', nctId + ' is already in the review queue.', 'var(--warning)');
    return;
  }

  pvShowStatus('pv-discoverStatus', 'Fetching ' + nctId + '...', 'var(--text-muted)');
  try {
    const ctgovData = await fetchTrialFromCTGov(nctId);
    const features = extractFeatures(ctgovData);
    const predictability = pvAssessPredictability(features);

    queue.push({
      nct_id: nctId,
      title: features.title ?? nctId,
      drug_class: features.drug_class ?? 'unknown',
      endpoint_type: features.endpoint_type ?? 'unknown',
      enrollment: features.enrollment,
      phase: (ctgovData.protocolSection?.designModule?.phases ?? [''])[0] ?? '',
      predictability: predictability,
      area: pvInferArea(features, ctgovData),
      _ctgovData: ctgovData
    });
    pvSaveQueue(queue);
    pvRenderReviewQueue();
    input.value = '';
    pvShowStatus('pv-discoverStatus', nctId + ' added to review queue.', 'var(--success)');
  } catch (err) {
    pvShowStatus('pv-discoverStatus', 'Error: ' + String(err), 'var(--danger)');
  }
}

/** Assess predictability of a trial based on feature completeness. */
function pvAssessPredictability(features) {
  let score = 0;
  if (features.drug_class && features.drug_class !== 'unknown') score++;
  if (features.endpoint_type && features.endpoint_type !== 'unknown') score++;
  if (features.enrollment !== null && features.enrollment > 0) score++;
  if (score === 3) return 'Ready';
  if (score >= 1) return 'Partial';
  return 'Skip';
}

/** Infer therapeutic area from conditions and drug class. */
function pvInferArea(features, ctgovData) {
  const conds = ((ctgovData.protocolSection?.conditionsModule?.conditions) ?? []).join(' ').toLowerCase();
  if (/atrial\s*(fib|flut)/i.test(conds)) return 'af';
  if (/coronary|acute coronary|myocardial infarction|angina/i.test(conds)) return 'cad';
  return 'cardiorenal'; // default
}

function pvShowStatus(elId, text, color) {
  const el = document.getElementById(elId);
  if (el) { el.textContent = text; el.style.color = color ?? 'var(--text-muted)'; }
}
```

- [ ] **Step 3: Add Auto-Discover function**

```javascript
// ── Auto-Discovery from CT.gov ────────────────────────────────────

const PV_DISCOVERY_QUERIES = [
  { area: 'cardiorenal', conditions: 'heart failure OR chronic kidney disease OR cardiorenal' },
  { area: 'cad', conditions: 'coronary artery disease OR acute coronary syndrome OR myocardial infarction' },
  { area: 'af', conditions: 'atrial fibrillation OR atrial flutter' }
];

async function pvAutoDiscover() {
  const lastCheck = localStorage.getItem(PV_KEYS.lastDiscover);
  if (lastCheck) {
    const elapsed = Date.now() - new Date(lastCheck).getTime();
    if (elapsed < 3600000) { // 1 hour cooldown
      pvShowStatus('pv-discoverStatus', 'Last checked ' + Math.round(elapsed/60000) + 'm ago. Try again later.', 'var(--warning)');
      return;
    }
  }

  const cohort = pvGetCohort();
  const queue = pvGetQueue();
  const existingIds = new Set([...cohort.map(e => e.nct_id), ...queue.map(e => e.nct_id)]);

  pvShowStatus('pv-discoverStatus', 'Discovering trials (0/' + PV_DISCOVERY_QUERIES.length + ')...', 'var(--text-muted)');
  let totalFound = 0;

  for (let qi = 0; qi < PV_DISCOVERY_QUERIES.length; qi++) {
    const q = PV_DISCOVERY_QUERIES[qi];
    pvShowStatus('pv-discoverStatus', 'Searching ' + q.area + ' (' + (qi+1) + '/' + PV_DISCOVERY_QUERIES.length + ')...', 'var(--text-muted)');

    try {
      const url = 'https://clinicaltrials.gov/api/v2/studies?query.cond=' +
        encodeURIComponent(q.conditions) +
        '&filter.overallStatus=RECRUITING' +
        '&filter.phase=PHASE2,PHASE3' +
        '&fields=protocolSection' +
        '&pageSize=50';

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);
      const resp = await fetch(url, { signal: controller.signal });
      clearTimeout(timeoutId);

      if (!resp.ok) continue;
      const data = await resp.json();
      const studies = data.studies ?? [];

      for (const study of studies) {
        const nctId = study.protocolSection?.identificationModule?.nctId;
        if (!nctId || existingIds.has(nctId)) continue;

        const features = extractFeatures(study);
        const predictability = pvAssessPredictability(features);
        if (predictability === 'Skip') continue;

        queue.push({
          nct_id: nctId,
          title: features.title ?? nctId,
          drug_class: features.drug_class ?? 'unknown',
          endpoint_type: features.endpoint_type ?? 'unknown',
          enrollment: features.enrollment,
          phase: (study.protocolSection?.designModule?.phases ?? [''])[0] ?? '',
          predictability: predictability,
          area: q.area,
          _ctgovData: study
        });
        existingIds.add(nctId);
        totalFound++;
      }
    } catch (err) {
      console.warn('PV discovery error for ' + q.area + ':', err);
    }

    // Rate limiting: 1s between queries
    if (qi < PV_DISCOVERY_QUERIES.length - 1) {
      await new Promise(r => setTimeout(r, 1000));
    }
  }

  pvSaveQueue(queue);
  localStorage.setItem(PV_KEYS.lastDiscover, new Date().toISOString());
  pvRenderReviewQueue();
  pvShowStatus('pv-discoverStatus', 'Found ' + totalFound + ' new candidate' + (totalFound !== 1 ? 's' : '') + '.', 'var(--success)');
}
```

- [ ] **Step 4: Add Review Queue rendering and approve/reject handlers**

```javascript
// ── Review Queue Rendering ────────────────────────────────────────

function pvRenderReviewQueue() {
  const queue = pvGetQueue();
  const section = document.getElementById('pv-reviewSection');
  const tbody = document.getElementById('pv-reviewTbody');
  const countEl = document.getElementById('pv-reviewCount');

  // Filter out entries without _ctgovData (they can't be approved)
  const reviewable = queue.filter(q => q._ctgovData || q.nct_id);
  countEl.textContent = String(reviewable.length);
  section.style.display = reviewable.length > 0 ? '' : 'none';

  tbody.innerHTML = '';
  for (const item of reviewable) {
    const tr = document.createElement('tr');
    tr.innerHTML =
      '<td><code>' + pvEsc(item.nct_id) + '</code></td>' +
      '<td>' + pvEsc((item.title ?? '').slice(0, 60)) + (item.title && item.title.length > 60 ? '...' : '') + '</td>' +
      '<td>' + pvEsc(item.drug_class) + '</td>' +
      '<td>' + pvEsc(item.endpoint_type) + '</td>' +
      '<td>' + (item.enrollment ?? '?') + '</td>' +
      '<td>' + pvEsc(item.phase) + '</td>' +
      '<td>' + pvEsc(item.predictability) + '</td>' +
      '<td></td>';

    const actionCell = tr.lastElementChild;
    const approveBtn = document.createElement('button');
    approveBtn.className = 'search-btn';
    approveBtn.textContent = 'Approve';
    approveBtn.style.cssText = 'padding:2px 8px;font-size:0.8rem;margin-right:4px';
    approveBtn.addEventListener('click', () => pvApproveFromQueue(item.nct_id));

    const rejectBtn = document.createElement('button');
    rejectBtn.textContent = 'Reject';
    rejectBtn.style.cssText = 'padding:2px 8px;font-size:0.8rem;background:var(--danger);color:#fff;border:none;border-radius:4px;cursor:pointer';
    rejectBtn.addEventListener('click', () => pvRejectFromQueue(item.nct_id));

    actionCell.appendChild(approveBtn);
    actionCell.appendChild(rejectBtn);
    tbody.appendChild(tr);
  }
}

async function pvApproveFromQueue(nctId) {
  const queue = pvGetQueue();
  const idx = queue.findIndex(q => q.nct_id === nctId);
  if (idx === -1) return;

  const item = queue[idx];
  let ctgovData = item._ctgovData;

  // If ctgovData was stripped (imported queue), re-fetch
  if (!ctgovData) {
    try {
      ctgovData = await fetchTrialFromCTGov(nctId);
    } catch (err) {
      pvShowStatus('pv-discoverStatus', 'Failed to fetch ' + nctId + ': ' + err, 'var(--danger)');
      return;
    }
  }

  try {
    await pvPredictAndLock(ctgovData, item.area ?? 'cardiorenal');
    queue.splice(idx, 1);
    // Strip _ctgovData from remaining queue items before saving (large objects)
    const cleanQueue = queue.map(q => {
      const { _ctgovData, ...rest } = q;
      return rest;
    });
    pvSaveQueue(cleanQueue);
    pvRenderReviewQueue();
    pvRenderCohortTable();
    pvShowStatus('pv-discoverStatus', nctId + ' locked into cohort.', 'var(--success)');
  } catch (err) {
    pvShowStatus('pv-discoverStatus', 'Error locking ' + nctId + ': ' + err, 'var(--danger)');
  }
}

function pvRejectFromQueue(nctId) {
  let queue = pvGetQueue();
  queue = queue.filter(q => q.nct_id !== nctId);
  pvSaveQueue(queue);
  pvRenderReviewQueue();
}

/** Minimal HTML escaping for table cells. */
function pvEsc(str) {
  if (str === null || str === undefined) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
```

- [ ] **Step 5: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "feat(pv): cohort management — add trial, auto-discover, review queue"
```

---

## Task 5: Cohort Table Rendering + Status Monitoring

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (continue in PV IIFE)

- [ ] **Step 1: Add cohort table rendering**

```javascript
// ── Cohort Table Rendering ────────────────────────────────────────

function pvRenderCohortTable() {
  const cohort = pvGetCohort();
  const resolutions = pvGetResolutions();
  const resMap = Object.fromEntries(resolutions.map(r => [r.nct_id, r]));
  const tbody = document.getElementById('pv-cohortTbody');
  const countEl = document.getElementById('pv-cohortCount');

  countEl.textContent = String(cohort.length);
  tbody.innerHTML = '';

  for (const entry of cohort) {
    const res = resMap[entry.nct_id];
    const tr = document.createElement('tr');
    const statusBadge = pvStatusBadge(entry.status, entry._statusChanged);
    const pFmt = (entry.prediction.p_ensemble * 100).toFixed(1) + '%';

    tr.innerHTML =
      '<td>' + entry.seq + '</td>' +
      '<td><code>' + pvEsc(entry.nct_id) + '</code></td>' +
      '<td>' + pvEsc(entry.trial_snapshot.area ?? '') + '</td>' +
      '<td>' + pvEsc(entry.trial_snapshot.drug_class) + '</td>' +
      '<td>' + pvEsc(entry.trial_snapshot.endpoint_type) + '</td>' +
      '<td><strong>' + pFmt + '</strong></td>' +
      '<td>' + pvEsc(entry.prediction.confidence) + '</td>' +
      '<td style="font-size:0.75rem">' + pvEsc(entry.locked_at.slice(0, 10)) + '</td>' +
      '<td>' + statusBadge + (res ? ' <span style="font-size:0.75rem;font-weight:600">' + pvEsc(res.outcome) + '</span>' : '') + '</td>';

    tbody.appendChild(tr);
  }
}

function pvStatusBadge(status, isNew) {
  const s = (status ?? 'UNKNOWN').toUpperCase();
  let cls = 'pv-badge ';
  if (s.includes('RECRUIT') || s.includes('ACTIVE'))      cls += 'pv-badge--recruiting';
  else if (s.includes('COMPLETED'))                        cls += 'pv-badge--completed';
  else if (s.includes('RESULT'))                           cls += 'pv-badge--results';
  else if (s.includes('TERMIN') || s.includes('WITHDR') || s.includes('SUSPEND')) cls += 'pv-badge--terminated';
  else                                                     cls += 'pv-badge--recruiting';

  let label = s.replace(/_/g, ' ');
  if (label.length > 15) label = label.slice(0, 15) + '...';
  let html = '<span class="' + cls + '">' + pvEsc(label) + '</span>';
  if (isNew) html += '<span class="pv-badge pv-badge--new">NEW</span>';
  return html;
}
```

- [ ] **Step 2: Add status checking (batch CT.gov polling)**

```javascript
// ── Status Monitoring ─────────────────────────────────────────────

async function pvCheckAllStatuses() {
  const cohort = pvGetCohort();
  if (cohort.length === 0) {
    pvShowStatus('pv-statusProgress', 'No trials in cohort.', 'var(--warning)');
    return;
  }

  const btn = document.getElementById('pv-checkStatusBtn');
  btn.disabled = true;
  let changedCount = 0;

  for (let i = 0; i < cohort.length; i++) {
    pvShowStatus('pv-statusProgress', 'Checking ' + (i+1) + '/' + cohort.length + '...', 'var(--text-muted)');

    try {
      const url = 'https://clinicaltrials.gov/api/v2/studies/' +
        encodeURIComponent(cohort[i].nct_id) +
        '?fields=protocolSection.statusModule';
      const controller = new AbortController();
      const tid = setTimeout(() => controller.abort(), 10000);
      const resp = await fetch(url, { signal: controller.signal });
      clearTimeout(tid);

      if (resp.ok) {
        const data = await resp.json();
        const newStatus = data.protocolSection?.statusModule?.overallStatus ?? cohort[i].status;
        const hasResults = !!(data.hasResults);

        const oldStatus = cohort[i].status;
        if (hasResults) {
          cohort[i].status = 'HAS_RESULTS';
        } else {
          cohort[i].status = newStatus.toUpperCase().replace(/ /g, '_');
        }
        cohort[i]._statusChanged = (cohort[i].status !== (oldStatus ?? '').toUpperCase().replace(/ /g, '_'));
        if (cohort[i]._statusChanged) changedCount++;
        cohort[i].last_status_check = new Date().toISOString();
      }
    } catch (err) {
      console.warn('PV status check failed for ' + cohort[i].nct_id + ':', err);
    }

    // Rate limit: 500ms between requests
    if (i < cohort.length - 1) {
      await new Promise(r => setTimeout(r, 500));
    }
  }

  pvSaveCohort(cohort);
  localStorage.setItem(PV_KEYS.lastStatus, new Date().toISOString());
  pvRenderCohortTable();
  pvUpdateResolveQueue();
  pvRenderTimeline();
  btn.disabled = false;
  pvShowStatus('pv-statusProgress',
    'Done. ' + changedCount + ' status change' + (changedCount !== 1 ? 's' : '') + ' detected.',
    changedCount > 0 ? 'var(--success)' : 'var(--text-muted)');
}
```

- [ ] **Step 3: Add chain verification UI handler**

```javascript
// ── Chain Verification UI ─────────────────────────────────────────

async function pvVerifyChainUI() {
  const statusEl = document.getElementById('pv-chainStatus');
  statusEl.textContent = 'Verifying...';
  statusEl.className = '';

  const cohort = pvGetCohort();
  const resolutions = pvGetResolutions();

  const chainResult = await pvVerifyChain(cohort);
  const resResult = await pvVerifyResolutions(resolutions);

  if (chainResult.valid && resResult.valid) {
    statusEl.textContent = 'Chain integrity verified (' + cohort.length + ' predictions, ' + resolutions.length + ' resolutions).';
    statusEl.className = 'pv-chain-ok';
  } else {
    let msg = 'CHAIN BROKEN: ';
    if (!chainResult.valid) msg += 'Prediction entry #' + (chainResult.brokenAt + 1) + ' tampered. ';
    if (!resResult.valid)   msg += 'Resolution entry #' + (resResult.brokenAt + 1) + ' tampered.';
    statusEl.textContent = msg;
    statusEl.className = 'pv-chain-broken';
  }
}
```

- [ ] **Step 4: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "feat(pv): cohort table rendering + status monitoring + chain verification"
```

---

## Task 6: Outcome Resolution System

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (continue in PV IIFE)

- [ ] **Step 1: Add resolution queue update and rendering**

```javascript
// ── Resolution Queue ──────────────────────────────────────────────

function pvUpdateResolveQueue() {
  const cohort = pvGetCohort();
  const resolutions = pvGetResolutions();
  const resolvedIds = new Set(resolutions.map(r => r.nct_id));

  // Trials that are completed/has results/terminated but not yet resolved
  const candidates = cohort.filter(e => {
    if (resolvedIds.has(e.nct_id)) return false;
    const s = (e.status ?? '').toUpperCase();
    return s.includes('COMPLETED') || s.includes('RESULT') || s.includes('TERMIN');
  });

  const section = document.getElementById('pv-resolveSection');
  const countEl = document.getElementById('pv-resolveCount');
  const list = document.getElementById('pv-resolveList');

  countEl.textContent = String(candidates.length);
  section.style.display = candidates.length > 0 ? '' : 'none';
  list.innerHTML = '';

  for (const entry of candidates) {
    const div = document.createElement('div');
    div.className = 'pv-resolve-form';
    div.setAttribute('data-nctid', entry.nct_id);

    const isSafetyTerminated = (entry.status ?? '').toUpperCase().includes('TERMIN');

    div.innerHTML =
      '<label><strong>' + pvEsc(entry.nct_id) + '</strong> — ' + pvEsc(entry.trial_snapshot.title) +
      ' <span class="pv-badge pv-badge--' + (isSafetyTerminated ? 'terminated' : 'completed') + '">' +
        pvEsc(entry.status) + '</span></label>' +
      '<div style="display:flex;gap:1rem;flex-wrap:wrap;align-items:center">' +
        '<label>Outcome: <select class="pv-resolve-outcome">' +
          '<option value="">— Select —</option>' +
          '<option value="SUCCESS"' + (isSafetyTerminated ? '' : '') + '>Success</option>' +
          '<option value="FAILURE">Failure</option>' +
          '<option value="SAFETY_FAILURE"' + (isSafetyTerminated ? ' selected' : '') + '>Safety Failure</option>' +
        '</select></label>' +
        '<label>p-value: <input type="text" class="pv-resolve-pval" placeholder="e.g. 0.003" style="width:80px"></label>' +
        '<label>Effect (HR/OR): <input type="text" class="pv-resolve-effect" placeholder="e.g. 0.82" style="width:80px"></label>' +
        '<label>CI lower: <input type="text" class="pv-resolve-ci-lo" placeholder="0.72" style="width:70px"></label>' +
        '<label>CI upper: <input type="text" class="pv-resolve-ci-hi" placeholder="0.94" style="width:70px"></label>' +
      '</div>' +
      '<label>DOI / Source: <input type="text" class="pv-resolve-doi" placeholder="https://doi.org/..." style="width:100%"></label>' +
      '<label>Notes: <textarea class="pv-resolve-notes" placeholder="Optional evidence notes"></textarea></label>' +
      '<button class="search-btn pv-resolve-confirm" type="button" style="align-self:flex-start">Confirm Resolution</button>';

    list.appendChild(div);

    // Attach confirm handler
    div.querySelector('.pv-resolve-confirm').addEventListener('click', () => pvConfirmResolution(entry.nct_id, div));
  }
}

async function pvConfirmResolution(nctId, formDiv) {
  const outcome = formDiv.querySelector('.pv-resolve-outcome').value;
  if (!outcome) {
    pvShowStatus('pv-statusProgress', 'Please select an outcome.', 'var(--danger)');
    return;
  }

  const parseFlt = (sel) => {
    const v = parseFloat(formDiv.querySelector(sel).value);
    return isFinite(v) ? v : null;
  };

  const cohort = pvGetCohort();
  const entry = cohort.find(e => e.nct_id === nctId);
  if (!entry) return;

  const resolution = {
    nct_id: nctId,
    resolved_at: new Date().toISOString(),
    outcome: outcome,
    evidence: {
      p_value: parseFlt('.pv-resolve-pval'),
      hr: parseFlt('.pv-resolve-effect'),
      ci_lower: parseFlt('.pv-resolve-ci-lo'),
      ci_upper: parseFlt('.pv-resolve-ci-hi'),
      doi: formDiv.querySelector('.pv-resolve-doi').value.trim() || null,
      notes: formDiv.querySelector('.pv-resolve-notes').value.trim() || null,
      source: 'manual'
    },
    prediction_entry_hash: entry.entry_hash,
    resolution_hash: ''
  };
  resolution.resolution_hash = await pvComputeResolutionHash(resolution);

  const resolutions = pvGetResolutions();
  resolutions.push(resolution);
  pvSaveResolutions(resolutions);

  pvUpdateResolveQueue();
  pvRenderCohortTable();
  pvRenderDashboard();
  pvShowStatus('pv-statusProgress', nctId + ' resolved as ' + outcome + '.', 'var(--success)');
}
```

- [ ] **Step 2: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "feat(pv): outcome resolution system with hash-locked confirmations"
```

---

## Task 7: Timeline Chart

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (continue in PV IIFE)

- [ ] **Step 1: Add timeline rendering**

```javascript
// ── Timeline Chart ────────────────────────────────────────────────

function pvRenderTimeline() {
  const cohort = pvGetCohort();
  const el = document.getElementById('pv-timelineChart');
  if (cohort.length === 0) {
    el.innerHTML = '<p class="pv-empty-state"><p>No trials to display.</p></p>';
    return;
  }

  const fontColor = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
  const gridColor = getComputedStyle(document.documentElement).getPropertyValue('--border').trim();

  // Group by area
  const areas = ['cardiorenal', 'cad', 'af'];
  const traces = [];
  const today = new Date().toISOString().slice(0, 10);

  for (const area of areas) {
    const trials = cohort.filter(e => (e.trial_snapshot.area ?? 'cardiorenal') === area);
    if (trials.length === 0) continue;

    const statusColors = {
      RECRUITING: '#198754', ACTIVE_NOT_YET_RECRUITING: '#198754',
      COMPLETED: '#c25e00', HAS_RESULTS: '#0d6efd',
      TERMINATED: '#dc3545', WITHDRAWN: '#dc3545', SUSPENDED: '#dc3545'
    };

    const y = trials.map(t => t.nct_id.slice(-7));
    const lockDates = trials.map(t => t.locked_at.slice(0, 10));
    const estEnd = trials.map(t => {
      const dur = t.trial_snapshot.duration_months ?? 36;
      const lockMs = new Date(t.locked_at).getTime();
      return new Date(lockMs + dur * 30.44 * 24 * 3600000).toISOString().slice(0, 10);
    });
    const colors = trials.map(t => statusColors[t.status] ?? '#6c757d');

    // Duration bars (lock date to estimated end)
    traces.push({
      type: 'scatter', mode: 'lines', x: [], y: [],
      line: { width: 8 }, name: area.toUpperCase(),
      showlegend: true, legendgroup: area,
      marker: { color: colors[0] }
    });

    for (let i = 0; i < trials.length; i++) {
      traces.push({
        type: 'scatter', mode: 'lines',
        x: [lockDates[i], estEnd[i]], y: [y[i], y[i]],
        line: { width: 8, color: colors[i] },
        showlegend: false, legendgroup: area,
        hovertext: trials[i].nct_id + ' (' + trials[i].trial_snapshot.drug_class + ')',
        hoverinfo: 'text'
      });
    }
  }

  const layout = {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { color: fontColor, size: 11 },
    margin: { t: 10, r: 20, b: 40, l: 80 },
    xaxis: { title: '', gridcolor: gridColor, type: 'date' },
    yaxis: { automargin: true, gridcolor: gridColor },
    shapes: [{
      type: 'line', x0: today, x1: today, y0: 0, y1: 1,
      xref: 'x', yref: 'paper',
      line: { color: '#dc3545', width: 2, dash: 'dash' }
    }],
    showlegend: true, legend: { orientation: 'h', y: -0.15 },
    height: Math.max(300, cohort.length * 25 + 80)
  };

  const fn = el._hasPlot ? Plotly.react : Plotly.newPlot;
  fn(el, traces, layout, { responsive: true, displayModeBar: false });
  el._hasPlot = true;
}
```

- [ ] **Step 2: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "feat(pv): trial timeline chart with status color coding"
```

---

## Task 8: Analysis Dashboard — Scorecard + Statistical Functions

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (continue in PV IIFE)

- [ ] **Step 1: Add xoshiro128** PRNG for bootstrap (if not already in file — check first)**

```bash
cd C:/Models/CardioOracle && grep -n 'xoshiro128' CardioOracle.html
```

If not found, add:

```javascript
// ── Seeded PRNG (xoshiro128**) for bootstrap ─────────────────────
function pvXoshiro128ss(a, b, c, d) {
  return function() {
    const t = b << 9; let r = a * 5; r = (r << 7 | r >>> 25) * 9;
    c ^= a; d ^= b; b ^= c; a ^= d; c ^= t;
    d = d << 11 | d >>> 21;
    return (r >>> 0) / 4294967296;
  };
}
function pvSeededRng(seed) {
  // Simple seed expansion
  let h = seed | 0;
  function next() { h = Math.imul(h ^ (h >>> 16), 2246822507); h = Math.imul(h ^ (h >>> 13), 3266489909); return (h ^= h >>> 16) >>> 0; }
  return pvXoshiro128ss(next(), next(), next(), next());
}
```

If already found, reuse the existing PRNG function — just alias it.

- [ ] **Step 2: Add core statistical functions**

```javascript
// ── Statistical Functions for Dashboard ───────────────────────────

/** Compute AUC via trapezoidal rule. */
function pvComputeAUC(yTrue, yProb) {
  const n = yTrue.length;
  if (n < 2) return null;
  // Create (prob, label) pairs sorted descending by prob
  const pairs = yTrue.map((y, i) => ({ p: yProb[i], y: y }));
  pairs.sort((a, b) => b.p - a.p);

  let tp = 0, fp = 0;
  const nPos = yTrue.filter(y => y === 1).length;
  const nNeg = n - nPos;
  if (nPos === 0 || nNeg === 0) return null;

  const roc = [{ fpr: 0, tpr: 0 }];
  for (const pair of pairs) {
    if (pair.y === 1) tp++;
    else fp++;
    roc.push({ fpr: fp / nNeg, tpr: tp / nPos });
  }

  // Trapezoidal AUC
  let auc = 0;
  for (let i = 1; i < roc.length; i++) {
    auc += (roc[i].fpr - roc[i-1].fpr) * (roc[i].tpr + roc[i-1].tpr) / 2;
  }
  return { auc, roc };
}

/** Bootstrap AUC with 95% CI. */
function pvBootstrapAUC(yTrue, yProb, nBoot, rng) {
  const n = yTrue.length;
  const aucs = [];
  for (let b = 0; b < nBoot; b++) {
    const idxs = Array.from({ length: n }, () => Math.floor(rng() * n));
    const yt = idxs.map(i => yTrue[i]);
    const yp = idxs.map(i => yProb[i]);
    const result = pvComputeAUC(yt, yp);
    if (result !== null) aucs.push(result.auc);
  }
  aucs.sort((a, b) => a - b);
  const lo = aucs[Math.floor(aucs.length * 0.025)] ?? null;
  const hi = aucs[Math.floor(aucs.length * 0.975)] ?? null;
  return { lo, hi };
}

/** Brier score + decomposition. */
function pvBrierScore(yTrue, yProb) {
  const n = yTrue.length;
  if (n === 0) return null;
  let brier = 0;
  for (let i = 0; i < n; i++) {
    brier += (yProb[i] - yTrue[i]) ** 2;
  }
  brier /= n;

  // Decomposition (Murphy 1973)
  const baseRate = yTrue.reduce((s, y) => s + y, 0) / n;
  const uncertainty = baseRate * (1 - baseRate);

  // Group into bins for reliability/resolution
  const nBins = Math.min(5, Math.max(2, Math.floor(n / 3)));
  const sorted = yTrue.map((y, i) => ({ y, p: yProb[i] })).sort((a, b) => a.p - b.p);
  const binSize = Math.ceil(n / nBins);
  let reliability = 0, resolution = 0;

  for (let b = 0; b < nBins; b++) {
    const start = b * binSize;
    const end = Math.min(start + binSize, n);
    const bin = sorted.slice(start, end);
    const nk = bin.length;
    if (nk === 0) continue;
    const meanP = bin.reduce((s, x) => s + x.p, 0) / nk;
    const obsRate = bin.reduce((s, x) => s + x.y, 0) / nk;
    reliability += nk * (meanP - obsRate) ** 2;
    resolution += nk * (obsRate - baseRate) ** 2;
  }
  reliability /= n;
  resolution /= n;

  return { brier, reliability, resolution, uncertainty };
}

/** Calibration slope via simple logistic regression on logit(p). */
function pvCalibrationSlope(yTrue, yProb) {
  // OLS of y on logit(p): slope = Cov(y, logit(p)) / Var(logit(p))
  const n = yTrue.length;
  if (n < 5) return null;
  const logits = yProb.map(p => {
    const clamped = Math.max(0.001, Math.min(0.999, p));
    return Math.log(clamped / (1 - clamped));
  });
  const meanY = yTrue.reduce((s, y) => s + y, 0) / n;
  const meanL = logits.reduce((s, l) => s + l, 0) / n;
  let cov = 0, varL = 0;
  for (let i = 0; i < n; i++) {
    cov  += (yTrue[i] - meanY) * (logits[i] - meanL);
    varL += (logits[i] - meanL) ** 2;
  }
  if (varL === 0) return null;
  return cov / varL;
}

/** Decision curve analysis: net benefit at threshold t. */
function pvNetBenefit(yTrue, yProb, threshold) {
  const n = yTrue.length;
  let tp = 0, fp = 0;
  for (let i = 0; i < n; i++) {
    if (yProb[i] >= threshold) {
      if (yTrue[i] === 1) tp++;
      else fp++;
    }
  }
  return (tp / n) - (fp / n) * (threshold / (1 - threshold));
}
```

- [ ] **Step 3: Add the main dashboard rendering orchestrator**

```javascript
// ── Dashboard Rendering ───────────────────────────────────────────

function pvRenderDashboard() {
  const cohort = pvGetCohort();
  const resolutions = pvGetResolutions();
  const resMap = Object.fromEntries(resolutions.map(r => [r.nct_id, r]));

  const resolved = cohort.filter(e => resMap[e.nct_id]);
  const msgEl = document.getElementById('pv-dashboardMsg');
  const dashEl = document.getElementById('pv-dashboard');

  msgEl.textContent = resolved.length + ' / ' + cohort.length + ' trials resolved' +
    (resolved.length < 5 ? ' \u2014 need 5+ for analysis.' : '.');
  msgEl.style.display = resolved.length >= 5 ? 'none' : '';
  dashEl.style.display = resolved.length >= 5 ? '' : 'none';

  if (resolved.length < 5) return;

  // Build arrays
  const yTrue = [];
  const yProb = [];
  const yBayes = [];
  const yPower = [];
  const yReg = [];
  const scoreRows = [];

  for (const entry of resolved) {
    const res = resMap[entry.nct_id];
    const actual = res.outcome === 'SUCCESS' ? 1 : 0;
    const predicted = entry.prediction.p_ensemble;
    yTrue.push(actual);
    yProb.push(predicted);
    yBayes.push(entry.prediction.p_bayes);
    yPower.push(entry.prediction.p_power);
    yReg.push(entry.prediction.p_reg);

    const correct = (predicted >= 0.5 && actual === 1) || (predicted < 0.5 && actual === 0);
    scoreRows.push({ entry, res, actual, predicted, correct });
  }

  // 1. Score summary cards
  pvRenderScoreSummary(yTrue, yProb);
  // 2. Scorecard table
  pvRenderScorecardTable(scoreRows);
  // 3. ROC curve
  pvRenderROC(yTrue, yProb);
  // 4. Calibration plot
  pvRenderCalibration(yTrue, yProb);
  // 5. Brier decomposition
  pvRenderBrier(yTrue, yProb);
  // 6. Decision curve
  pvRenderDCA(yTrue, yProb);
  // 7. Component comparison
  pvRenderComponentComparison(yTrue, yBayes, yPower, yReg, yProb);
  // 8. Temporal tracking
  pvRenderTemporalTracking(scoreRows);
}
```

- [ ] **Step 4: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "feat(pv): statistical engine — AUC, Brier, calibration, DCA, bootstrap"
```

---

## Task 9: Analysis Dashboard — Chart Rendering (7 Charts)

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (continue in PV IIFE)

- [ ] **Step 1: Score summary cards + scorecard table**

```javascript
// ── Score Summary Cards ───────────────────────────────────────────

function pvRenderScoreSummary(yTrue, yProb) {
  const el = document.getElementById('pv-scoreSummary');
  const rng = pvSeededRng(42);
  const aucResult = pvComputeAUC(yTrue, yProb);
  const aucCI = pvBootstrapAUC(yTrue, yProb, 2000, rng);
  const brierResult = pvBrierScore(yTrue, yProb);
  const calSlope = pvCalibrationSlope(yTrue, yProb);
  const accuracy = yTrue.reduce((s, y, i) => s + ((yProb[i] >= 0.5) === (y === 1) ? 1 : 0), 0) / yTrue.length;

  const cards = [
    { val: (accuracy * 100).toFixed(1) + '%', lbl: 'Accuracy' },
    { val: aucResult ? aucResult.auc.toFixed(3) : 'N/A', lbl: 'AUC' + (aucCI.lo !== null ? ' (' + aucCI.lo.toFixed(2) + '-' + aucCI.hi.toFixed(2) + ')' : '') },
    { val: brierResult ? brierResult.brier.toFixed(3) : 'N/A', lbl: 'Brier Score' },
    { val: calSlope !== null ? calSlope.toFixed(3) : 'N/A', lbl: 'Cal. Slope' },
    { val: String(yTrue.length), lbl: 'Resolved Trials' }
  ];

  el.innerHTML = cards.map(c =>
    '<div class="pv-score-card"><div class="pv-score-val">' + c.val + '</div><div class="pv-score-lbl">' + c.lbl + '</div></div>'
  ).join('');
}

// ── Scorecard Table ───────────────────────────────────────────────

function pvRenderScorecardTable(scoreRows) {
  const tbody = document.getElementById('pv-scorecardTbody');
  tbody.innerHTML = '';
  scoreRows.forEach((row, i) => {
    const tr = document.createElement('tr');
    tr.className = row.correct ? 'pv-correct' : 'pv-incorrect';
    tr.innerHTML =
      '<td>' + (i+1) + '</td>' +
      '<td><code>' + pvEsc(row.entry.nct_id) + '</code></td>' +
      '<td>' + pvEsc(row.entry.trial_snapshot.area ?? '') + '</td>' +
      '<td>' + pvEsc(row.entry.trial_snapshot.drug_class) + '</td>' +
      '<td>' + pvEsc(row.entry.trial_snapshot.endpoint_type) + '</td>' +
      '<td><strong>' + (row.predicted * 100).toFixed(1) + '%</strong></td>' +
      '<td>' + (row.actual === 1 ? 'Success' : 'Failure') + '</td>' +
      '<td>' + (row.correct ? 'Yes' : 'No') + '</td>' +
      '<td>' + pvEsc(row.entry.prediction.confidence) + '</td>';
    tbody.appendChild(tr);
  });
}
```

- [ ] **Step 2: ROC curve + Calibration plot**

```javascript
// ── ROC Curve ─────────────────────────────────────────────────────

function pvRenderROC(yTrue, yProb) {
  const el = document.getElementById('pv-rocChart');
  const fc = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
  const gc = getComputedStyle(document.documentElement).getPropertyValue('--border').trim();
  const aucResult = pvComputeAUC(yTrue, yProb);
  if (!aucResult) { el.innerHTML = '<p>Insufficient data.</p>'; return; }

  const rng = pvSeededRng(42);
  const ci = pvBootstrapAUC(yTrue, yProb, 2000, rng);

  const traces = [
    { x: [0, 1], y: [0, 1], mode: 'lines', line: { color: gc, dash: 'dash', width: 1 }, showlegend: false },
    { x: aucResult.roc.map(p => p.fpr), y: aucResult.roc.map(p => p.tpr), mode: 'lines',
      line: { color: '#0d6efd', width: 2 },
      name: 'AUC = ' + aucResult.auc.toFixed(3) + (ci.lo !== null ? ' (' + ci.lo.toFixed(2) + '-' + ci.hi.toFixed(2) + ')' : '') }
  ];
  const layout = {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { color: fc, size: 11 }, margin: { t: 10, r: 10, b: 40, l: 45 },
    xaxis: { title: 'False Positive Rate', range: [0, 1], gridcolor: gc },
    yaxis: { title: 'True Positive Rate', range: [0, 1.05], gridcolor: gc },
    showlegend: true, legend: { x: 0.4, y: 0.1 }, height: 300
  };
  const fn = el._hasPlot ? Plotly.react : Plotly.newPlot;
  fn(el, traces, layout, { responsive: true, displayModeBar: false });
  el._hasPlot = true;
}

// ── Calibration Plot ──────────────────────────────────────────────

function pvRenderCalibration(yTrue, yProb) {
  const el = document.getElementById('pv-calChart');
  const fc = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
  const gc = getComputedStyle(document.documentElement).getPropertyValue('--border').trim();
  const n = yTrue.length;
  const nBins = Math.min(5, Math.max(2, Math.floor(n / 3)));
  const sorted = yTrue.map((y, i) => ({ y, p: yProb[i] })).sort((a, b) => a.p - b.p);
  const binSize = Math.ceil(n / nBins);

  const binX = [], binY = [], binErr = [];
  for (let b = 0; b < nBins; b++) {
    const start = b * binSize;
    const end = Math.min(start + binSize, n);
    const bin = sorted.slice(start, end);
    const nk = bin.length;
    if (nk === 0) continue;
    const meanP = bin.reduce((s, x) => s + x.p, 0) / nk;
    const obsRate = bin.reduce((s, x) => s + x.y, 0) / nk;
    // Wilson interval
    const z = 1.96;
    const denom = 1 + z*z/nk;
    const center = (obsRate + z*z/(2*nk)) / denom;
    const halfWidth = z * Math.sqrt((obsRate*(1-obsRate) + z*z/(4*nk)) / nk) / denom;
    binX.push(meanP);
    binY.push(obsRate);
    binErr.push(halfWidth);
  }

  const traces = [
    { x: [0, 1], y: [0, 1], mode: 'lines', line: { color: gc, dash: 'dash', width: 1 }, showlegend: false },
    { x: binX, y: binY, mode: 'markers+lines', type: 'scatter',
      error_y: { type: 'data', array: binErr, visible: true, color: '#0d6efd' },
      marker: { color: '#0d6efd', size: 8 }, line: { color: '#0d6efd', width: 2 },
      name: 'Observed' }
  ];
  const calSlope = pvCalibrationSlope(yTrue, yProb);
  const layout = {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { color: fc, size: 11 }, margin: { t: 10, r: 10, b: 40, l: 45 },
    xaxis: { title: 'Predicted Probability', range: [0, 1], gridcolor: gc },
    yaxis: { title: 'Observed Frequency', range: [0, 1.05], gridcolor: gc },
    annotations: calSlope !== null ? [{ x: 0.05, y: 0.95, xref: 'paper', yref: 'paper', showarrow: false,
      text: 'Slope: ' + calSlope.toFixed(3), font: { size: 11, color: fc } }] : [],
    showlegend: false, height: 300
  };
  const fn = el._hasPlot ? Plotly.react : Plotly.newPlot;
  fn(el, traces, layout, { responsive: true, displayModeBar: false });
  el._hasPlot = true;
}
```

- [ ] **Step 3: Brier decomposition + Decision curve**

```javascript
// ── Brier Decomposition Chart ─────────────────────────────────────

function pvRenderBrier(yTrue, yProb) {
  const el = document.getElementById('pv-brierChart');
  const fc = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
  const result = pvBrierScore(yTrue, yProb);
  if (!result) { el.innerHTML = '<p>Insufficient data.</p>'; return; }

  const trace = {
    type: 'bar', orientation: 'h',
    y: ['Reliability', 'Resolution', 'Uncertainty', 'Overall Brier'],
    x: [result.reliability, result.resolution, result.uncertainty, result.brier],
    marker: { color: ['#dc3545', '#198754', '#6c757d', '#0d6efd'] },
    text: [result.reliability.toFixed(4), result.resolution.toFixed(4), result.uncertainty.toFixed(4), result.brier.toFixed(4)],
    textposition: 'outside'
  };
  const layout = {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { color: fc, size: 11 }, margin: { t: 10, r: 60, b: 30, l: 90 },
    xaxis: { title: '' }, yaxis: { automargin: true },
    showlegend: false, height: 200
  };
  const fn = el._hasPlot ? Plotly.react : Plotly.newPlot;
  fn(el, [trace], layout, { responsive: true, displayModeBar: false });
  el._hasPlot = true;
}

// ── Decision Curve Analysis ───────────────────────────────────────

function pvRenderDCA(yTrue, yProb) {
  const el = document.getElementById('pv-dcaChart');
  const fc = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
  const gc = getComputedStyle(document.documentElement).getPropertyValue('--border').trim();
  const n = yTrue.length;
  const prevalence = yTrue.reduce((s, y) => s + y, 0) / n;

  const thresholds = [];
  for (let t = 0.05; t <= 0.95; t += 0.05) thresholds.push(t);

  const nbModel = thresholds.map(t => pvNetBenefit(yTrue, yProb, t));
  const nbAll   = thresholds.map(t => prevalence - (1 - prevalence) * (t / (1 - t)));
  const nbNone  = thresholds.map(() => 0);

  const traces = [
    { x: thresholds, y: nbModel, mode: 'lines', name: 'CardioOracle', line: { color: '#0d6efd', width: 2 } },
    { x: thresholds, y: nbAll, mode: 'lines', name: 'Predict All', line: { color: '#6c757d', dash: 'dash', width: 1 } },
    { x: thresholds, y: nbNone, mode: 'lines', name: 'Predict None', line: { color: '#6c757d', dash: 'dot', width: 1 } }
  ];
  const layout = {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { color: fc, size: 11 }, margin: { t: 10, r: 10, b: 40, l: 55 },
    xaxis: { title: 'Threshold Probability', range: [0, 1], gridcolor: gc },
    yaxis: { title: 'Net Benefit', gridcolor: gc },
    showlegend: true, legend: { orientation: 'h', y: -0.2 }, height: 300
  };
  const fn = el._hasPlot ? Plotly.react : Plotly.newPlot;
  fn(el, traces, layout, { responsive: true, displayModeBar: false });
  el._hasPlot = true;
}
```

- [ ] **Step 4: Component comparison + Temporal tracking**

```javascript
// ── Component Comparison ──────────────────────────────────────────

function pvRenderComponentComparison(yTrue, yBayes, yPower, yReg, yEnsemble) {
  const el = document.getElementById('pv-compChart');
  const fc = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();

  // Filter out nulls per component
  function aucFor(probs) {
    const valid = yTrue.map((y, i) => ({ y, p: probs[i] })).filter(x => x.p !== null && isFinite(x.p));
    if (valid.length < 5) return null;
    const r = pvComputeAUC(valid.map(x => x.y), valid.map(x => x.p));
    return r ? r.auc : null;
  }

  const aucB = aucFor(yBayes);
  const aucP = aucFor(yPower);
  const aucR = aucFor(yReg);
  const aucE = aucFor(yEnsemble);

  const labels = ['Bayesian', 'Cond. Power', 'Meta-Reg', 'Ensemble'];
  const values = [aucB, aucP, aucR, aucE];
  const colors = ['#198754', '#c25e00', '#6f42c1', '#0d6efd'];

  const trace = {
    type: 'bar', x: labels, y: values.map(v => v ?? 0),
    marker: { color: colors },
    text: values.map(v => v !== null ? v.toFixed(3) : 'N/A'),
    textposition: 'outside'
  };
  const layout = {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { color: fc, size: 11 }, margin: { t: 10, r: 10, b: 30, l: 45 },
    yaxis: { title: 'AUC', range: [0, 1.1] }, showlegend: false, height: 250
  };
  const fn = el._hasPlot ? Plotly.react : Plotly.newPlot;
  fn(el, [trace], layout, { responsive: true, displayModeBar: false });
  el._hasPlot = true;
}

// ── Temporal Tracking ─────────────────────────────────────────────

function pvRenderTemporalTracking(scoreRows) {
  const el = document.getElementById('pv-tempChart');
  const fc = getComputedStyle(document.documentElement).getPropertyValue('--text').trim();
  const gc = getComputedStyle(document.documentElement).getPropertyValue('--border').trim();

  // Sort by resolution date
  const sorted = [...scoreRows].sort((a, b) =>
    new Date(a.res.resolved_at).getTime() - new Date(b.res.resolved_at).getTime()
  );

  const dates = [];
  const cumAcc = [];
  const cumAuc = [];
  let correctCount = 0;

  for (let i = 0; i < sorted.length; i++) {
    dates.push(sorted[i].res.resolved_at.slice(0, 10));
    if (sorted[i].correct) correctCount++;
    cumAcc.push((correctCount / (i + 1)) * 100);

    // Cumulative AUC (only when enough data)
    if (i >= 4) {
      const yt = sorted.slice(0, i + 1).map(r => r.actual);
      const yp = sorted.slice(0, i + 1).map(r => r.predicted);
      const result = pvComputeAUC(yt, yp);
      cumAuc.push(result ? result.auc * 100 : null);
    } else {
      cumAuc.push(null);
    }
  }

  const traces = [
    { x: dates, y: cumAcc, mode: 'lines+markers', name: 'Accuracy (%)',
      line: { color: '#0d6efd', width: 2 }, marker: { size: 5 } },
    { x: dates, y: cumAuc, mode: 'lines+markers', name: 'AUC (%)',
      line: { color: '#198754', width: 2 }, marker: { size: 5 }, connectgaps: true }
  ];
  const layout = {
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { color: fc, size: 11 }, margin: { t: 10, r: 10, b: 40, l: 45 },
    xaxis: { title: 'Resolution Date', type: 'date', gridcolor: gc },
    yaxis: { title: '%', range: [0, 105], gridcolor: gc },
    showlegend: true, legend: { orientation: 'h', y: -0.2 }, height: 300
  };
  const fn = el._hasPlot ? Plotly.react : Plotly.newPlot;
  fn(el, traces, layout, { responsive: true, displayModeBar: false });
  el._hasPlot = true;
}
```

- [ ] **Step 5: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "feat(pv): 7-chart analysis dashboard — ROC, calibration, Brier, DCA, components, temporal"
```

---

## Task 10: Export/Import + Event Wiring + Initialization

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (continue in PV IIFE — closing section)

- [ ] **Step 1: Add export function**

```javascript
// ── Export Validation Bundle ──────────────────────────────────────

async function pvExportBundle() {
  const cohort = pvGetCohort();
  const resolutions = pvGetResolutions();
  const resMap = Object.fromEntries(resolutions.map(r => [r.nct_id, r]));

  const resolved = cohort.filter(e => resMap[e.nct_id]);
  let accuracy = null, auc = null;
  if (resolved.length >= 5) {
    const yTrue = resolved.map(e => resMap[e.nct_id].outcome === 'SUCCESS' ? 1 : 0);
    const yProb = resolved.map(e => e.prediction.p_ensemble);
    accuracy = yTrue.reduce((s, y, i) => s + ((yProb[i] >= 0.5) === (y === 1) ? 1 : 0), 0) / yTrue.length;
    const aucResult = pvComputeAUC(yTrue, yProb);
    auc = aucResult ? aucResult.auc : null;
  }

  const bundle = {
    format: 'cardiooracle_prospective_v1',
    exported_at: new Date().toISOString(),
    model_version: PV_MODEL_VERSION,
    training_hash: cohort.length > 0 ? cohort[0].training_hash : null,
    predictions: cohort,
    resolutions: resolutions,
    summary: {
      total_tracked: cohort.length,
      resolved: resolutions.length,
      accuracy: accuracy,
      auc: auc
    }
  };

  const payload = JSON.stringify(bundle, null, 2);
  bundle.bundle_hash = await sha256Hex(JSON.stringify(cohort) + JSON.stringify(resolutions));

  const finalPayload = JSON.stringify(bundle, null, 2);
  const blob = new Blob([finalPayload], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'cardiooracle_validation_' + new Date().toISOString().slice(0, 10) + '.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 2: Add import function**

```javascript
// ── Import Validation Bundle ──────────────────────────────────────

async function pvImportBundle(file) {
  const statusEl = document.getElementById('pv-importStatus');
  statusEl.textContent = 'Reading file...';
  statusEl.style.color = 'var(--text-muted)';

  try {
    const text = await file.text();
    const bundle = JSON.parse(text);

    if (bundle.format !== 'cardiooracle_prospective_v1') {
      statusEl.textContent = 'Error: unrecognized format.';
      statusEl.style.color = 'var(--danger)';
      return;
    }

    statusEl.textContent = 'Verifying chain integrity...';

    // Verify prediction chain
    const chainResult = await pvVerifyChain(bundle.predictions ?? []);
    if (!chainResult.valid) {
      statusEl.textContent = 'Error: prediction chain broken at entry #' + (chainResult.brokenAt + 1) + '. Import refused.';
      statusEl.style.color = 'var(--danger)';
      return;
    }

    // Verify resolution chain
    const resResult = await pvVerifyResolutions(bundle.resolutions ?? []);
    if (!resResult.valid) {
      statusEl.textContent = 'Error: resolution chain broken at entry #' + (resResult.brokenAt + 1) + '. Import refused.';
      statusEl.style.color = 'var(--danger)';
      return;
    }

    // Merge: dedup by nct_id
    const existingCohort = pvGetCohort();
    const existingIds = new Set(existingCohort.map(e => e.nct_id));
    let newPredictions = 0;
    for (const entry of (bundle.predictions ?? [])) {
      if (!existingIds.has(entry.nct_id)) {
        existingCohort.push(entry);
        existingIds.add(entry.nct_id);
        newPredictions++;
      }
    }
    pvSaveCohort(existingCohort);

    const existingRes = pvGetResolutions();
    const resIds = new Set(existingRes.map(r => r.nct_id));
    let newResolutions = 0;
    for (const res of (bundle.resolutions ?? [])) {
      if (!resIds.has(res.nct_id)) {
        existingRes.push(res);
        resIds.add(res.nct_id);
        newResolutions++;
      }
    }
    pvSaveResolutions(existingRes);

    pvRenderAll();
    statusEl.textContent = 'Imported ' + newPredictions + ' predictions, ' + newResolutions + ' resolutions. Chain integrity verified.';
    statusEl.style.color = 'var(--success)';
  } catch (err) {
    statusEl.textContent = 'Error: ' + String(err);
    statusEl.style.color = 'var(--danger)';
  }
}
```

- [ ] **Step 3: Add event wiring and initialization**

```javascript
// ── Render All ────────────────────────────────────────────────────

function pvRenderAll() {
  pvRenderReviewQueue();
  pvRenderCohortTable();
  pvUpdateResolveQueue();
  pvRenderTimeline();
  pvRenderDashboard();
}

// ── Event Wiring ──────────────────────────────────────────────────

document.getElementById('pv-addBtn').addEventListener('click', pvHandleAddTrial);
document.getElementById('pv-manualNctInput').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') { e.preventDefault(); pvHandleAddTrial(); }
});
document.getElementById('pv-discoverBtn').addEventListener('click', pvAutoDiscover);
document.getElementById('pv-checkStatusBtn').addEventListener('click', pvCheckAllStatuses);
document.getElementById('pv-verifyChainBtn').addEventListener('click', pvVerifyChainUI);
document.getElementById('pv-exportBtn').addEventListener('click', pvExportBundle);
document.getElementById('pv-importBtn').addEventListener('click', function() {
  document.getElementById('pv-importFile').click();
});
document.getElementById('pv-importFile').addEventListener('change', function(e) {
  const file = e.target.files[0];
  if (file) pvImportBundle(file);
  e.target.value = ''; // Reset so same file can be re-imported
});

// ── Initialize ────────────────────────────────────────────────────

pvSeedIfNeeded().then(function() {
  pvRenderAll();
}).catch(function(err) {
  console.warn('PV initialization error:', err);
});

})(); // END Prospective Validation IIFE
```

- [ ] **Step 4: Verify no literal `</script>` inside JS**

```bash
cd C:/Models/CardioOracle && grep -n '</script>' CardioOracle.html | head -5
```

Should show exactly ONE match — the legitimate closing tag.

- [ ] **Step 5: Verify div balance**

```bash
cd C:/Models/CardioOracle && python -c "
import re
html = open('CardioOracle.html', encoding='utf-8').read()
opens = len(re.findall(r'<div[\s>]', html))
closes = len(re.findall(r'</div>', html))
print(f'<div>: {opens}, </div>: {closes}, diff: {opens - closes}')
"
```

Diff should be 0 (or ±1 if regex inside `<script>` matches — verify manually).

- [ ] **Step 6: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "feat(pv): export/import + event wiring + initialization — system complete"
```

---

## Task 11: Populate Seed Data from prospective_predictions_20260325.json

**Files:**
- Modify: `C:\Models\CardioOracle\CardioOracle.html` (replace the `SEED_PREDICTIONS = []` placeholder)

- [ ] **Step 1: Generate the seed array from the JSON file**

```bash
cd C:/Models/CardioOracle && python -c "
import json
d = json.load(open('prospective_predictions_20260325.json'))
out = []
for t in d['trials']:
    out.append({
        'nct_id': t['nct_id'],
        'area': t['area'],
        'title': t['title'],
        'features': {
            'enrollment': t['features']['enrollment'],
            'duration_months': t['features']['duration_months'],
            'drug_class': t['features']['drug_class'],
            'endpoint_type': t['features']['endpoint_type'],
            'comparator_type': t['features']['comparator_type'],
            'double_blind': t['features']['double_blind'],
            'placebo_controlled': t['features']['placebo_controlled'],
            'is_industry': t['features']['is_industry'],
            'num_sites': t['features']['num_sites'],
            'has_dsmb': t['features']['has_dsmb'],
            'year': t['features']['year']
        },
        'prediction': t['prediction']
    })
print(json.dumps(out, indent=2))
" > /tmp/seed_data.json
```

- [ ] **Step 2: Replace the empty `SEED_PREDICTIONS` array with the generated data**

Find `const SEED_PREDICTIONS = /* EMBED_HERE` and replace the entire line (up to and including `[];`) with:

```javascript
const SEED_PREDICTIONS = [/* paste the contents of /tmp/seed_data.json here */];
```

- [ ] **Step 3: Verify the seed count**

```bash
cd C:/Models/CardioOracle && grep -o 'nct_id' CardioOracle.html | wc -l
```

The count of `nct_id` occurrences should have increased by 25 (the seeded trials) compared to before.

- [ ] **Step 4: Commit**

```bash
cd C:/Models/CardioOracle && git add CardioOracle.html && git commit -m "feat(pv): embed 25 seed predictions from 2026-03-25 cohort"
```

---

## Task 12: Manual Testing + Browser Smoke Test

**Files:** None (testing only)

- [ ] **Step 1: Open CardioOracle.html in Chrome and verify the tab appears**

Open the file in a browser. Verify:
- 6th tab "Prospective Validation" is visible in the tab bar
- Clicking it shows the panel with 4 cards (Cohort Management, Monitoring, Analysis Dashboard, Data Management)
- 25 trials appear in the Locked Cohort table (auto-seeded)
- Tab keyboard navigation (ArrowRight/Left) includes the new tab

- [ ] **Step 2: Test chain verification**

Click "Verify Chain". Should show green "Chain integrity verified (25 predictions, 0 resolutions)."

- [ ] **Step 3: Test manual add**

Enter a valid NCT ID (e.g., `NCT04564742`) in the input field, click "Add Trial". Should:
- Appear in the Review Queue
- Show drug class, endpoint, enrollment, predictability
- "Approve" should lock it into cohort (now 26 entries)
- "Reject" should remove from queue

- [ ] **Step 4: Test export**

Click "Export Validation Bundle". Should download a JSON file with all 26 predictions and the bundle_hash.

- [ ] **Step 5: Test dark mode**

Toggle dark mode. Verify all PV elements render correctly with dark theme colors.

- [ ] **Step 6: Commit final**

```bash
cd C:/Models/CardioOracle && git add -A && git commit -m "feat: prospective validation system — complete (6th tab, hash chain, 7 charts)"
```

---

## Spec Coverage Verification

| Spec Section | Task(s) | Status |
|-------------|---------|--------|
| 1. Tab Structure & UI Layout | Task 2 | Covered |
| 2. TruthCert Hash Chain | Task 3 | Covered |
| 3. Auto-Discovery Engine | Task 4 | Covered |
| 4. Monitoring & Outcome Resolution | Tasks 5, 6 | Covered |
| 5. Analysis Dashboard (7 metrics) | Tasks 8, 9 | Covered |
| 6. Data Persistence & Export/Import | Tasks 3, 10 | Covered |
| Seed behavior (25 predictions) | Tasks 3, 11 | Covered |
| Timeline chart | Task 7 | Covered |
| Implementation constraints | All tasks | Enforced |

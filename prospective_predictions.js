#!/usr/bin/env node
/**
 * CardioOracle — Prospective Validation Batch Predictions
 * ========================================================
 * Generates timestamped predictions for currently recruiting Phase 3 CV trials.
 * Uses the EXACT same meta-regression coefficients + drug/endpoint classifiers
 * as the live CardioOracle HTML app.
 *
 * Purpose: Create irrefutable prospective evidence. When these trials report
 * results (2026-2031), we compare predictions vs outcomes.
 *
 * Usage: node prospective_predictions.js
 * Output: prospective_predictions_YYYYMMDD.json
 */

const https = require('https');
const fs = require('fs');

// ═══════════════════════════════════════════════════════════════════
// MODEL COEFFICIENTS — exact copy from cardiooracle.html line 2024
// ═══════════════════════════════════════════════════════════════════
const MODEL_COEFFICIENTS = {
  intercept: -0.45,
  enrollment_log: 0.12, duration_months: -0.003, placebo_controlled: 0.18,
  double_blind: 0.22, is_industry: -0.08, num_sites_log: 0.10,
  endpoint_mace: 0.35, endpoint_mortality: 0.28, endpoint_hf: 0.30,
  endpoint_renal: 0.20, endpoint_surrogate: 0.45,
  drug_sglt2i: 0.52, drug_mra_ns: 0.40, drug_glp1ra: 0.38,
  drug_pcsk9i: 0.30, drug_statin: 0.25,
  has_dsmb: 0.15, comparator_active: -0.12
};

// Ensemble weights — cardiorenal config
const ENSEMBLE_W = { bayesian: 0.40, conditional_power: 0.35, meta_regression: 0.25 };

// ═══════════════════════════════════════════════════════════════════
// DRUG + ENDPOINT CLASSIFIERS — exact copy from cardiooracle.html
// ═══════════════════════════════════════════════════════════════════
const DRUG_CLASS_MAP = {
  empagliflozin: 'sglt2i', dapagliflozin: 'sglt2i', canagliflozin: 'sglt2i',
  ertugliflozin: 'sglt2i', sotagliflozin: 'sglt2i', ipragliflozin: 'sglt2i',
  spironolactone: 'mra', eplerenone: 'mra',
  finerenone: 'ns_mra', esaxerenone: 'ns_mra', ocedurenone: 'ns_mra',
  balcinrenone: 'ns_mra', baxdrostat: 'ns_mra', vicadrostat: 'ns_mra',
  sacubitril: 'arni', entresto: 'arni',
  losartan: 'arb', irbesartan: 'arb', olmesartan: 'arb', telmisartan: 'arb',
  candesartan: 'arb', valsartan: 'arb',
  ramipril: 'acei', enalapril: 'acei', lisinopril: 'acei', captopril: 'acei',
  perindopril: 'acei',
  carvedilol: 'bb', metoprolol: 'bb', bisoprolol: 'bb', nebivolol: 'bb', atenolol: 'bb',
  semaglutide: 'glp1ra', liraglutide: 'glp1ra', dulaglutide: 'glp1ra',
  exenatide: 'glp1ra', tirzepatide: 'glp1ra',
  evolocumab: 'pcsk9i', alirocumab: 'pcsk9i', inclisiran: 'pcsk9i',
  atorvastatin: 'statin', rosuvastatin: 'statin', simvastatin: 'statin',
  rivaroxaban: 'anticoag', apixaban: 'anticoag', edoxaban: 'anticoag',
  dabigatran: 'anticoag', warfarin: 'anticoag',
  clopidogrel: 'antiplat', ticagrelor: 'antiplat', prasugrel: 'antiplat',
  aspirin: 'antiplat'
};

const ENDPOINT_KEYWORDS = [
  ['mace',      ['mace', 'major adverse cardiovascular', 'composite cardiovascular']],
  ['mortality', ['mortality', 'death', 'all-cause', 'cardiovascular death', 'cv death']],
  ['hf',        ['heart failure', 'hospitalization for heart failure', 'hf hospitalization', 'hfh']],
  ['renal',     ['renal', 'kidney', 'egfr', 'creatinine doubling', 'esrd', 'dialysis']],
  ['surrogate', ['hba1c', 'ldl', 'blood pressure', 'cholesterol', 'lvef', 'ejection fraction',
                 'plaque', 'fibrosis', 'remodeling', 'remodelling', 'nt-probnp', 'ntprobnp']]
];

// Class-level historical success rates from CardioOracle training data
// Used as Bayesian prior when full training corpus unavailable
const CLASS_PRIORS = {
  sglt2i:   { alpha: 8, beta: 2 },   // ~80% success (DAPA-HF, EMPEROR, EMPA-KIDNEY, DELIVER)
  ns_mra:   { alpha: 6, beta: 4 },   // ~60% (FIDELIO, FIGARO positive; some null)
  mra:      { alpha: 5, beta: 5 },   // ~50% (RALES+, TOPCAT mixed)
  glp1ra:   { alpha: 7, beta: 3 },   // ~70% (LEADER, SUSTAIN-6, SELECT, STEP-HFpEF)
  pcsk9i:   { alpha: 6, beta: 4 },   // ~60% (FOURIER+, ODYSSEY+)
  bb:       { alpha: 5, beta: 5 },   // ~50% (mature class, mixed recent trials)
  arni:     { alpha: 6, beta: 4 },   // ~60% (PARADIGM-HF+, PARAGON mixed)
  arb:      { alpha: 4, beta: 6 },   // ~40%
  acei:     { alpha: 5, beta: 5 },   // ~50%
  statin:   { alpha: 7, beta: 3 },   // ~70% (4S, JUPITER, etc.)
  anticoag: { alpha: 6, beta: 4 },   // ~60%
  antiplat: { alpha: 5, beta: 5 },   // ~50%
  other:    { alpha: 4.5, beta: 5.5 } // uninformative
};

// ═══════════════════════════════════════════════════════════════════
// CURATED TARGET TRIALS — recruiting Phase 3 CV trials (2026-03-25)
// ═══════════════════════════════════════════════════════════════════
const TARGET_TRIALS = [
  // ── Heart Failure / Cardiorenal ──
  { nctId: 'NCT06307652', area: 'cardiorenal', note: 'Balcinrenone/dapagliflozin vs dapa — AstraZeneca — N=4800 — HF events + CV death' },
  { nctId: 'NCT06677060', area: 'cardiorenal', note: 'Baxdrostat+dapagliflozin vs dapa — AstraZeneca — N=11300 — incident HF + CV death' },
  { nctId: 'NCT06935370', area: 'cardiorenal', note: 'Vicadrostat+empagliflozin vs empa — Boehringer — N=4200 — HFrEF' },
  { nctId: 'NCT02901184', area: 'cardiorenal', note: 'Spironolactone in HFpEF (SPIRRIT) — Uppsala — N=2000' },
  { nctId: 'NCT06024746', area: 'cardiorenal', note: 'Finerenone+SGLT2i early (CONFIRMATION-HF) — N=1500' },
  { nctId: 'NCT05392764', area: 'cardiorenal', note: 'Empagliflozin acute HF — Juntendo — N=444' },
  { nctId: 'NCT07038356', area: 'cardiorenal', note: 'Empagliflozin in ADHF on existing SGLT2i — N=536' },
  { nctId: 'NCT06030843', area: 'cardiorenal', note: 'Empagliflozin cardiorenal syndrome type 1 — N=200' },
  { nctId: 'NCT06217302', area: 'cardiorenal', note: 'Sotagliflozin in T1D + DKD — N=150' },
  { nctId: 'NCT05636176', area: 'cardiorenal', note: 'Ziltivekimab HFpEF CVOT — Novo Nordisk — N=5600 — HF morbidity/mortality' },

  // ── Coronary Artery Disease / ACS ──
  { nctId: 'NCT06494501', area: 'cad', note: 'Inclisiran to prevent CAD — Mount Sinai — N=1600 — plaque regression' },
  { nctId: 'NCT05764057', area: 'cad', note: 'Dapagliflozin post-MI (DAPA-TECTO) — N=450 — LV remodeling' },
  { nctId: 'NCT05360446', area: 'cad', note: 'Inclisiran plaque regression (VICTORION-PLAQUE) — Novartis — N=610' },
  { nctId: 'NCT06174753', area: 'cad', note: 'Dapagliflozin post-STEMI — Ottawa — N=256' },
  { nctId: 'NCT05997693', area: 'cad', note: 'Ticagrelor post-CABG — Cornell — N=700' },
  { nctId: 'NCT07195149', area: 'cad', note: 'Aspirin doses +/- prasugrel post-CABG (OPTIMUS) — N=1703' },
  { nctId: 'NCT05918861', area: 'cad', note: 'Dalcetrapib genetically-guided ACS (dal-GenE 2) — N=2000 — MACE' },
  { nctId: 'NCT06118281', area: 'cad', note: 'Ziltivekimab post-MI (ARTEMIS) — Novo Nordisk — N=10000 — MACE' },

  // ── AF / Arrhythmia ──
  { nctId: 'NCT05757869', area: 'af', note: 'Milvexian vs apixaban in AF (LIBREXIA-AF) — Janssen — N=20284 — stroke/SE' },
  { nctId: 'NCT07187570', area: 'af', note: 'Dapagliflozin AF recurrence after cardioversion (RECUR-AF) — N=1600' },
  { nctId: 'NCT05852704', area: 'af', note: 'Dapagliflozin pre-CABG AF prevention (STENOTYPE) — N=800' },
  { nctId: 'NCT06111443', area: 'af', note: 'Dapagliflozin post-ablation AF (Chang Gung) — N=196' },
  { nctId: 'NCT06499857', area: 'af', note: 'Semaglutide for AF in obesity — U Chicago — N=200' },
  { nctId: 'NCT05712200', area: 'af', note: 'Abelacimab in high-risk AF (LILAC) — Anthos — N=1900 — stroke/SE' },
  { nctId: 'NCT03907046', area: 'af', note: 'Apixaban vs aspirin post-ICH AF — Yale — N=700 — stroke' },
];

// ═══════════════════════════════════════════════════════════════════
// PREDICTION ENGINE — replicates cardiooracle.html exactly
// ═══════════════════════════════════════════════════════════════════

function classifyDrug(interventions) {
  for (const name of (interventions ?? [])) {
    const lower = String(name).toLowerCase().trim();
    // Direct match
    for (const [key, cls] of Object.entries(DRUG_CLASS_MAP)) {
      if (lower.includes(key)) return cls;
    }
  }
  return null;
}

function classifyEndpoint(text) {
  const lower = String(text ?? '').toLowerCase();
  for (const [type, keywords] of ENDPOINT_KEYWORDS) {
    for (const kw of keywords) {
      if (lower.includes(kw)) return type;
    }
  }
  return 'other';
}

function extractPopulationTags(text) {
  const lower = String(text ?? '').toLowerCase();
  const tags = [];
  if (/hfref|hf.{0,30}reduced|reduced.{0,30}ejection|(?:lvef|ef)\s*(?:[<≤]|<=)\s*(?:35|40|45)/.test(lower)) tags.push('HFrEF');
  if (/hfpef|hf.{0,30}preserved|preserved.{0,30}ejection|(?:lvef|ef)\s*(?:[>≥]|>=)\s*(?:40|45|50)/.test(lower)) tags.push('HFpEF');
  if (/diabet|t2dm|type\s*2\s*diabetes/.test(lower)) tags.push('diabetic');
  if (/ckd|chronic kidney|renal impairment|egfr/.test(lower)) tags.push('CKD');
  if (/elder|older adult|age\s*[>≥]\s*65|geriatric/.test(lower)) tags.push('elderly');
  if (/atrial fibrillation|atrial flutter|afib|a-fib|\baf\b/.test(lower)) tags.push('AF');
  return tags;
}

function extractFeatures(data) {
  const study    = data.protocolSection ?? data;
  const design   = study.designModule ?? {};
  const status   = study.statusModule ?? {};
  const sponsor  = study.sponsorCollaboratorsModule ?? {};
  const oversight= study.oversightModule ?? {};
  const contacts = study.contactsLocationsModule ?? {};
  const arms     = (design.armsInterventionsModule ?? study.armsInterventionsModule ?? {}).armGroups ?? [];
  const outcomes = study.outcomesModule ?? {};
  const primary  = (outcomes.primaryOutcomes ?? [])[0] ?? {};
  const interv   = study.armsInterventionsModule ?? {};
  const interventions = interv.interventions ?? [];

  const enrollment = design.enrollmentInfo?.count ?? null;

  let duration = null;
  try {
    const startRaw = status.startDateStruct?.date;
    const endRaw   = status.primaryCompletionDateStruct?.date;
    if (startRaw && endRaw) {
      const startMs = Date.parse(startRaw + (startRaw.length <= 7 ? '-01' : ''));
      const endMs   = Date.parse(endRaw   + (endRaw.length   <= 7 ? '-01' : ''));
      if (!isNaN(startMs) && !isNaN(endMs)) {
        duration = Math.round((endMs - startMs) / (1000 * 60 * 60 * 24 * 30.44));
      }
    }
  } catch (_) {}

  const masking = (design.maskingInfo?.masking ?? '').toUpperCase();
  const double_blind = masking.includes('DOUBLE') || masking.includes('TRIPLE') || masking.includes('QUADRUPLE');
  const placebo_controlled = arms.some(a => (a.type ?? '').toUpperCase().includes('PLACEBO'));
  const is_industry = (sponsor.leadSponsor?.class ?? '').toUpperCase() === 'INDUSTRY';
  const num_sites = (contacts.locations ?? []).length;
  const has_dsmb = !!(oversight.oversightHasDmc);

  const endpointText = (primary.measure ?? '') + ' ' + (primary.description ?? '');
  const endpoint_type = classifyEndpoint(endpointText);

  const drugNames = interventions.map(i => i.name ?? '').filter(Boolean);
  const drug_class = classifyDrug(drugNames);

  let comparator_type = 'placebo';
  if (arms.some(a => (a.type ?? '').toUpperCase().includes('ACTIVE_COMPARATOR'))) {
    comparator_type = 'active';
  }

  const eligModule = study.eligibilityModule ?? {};
  const condText = (study.conditionsModule?.conditions ?? []).join(' ');
  const eligText = eligModule.eligibilityCriteria ?? '';
  const population_tags = extractPopulationTags(condText + ' ' + eligText);

  let year = null;
  try {
    const raw = status.startDateStruct?.date ?? '';
    const y = parseInt(raw.slice(0, 4), 10);
    if (!isNaN(y) && y > 1990) year = y;
  } catch (_) {}

  const title = study.identificationModule?.briefTitle ?? '';

  return {
    enrollment, duration, placebo_controlled, double_blind,
    is_industry, num_sites, endpoint_type, drug_class,
    has_dsmb, comparator_type, population_tags, year, title,
    _interventionNames: drugNames
  };
}

function metaRegressionPredict(features) {
  const epType = features.endpoint_type ?? 'other';
  const dClass = features.drug_class ?? '';

  const vec = [
    Math.log(Math.max(1, features.enrollment ?? 1000)),
    features.duration ?? 36,
    features.placebo_controlled ? 1 : 0,
    features.double_blind ? 1 : 0,
    features.is_industry ? 1 : 0,
    Math.log(Math.max(1, features.num_sites ?? 100)),
    epType === 'mace'      ? 1 : 0,
    epType === 'mortality' ? 1 : 0,
    epType === 'hf'        ? 1 : 0,
    epType === 'renal'     ? 1 : 0,
    epType === 'surrogate' ? 1 : 0,
    dClass === 'sglt2i'    ? 1 : 0,
    (dClass === 'mra' || dClass === 'ns_mra') ? 1 : 0,
    dClass === 'glp1ra'    ? 1 : 0,
    dClass === 'pcsk9i'    ? 1 : 0,
    dClass === 'statin'    ? 1 : 0,
    features.has_dsmb ? 1 : 0,
    features.comparator_type === 'active' ? 1 : 0
  ];

  const featureNames = [
    'enrollment_log', 'duration_months', 'placebo_controlled', 'double_blind',
    'is_industry', 'num_sites_log', 'endpoint_mace', 'endpoint_mortality',
    'endpoint_hf', 'endpoint_renal', 'endpoint_surrogate',
    'drug_sglt2i', 'drug_mra_ns', 'drug_glp1ra', 'drug_pcsk9i',
    'drug_statin', 'has_dsmb', 'comparator_active'
  ];

  let logit = MODEL_COEFFICIENTS.intercept;
  const contributions = {};
  featureNames.forEach((name, i) => {
    const coeff = MODEL_COEFFICIENTS[name] ?? 0;
    const contrib = coeff * vec[i];
    logit += contrib;
    contributions[name] = +contrib.toFixed(4);
  });

  const p = 1 / (1 + Math.exp(-logit));
  return { p: +p.toFixed(4), logit: +logit.toFixed(4), contributions };
}

function normalCDF(x) {
  const a1 =  0.254829592, a2 = -0.284496736, a3 = 1.421413741;
  const a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x) / Math.SQRT2;
  const t = 1.0 / (1.0 + p * x);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  return 0.5 * (1.0 + sign * y);
}

function conditionalPower(features, classSuccessRate) {
  const endpointType = features.endpoint_type ?? 'mace';
  const enrollment = features.enrollment ?? 5000;
  const events = enrollment * 0.7;
  let power = 0.5;
  let estimated_hr = null;

  if (endpointType === 'surrogate') {
    const estimatedSMD = 0.1 + 0.4 * classSuccessRate;
    const n = enrollment / 2;
    const lambda = estimatedSMD * Math.sqrt(n / 2);
    power = normalCDF(lambda - 1.96) + normalCDF(-lambda - 1.96);
    estimated_hr = estimatedSMD;
  } else {
    estimated_hr = Math.exp(-0.05 - 0.25 * classSuccessRate);
    const logHR = Math.log(estimated_hr);
    const z = Math.abs(logHR) * Math.sqrt(events) / 2;
    power = normalCDF(z - 1.96) + normalCDF(-z - 1.96);
  }

  return { power: Math.max(0, Math.min(1, +power.toFixed(4))), estimated_hr: +estimated_hr.toFixed(4) };
}

function bayesianPrior(drugClass) {
  const prior = CLASS_PRIORS[drugClass] ?? CLASS_PRIORS.other;
  const p = prior.alpha / (prior.alpha + prior.beta);
  return { p: +p.toFixed(4), alpha: prior.alpha, beta: prior.beta, source: 'class_prior' };
}

function ensemblePredict(bayesian, power, regression) {
  let wB = ENSEMBLE_W.bayesian;
  let wP = ENSEMBLE_W.conditional_power;
  let wR = ENSEMBLE_W.meta_regression;

  const total = wB + wP + wR;
  const p = (wB * bayesian.p + wP * power.power + wR * regression.p) / total;

  let level;
  if (p > 0.6)      level = 'high';
  else if (p >= 0.3) level = 'moderate';
  else               level = 'low';

  return { p_success: +(p * 100).toFixed(1) / 100, level, components: { bayesian: bayesian.p, power: power.power, regression: regression.p } };
}

// ═══════════════════════════════════════════════════════════════════
// CT.GOV API FETCH
// ═══════════════════════════════════════════════════════════════════

function fetchTrial(nctId) {
  return new Promise((resolve, reject) => {
    const url = `https://clinicaltrials.gov/api/v2/studies/${nctId}`;
    https.get(url, { headers: { 'Accept': 'application/json' } }, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode} for ${nctId}`));
        res.resume();
        return;
      }
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(body)); }
        catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

// ═══════════════════════════════════════════════════════════════════
// MAIN — BATCH PREDICTIONS
// ═══════════════════════════════════════════════════════════════════

async function main() {
  const now = new Date();
  const dateStamp = now.toISOString().slice(0, 10).replace(/-/g, '');

  console.log('CardioOracle Prospective Validation — Batch Predictions');
  console.log('='.repeat(60));
  console.log(`Timestamp: ${now.toISOString()}`);
  console.log(`Trials: ${TARGET_TRIALS.length}`);
  console.log('');

  const results = {
    type: 'CardioOracle Prospective Validation Cohort',
    version: '1.0.0',
    generated: now.toISOString(),
    model_source: 'cardiooracle.html (same coefficients, classifiers, ensemble weights)',
    ensemble_weights: ENSEMBLE_W,
    coefficients: MODEL_COEFFICIENTS,
    purpose: 'Timestamped predictions for currently recruiting Phase 3 CV trials. Compare against actual outcomes when trials report (2026-2031).',
    trials: []
  };

  let successCount = 0;
  let failCount = 0;

  for (const target of TARGET_TRIALS) {
    process.stdout.write(`  ${target.nctId} ... `);

    try {
      // Fetch from CT.gov
      const ctgovData = await fetchTrial(target.nctId);

      // Extract features (same logic as HTML app)
      const features = extractFeatures(ctgovData);

      // Run all 3 prediction components
      const drugClass = features.drug_class ?? 'other';
      const bays = bayesianPrior(drugClass);
      const classRate = bays.p;
      const pwr = conditionalPower(features, classRate);
      const reg = metaRegressionPredict(features);
      const ens = ensemblePredict(bays, pwr, reg);

      const record = {
        nct_id: target.nctId,
        area: target.area,
        note: target.note,
        title: features.title,
        features: {
          enrollment: features.enrollment,
          duration_months: features.duration,
          drug_class: features.drug_class,
          endpoint_type: features.endpoint_type,
          comparator_type: features.comparator_type,
          double_blind: features.double_blind,
          placebo_controlled: features.placebo_controlled,
          is_industry: features.is_industry,
          num_sites: features.num_sites,
          has_dsmb: features.has_dsmb,
          population_tags: features.population_tags,
          year: features.year,
          interventions: features._interventionNames
        },
        prediction: {
          p_success: ens.p_success,
          level: ens.level,
          components: ens.components
        },
        meta_regression_detail: {
          logit: reg.logit,
          top_contributors: Object.entries(reg.contributions)
            .filter(([, v]) => Math.abs(v) > 0.01)
            .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
            .slice(0, 5)
            .map(([k, v]) => ({ feature: k, contribution: v }))
        },
        conditional_power_detail: {
          power: pwr.power,
          estimated_effect: pwr.estimated_hr
        },
        bayesian_detail: {
          class_prior_p: bays.p,
          alpha: bays.alpha,
          beta: bays.beta,
          note: `Class-level prior for ${drugClass} based on historical trial success rates`
        },
        outcome: null,  // TO BE FILLED when trial reports
        outcome_date: null,
        outcome_source: null
      };

      results.trials.push(record);
      successCount++;

      const pct = (ens.p_success * 100).toFixed(1);
      const arrow = ens.level === 'high' ? '+' : ens.level === 'low' ? '-' : '~';
      console.log(`${arrow} P(success)=${pct}% [${ens.level}]  (${features.drug_class ?? 'unknown'} | ${features.endpoint_type})`);

      // Rate limit: 200ms between requests
      await new Promise(r => setTimeout(r, 200));

    } catch (err) {
      console.log(`FAILED: ${err.message}`);
      failCount++;
      results.trials.push({
        nct_id: target.nctId,
        area: target.area,
        note: target.note,
        error: err.message,
        outcome: null
      });
    }
  }

  // Summary stats
  const predictions = results.trials.filter(t => t.prediction);
  const highCount = predictions.filter(t => t.prediction.level === 'high').length;
  const modCount  = predictions.filter(t => t.prediction.level === 'moderate').length;
  const lowCount  = predictions.filter(t => t.prediction.level === 'low').length;
  const avgP = predictions.length > 0
    ? predictions.reduce((s, t) => s + t.prediction.p_success, 0) / predictions.length
    : 0;

  results.summary = {
    total_trials: TARGET_TRIALS.length,
    successful_predictions: successCount,
    failed_fetches: failCount,
    high_confidence: highCount,
    moderate_confidence: modCount,
    low_confidence: lowCount,
    mean_p_success: +avgP.toFixed(4)
  };

  // Write output
  const outFile = `prospective_predictions_${dateStamp}.json`;
  fs.writeFileSync(outFile, JSON.stringify(results, null, 2));

  console.log('');
  console.log('='.repeat(60));
  console.log(`Predictions: ${successCount}/${TARGET_TRIALS.length} successful`);
  console.log(`High: ${highCount}  |  Moderate: ${modCount}  |  Low: ${lowCount}`);
  console.log(`Mean P(success): ${(avgP * 100).toFixed(1)}%`);
  console.log(`Output: ${outFile}`);
  console.log('');
  console.log('Next step: When trials report results, fill in outcome/outcome_date fields');
  console.log('and compute calibration metrics (Brier, AUC, calibration slope).');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

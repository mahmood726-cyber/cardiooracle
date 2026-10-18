'use strict';
// Research-stage audit of the ORIGINAL deployed browser storage contract.
// This test intentionally demonstrates historical data-loss behaviour.
// It does not alter or certify the published predictor or frozen forecasts.
const test = require('node:test');
const assert = require('node:assert/strict');
const cp = require('node:child_process');
const PIN = 'e35c349d269743cc7cd7f8bc199e09470807fe86';
const HTML_BLOB = 'a52f055dae8c5f672b9d8498f7e79e966458e414';
const htmlBytes = cp.execFileSync('git', ['show', PIN + ':CardioOracle.html'],
  { maxBuffer: 16 * 1024 * 1024, timeout: 20000 });
const blob = cp.execFileSync('git', ['hash-object', '--stdin'],
  { input: htmlBytes, timeout: 20000 }).toString().trim();
assert.equal(blob, HTML_BLOB, 'live-source audit must use the pinned HTML blob');
const html = htmlBytes.toString('utf8');
function sourceBetween(start, end) {
  const i = html.indexOf(start);
  const j = html.indexOf(end, i + start.length);
  assert.ok(i >= 0 && j > i, 'cannot inspect original function: ' + start);
  return html.slice(i, j);
}
const seedMatch = html.match(/const SEED_PREDICTIONS\s*=\s*(\[[\s\S]*?\]);\s*\/\/ === HASH CHAIN ENGINE ===/);
assert.ok(seedMatch, 'original 25-case seed source must be inspectable');
const seeds = JSON.parse(seedMatch[1]);
assert.equal(seeds.length, 25);
const storage = sourceBetween('function pvLoad(key)', '// === SEED ON FIRST LOAD ===');
const seed = sourceBetween('async function pvSeedIfNeeded()', '// === PREDICT AND LOCK ===');
const lock = sourceBetween('async function pvPredictAndLock(', '// === MANUAL ADD ===');
const resolution = sourceBetween('async function pvConfirmResolution(', '// ── Timeline Chart');
const source = [storage, seed, lock, resolution].join('\n');
assert.match(storage, /catch \(e\) \{ console\.warn\('PV localStorage save failed:/);
const KEYS = {
  cohort: 'cardiooracle_pv_cohort',
  resolutions: 'cardiooracle_pv_resolutions',
  queue: 'cardiooracle_pv_queue',
  seeded: 'cardiooracle_pv_seeded'
};
function limitedStorage(quota) {
  const items = new Map();
  return {
    quota,
    failures: [],
    getItem(key) { return items.has(key) ? items.get(key) : null; },
    setItem(key, value) {
      const data = String(value);
      if (data.length > this.quota) {
        this.failures.push(key);
        const err = new Error('QuotaExceededError');
        err.name = 'QuotaExceededError';
        throw err;
      }
      items.set(key, data);
    }
  };
}
function machine(localStorage) {
  const messages = [];
  const impl = new Function('localStorage', 'PV_KEYS', 'TRAINING_DATA',
    'SEED_PREDICTIONS', 'PV_MODEL_VERSION', 'sha256Hex', 'pvComputeEntryHash',
    'pvComputeResolutionHash', 'extractFeatures', 'computeSimilarity',
    'bayesianBorrowing', 'conditionalPower', 'metaRegressionPredict',
    'ensemblePredict', 'pvShowStatus', 'pvUpdateResolveQueue',
    'pvRenderCohortTable', 'pvRenderDashboard', 'console',
    source + '\nreturn {pvSeedIfNeeded,pvPredictAndLock,pvConfirmResolution,pvGetCohort,pvGetResolutions,pvSaveCohort};');
  const api = impl(localStorage, KEYS, { trials: [{ success: 1 }] },
    seeds, 'cardiooracle_v1.0',
    async (data) => 'MOCK_SHA_' + String(data).length,
    async (entry) => 'MOCK_ENTRY_' + entry.nct_id,
    async () => 'MOCK_RESOLUTION',
    () => ({ title: 'Synthetic', drug_class: 'sglt2i', endpoint_type: 'mortality',
      enrollment: 100, duration: 12 }),
    () => 0.7,
    () => ({ p: 0.66 }),
    () => ({ power: 0.66 }),
    () => ({ p: 0.66 }),
    () => ({ p: 0.66, levelLabel: 'moderate' }),
    (_id, text) => messages.push(text), () => {}, () => {}, () => {},
    { warn() {} });
  return { ...api, messages };
}
test('positive control: original 25 frozen predictions persist if writes succeed', async () => {
  const s = limitedStorage(1e7);
  const m = machine(s);
  await m.pvSeedIfNeeded();
  assert.equal(m.pvGetCohort().length, 25);
  assert.equal(s.getItem(KEYS.seeded), '1');
  assert.equal(m.pvGetCohort()[0].nct_id, seeds[0].nct_id);
});
test('large failed cohort write followed by small seeded flag loses all 25 forecasts', async () => {
  for (const quota of [1, 2, 10, 50, 100, 250, 500]) {
    const s = limitedStorage(quota);
    const m = machine(s);
    await m.pvSeedIfNeeded();
    assert.equal(s.getItem(KEYS.seeded), '1');
    assert.equal(m.pvGetCohort().length, 0);
    assert.ok(s.failures.includes(KEYS.cohort));
    s.quota = 1e7;
    await m.pvSeedIfNeeded();
    assert.equal(m.pvGetCohort().length, 0, 'seed flag blocks recovery');
  }
});
test('original prediction operation returns a locked entry after failed save', async () => {
  for (const quota of [1, 5, 20, 100, 200]) {
    const s = limitedStorage(quota);
    const m = machine(s);
    const entry = await m.pvPredictAndLock({
      protocolSection: { identificationModule: { nctId: 'NCT12345678' },
        designModule: { phases: ['PHASE3'] } }
    }, 'cardiorenal');
    assert.equal(entry.nct_id, 'NCT12345678');
    assert.equal(m.pvGetCohort().length, 0);
    assert.ok(s.failures.includes(KEYS.cohort));
  }
});
test('original manual resolution confirms SUCCESS although write failed', async () => {
  for (const quota of [1, 10, 25, 70, 100]) {
    const s = limitedStorage(1e7);
    const m = machine(s);
    m.pvSaveCohort([{ nct_id: 'NCT12345678', entry_hash: 'HASH',
      prediction: { p_ensemble: 0.66 }, trial_snapshot: {} }]);
    s.quota = quota;
    const inputs = {
      '.pv-resolve-outcome': 'SUCCESS', '.pv-resolve-pval': '0.001',
      '.pv-resolve-effect': '0.83', '.pv-resolve-ci-lo': '0.74',
      '.pv-resolve-ci-hi': '0.94', '.pv-resolve-doi': '10.1000/example',
      '.pv-resolve-notes': 'primary outcome'
    };
    await m.pvConfirmResolution('NCT12345678',
      { querySelector: (key) => ({ value: inputs[key] ?? '' }) });
    assert.equal(m.pvGetResolutions().length, 0);
    assert.ok(s.failures.includes(KEYS.resolutions));
    assert.ok(m.messages.includes('NCT12345678 resolved as SUCCESS.'));
  }
});
// Mocked hashing isolates persistence behaviour; this is not a
// genuine browser/WebCrypto end-to-end test or clinical validation.
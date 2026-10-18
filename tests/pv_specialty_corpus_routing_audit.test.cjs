'use strict';
// Research-stage audit witness only: not a repair, nor a clinical validation claim.
const test = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { createHash } = require('node:crypto');
const MASTER = 'e35c349d269743cc7cd7f8bc199e09470807fe86';
const HTML_BLOB = 'a52f055dae8c5f672b9d8498f7e79e966458e414';
const html = execFileSync('git', ['show', MASTER + ':CardioOracle.html'], {
  encoding: 'utf8', maxBuffer: 8 * 1024 * 1024
});
const blob = createHash('sha1').update('blob ' + Buffer.byteLength(html) + '\0').update(html).digest('hex');

function declaration(name) {
  const i = html.indexOf('const ' + name + ' = ');
  assert.ok(i >= 0, name + ' must exist in audited source');
  const start = html.indexOf('{', i);
  let depth = 0, quote = '', escape = false;
  for (let j = start; j < html.length; j++) {
    const c = html[j];
    if (quote) {
      if (escape) escape = false;
      else if (c === '\\') escape = true;
      else if (c === quote) quote = '';
      continue;
    }
    if (c === '{' || c === '}' || c === '"' || c === "'" || c.charCodeAt(0) === 96) {
      if (c === '"' || c === "'" || c.charCodeAt(0) === 96) { quote = c; continue; }
    }
    if (c === '{') depth++;
    else if (c === '}' && --depth === 0) return html.slice(i, j + 2);
  }
  throw new Error('Unclosed source declaration: ' + name);
}

function functionSource(name) {
  const i = html.indexOf('function ' + name + '(');
  assert.ok(i >= 0, name + ' must exist in audited source');
  const start = html.indexOf('{', i);
  let depth = 0, quote = '', escape = false, comment = 0;
  for (let j = start; j < html.length; j++) {
    const c = html[j], next = html[j + 1];
    if (comment === 1) { if (c === '\n') comment = 0; continue; }
    if (comment === 2) { if (c === '*' && next === '/') { comment = 0; j++; } continue; }
    if (quote) {
      if (escape) escape = false;
      else if (c === '\\') escape = true;
      else if (c === quote) quote = '';
      continue;
    }
    if (c === '/' && next === '/') { comment = 1; j++; continue; }
    if (c === '/' && next === '*') { comment = 2; j++; continue; }
    if (c === '"' || c === "'" || c.charCodeAt(0) === 96) { quote = c; continue; }
    if (c === '{') depth++;
    else if (c === '}' && --depth === 0) return html.slice(i, j + 1);
  }
  throw new Error('Unclosed source function: ' + name);
}

const datasets = declaration('DATA_LIBRARY') + '\n' + declaration('CONFIG_LIBRARY');
const dataLibrary = new Function(datasets + '\nreturn DATA_LIBRARY;')();
const originalFns = [
  'normalCDF', 'normalQuantile', 'zAlpha', 'computeSimilarity',
  'bayesianBorrowing', 'conditionalPower', 'metaRegressionPredict', 'ensemblePredict'
].map(functionSource).join('\n') + '\nasync ' + functionSource('pvPredictAndLock');

// Browser I/O and API feature parsing are stubs; all original embedded training
// records, models, similarity, Bayesian, power, regression, ensemble and forecast
// locking come from the source-pinned historical HTML.
const context = datasets + '\nreturn async function(activeConfig, target, area, nctId) {\n' +
  'const TRAINING_DATA=DATA_LIBRARY[activeConfig].training;\n' +
  'const MODEL=DATA_LIBRARY[activeConfig].model;\n' +
  'const CONFIG=CONFIG_LIBRARY[activeConfig];\n' +
  "const PV_MODEL_VERSION='cardiooracle_v1.0';\n" +
  declaration('BROAD_MECH_JS') + '\n' +
  "const HARD_ENDPOINT_TYPES=new Set(['mace','mortality','hf','renal']);\n" +
  'function extractFeatures(x){return x._testFeatures;}\n' +
  "async function sha256Hex(x){return createHash('sha256').update(x).digest('hex');}\n" +
  'function pvGetCohort(){return [];}\nfunction pvSaveCohort(x){}\n' +
  'async function pvComputeEntryHash(e,p){return sha256Hex(e.nct_id+e.prediction.p_ensemble);}\n' +
  originalFns + '\n' +
  "const entry=await pvPredictAndLock({protocolSection:{identificationModule:{nctId},designModule:{phases:['PHASE3']}},_testFeatures:target},area);\n" +
  'return {entry,activeConfig,nTraining:TRAINING_DATA.trials.length,corpusId:TRAINING_DATA.config_id};\n}';
const forecast = new Function('createHash', context)(createHash);

test('pins the source and all three embedded specialty corpora', () => {
  assert.equal(blob, HTML_BLOB);
  assert.equal(dataLibrary.cardiorenal.training.trials.length, 784);
  assert.equal(dataLibrary.cad.training.trials.length, 90);
  assert.equal(dataLibrary.af.training.trials.length, 28);
  assert.match(functionSource('pvApproveFromQueue'), /pvPredictAndLock\(ctgovData, item\.area/);
});

test('passing another clinical area changes the label but NOT the active model', async () => {
  for (const area of ['cad', 'af']) {
    for (const row of dataLibrary[area].training.trials.slice(0, 12)) {
      const nct = 'NCT90000000';
      const labelled = await forecast('cardiorenal', row.features, area, nct);
      const relabelled = await forecast('cardiorenal', row.features, 'cardiorenal', nct);
      assert.equal(labelled.entry.trial_snapshot.area, area);
      assert.equal(labelled.nTraining, 784);
      assert.equal(labelled.corpusId, 'cardiorenal');
      assert.equal(labelled.entry.prediction.p_ensemble, relabelled.entry.prediction.p_ensemble);
      assert.equal(labelled.entry.training_hash, relabelled.entry.training_hash);
    }
  }
});

test('embedded CAD and AF feature profiles expose material model-configuration differences', async () => {
  for (const area of ['cad', 'af']) {
    const rows = dataLibrary[area].training.trials;
    const differences = [];
    for (let i = 0; i < rows.length; i++) {
      const nct = 'NCT' + String(90000000 + i);
      const defaultPage = await forecast('cardiorenal', rows[i].features, area, nct);
      const specialtyPage = await forecast(area, rows[i].features, area, nct);
      assert.equal(defaultPage.entry.trial_snapshot.area, area);
      assert.equal(defaultPage.nTraining, 784);
      assert.equal(specialtyPage.nTraining, rows.length);
      assert.notEqual(defaultPage.entry.training_hash, specialtyPage.entry.training_hash);
      const delta = Math.abs(defaultPage.entry.prediction.p_ensemble -
                             specialtyPage.entry.prediction.p_ensemble);
      assert.ok(Number.isFinite(delta));
      differences.push(delta);
    }
    differences.sort((a, b) => a - b);
    const n = differences.length;
    const median = n % 2 ? differences[(n - 1) / 2] :
      (differences[n / 2 - 1] + differences[n / 2]) / 2;
    // Audit witness thresholds, not a clinical performance requirement.
    assert.ok(differences.every(d => d > 1e-12));
    assert.ok(median > 0.04);
    assert.ok(differences[n - 1] > 0.20);
  }
});

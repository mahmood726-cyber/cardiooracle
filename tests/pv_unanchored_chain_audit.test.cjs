'use strict';
// Historical, research-only audit: the browser's public SHA-256 chain is not
// independently anchored or signed and cannot prove the timing of forecasts.
// The 2026-03-25 archived 25-trial record and deployed app remain unchanged.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const crypto = require('node:crypto');
const BASE = 'e35c349d269743cc7cd7f8bc199e09470807fe86';
const EXPECTED_HTML = 'a52f055dae8c5f672b9d8498f7e79e966458e414';
const clone = x => JSON.parse(JSON.stringify(x));
const sha256Hex = async s => crypto.createHash('sha256').update(s, 'utf8').digest('hex');

function extractFn(src, name) {
  const i = src.indexOf('function ' + name + '(');
  assert.ok(i >= 0, 'missing original function ' + name);
  const start = src.slice(i - 6, i) === 'async ' ? i - 6 : i;
  const b = src.indexOf('{', i);
  let depth = 0;
  for (let j = b; j < src.length; j++) {
    if (src[j] === '{') depth++;
    if (src[j] === '}' && --depth === 0) return src.slice(start, j + 1);
  }
  throw new Error('unclosed source function ' + name);
}
function extractConst(src, declaration, close) {
  const i = src.indexOf(declaration);
  assert.ok(i >= 0, 'missing original ' + declaration);
  const end = src.indexOf(close, i);
  assert.ok(end >= 0);
  return src.slice(i, end + close.length);
}
function sourceHarness() {
  const sha = execFileSync('git', ['rev-parse', BASE + ':CardioOracle.html'], { encoding: 'utf8' }).trim();
  assert.equal(sha, EXPECTED_HTML, 'unexpected published HTML Git blob');
  const src = execFileSync('git', ['show', BASE + ':CardioOracle.html'], {
    encoding: 'utf8', maxBuffer: 8 * 1024 * 1024
  });
  const funcs = ['pvComputeEntryHash', 'pvComputeResolutionHash', 'pvVerifyChain',
    'pvVerifyResolutions', 'pvLoad', 'pvSave', 'pvGetCohort', 'pvSaveCohort',
    'pvGetResolutions', 'pvSaveResolutions', 'pvSeedIfNeeded'];
  const body = extractConst(src, 'const PV_KEYS = {', '};') + '\n' +
    "const PV_MODEL_VERSION = 'cardiooracle_v1.0';\n" +
    extractConst(src, 'const SEED_PREDICTIONS = [', '];') + '\n' +
    funcs.map(n => extractFn(src, n)).join('\n') + '\n' +
    'return {' + funcs.join(',') + '};';
  const storage = new Map();
  const localStorage = {
    getItem: k => storage.get(k) ?? null,
    setItem: (k, v) => storage.set(k, String(v))
  };
  return new Function('sha256Hex', 'localStorage', 'TRAINING_DATA', body)(
    sha256Hex, localStorage, { trials: [] });
}
let pv, original;
test('original published functions seed an intact chain of 25 forecasts', async () => {
  pv = sourceHarness();
  await pv.pvSeedIfNeeded();
  original = pv.pvGetCohort();
  assert.equal(original.length, 25);
  assert.equal(original[0].nct_id, 'NCT06307652');
  assert.equal((await pv.pvVerifyChain(original)).valid, true);
});
test('unrehashed tampering is detected; public SHA-256 rehash passes, unlike external anchor', async () => {
  const originalJson = JSON.stringify(original);
  const publishedHead = original[24].entry_hash;
  for (let pivot = 0; pivot < 25; pivot++) {
    const candidate = clone(original);
    candidate[pivot].prediction.p_ensemble += 0.025;
    const detected = await pv.pvVerifyChain(candidate);
    assert.equal(detected.valid, false);
    assert.equal(detected.brokenAt, pivot);
    for (let j = pivot; j < candidate.length; j++) {
      const prev = j ? candidate[j - 1].entry_hash : null;
      candidate[j].prev_hash = prev;
      candidate[j].entry_hash = await pv.pvComputeEntryHash(candidate[j], prev);
    }
    assert.equal((await pv.pvVerifyChain(candidate)).valid, true);
    assert.notEqual(candidate[24].entry_hash, publishedHead);
  }
  assert.equal(JSON.stringify(original), originalJson, 'must not mutate original 25');
});
test('recomputed chain accepts an arbitrarily backdated forecast timestamp', async () => {
  const x = clone(original);
  x[0].locked_at = '2025-01-01T00:00:00.000Z';
  for (let j = 0; j < x.length; j++) {
    const prev = j ? x[j - 1].entry_hash : null;
    x[j].prev_hash = prev;
    x[j].entry_hash = await pv.pvComputeEntryHash(x[j], prev);
  }
  assert.equal((await pv.pvVerifyChain(x)).valid, true);
  assert.notEqual(x[24].entry_hash, original[24].entry_hash);
});
test('individually hashed outcome labels can also be rewritten and rehashed', async () => {
  const resolution = {
    nct_id: original[0].nct_id, resolved_at: '2026-10-18T09:00:00.000Z',
    outcome: 'FAILURE', evidence: { p_value: 0.61, hr: 1.05 },
    prediction_entry_hash: original[0].entry_hash, resolution_hash: ''
  };
  resolution.resolution_hash = await pv.pvComputeResolutionHash(resolution);
  assert.equal((await pv.pvVerifyResolutions([resolution])).valid, true);
  const changed = clone(resolution);
  changed.outcome = 'SUCCESS';
  assert.equal((await pv.pvVerifyResolutions([changed])).valid, false);
  changed.resolution_hash = await pv.pvComputeResolutionHash(changed);
  assert.equal((await pv.pvVerifyResolutions([changed])).valid, true);
});
'use strict';
// Historical source-identity audit, not a clinical model or a forecast generator.
// This tests the immutable 2026-03-25 evidence using a full Git checkout.
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const SOURCES = Object.freeze({
  generator: ['88bf686c44fade0021350f0ddcc26bf74fdf4071','prospective_predictions.js','2ab83151e20a8555620c970e8bfb67b2adbedede'],
  browser: ['caeeb15d6bbca31a4206295a159e3070da8de474','CardioOracle.html','a48255e49a39c45b107a7d5ee1a7e9ab815d7218'],
  archive: ['88bf686c44fade0021350f0ddcc26bf74fdf4071','prospective_predictions_20260325.json','d61e874de348d8840317417848b51514ae272c8f']
});
function historical(name) {
  const [commit,path,expected] = SOURCES[name];
  const bytes = cp.execFileSync('git',['show',commit+':'+path],{
    stdio:['ignore','pipe','pipe'],timeout:20000,maxBuffer:16*1024*1024
  });
  const sha=crypto.createHash('sha1').update(Buffer.from('blob '+bytes.length+'\0'))
    .update(bytes).digest('hex');
  assert.equal(sha,expected,'immutable historical source changed: '+name);
  return bytes.toString('utf8');
}
function generatorCoefficients(text) {
  const match=text.match(/const MODEL_COEFFICIENTS\s*=\s*\{([\s\S]*?)\};/);
  assert.ok(match,'generator fixed coefficient schema must be inspectable');
  const pairs=Array.from(match[1].matchAll(/([a-z0-9_]+)\s*:\s*(-?\d+(?:\.\d+)?)/g));
  assert.equal(pairs.length,19);
  return Object.fromEntries(pairs.map(m=>[m[1],Number(m[2])]));
}
function browserCoefficients(html) {
  assert.ok(html.includes("const key = params.get('config') ?? 'cardiorenal'"));
  assert.ok(html.includes('const MODEL = DATA_LIBRARY[window._configKey].model'));
  assert.ok(html.includes('const coeff = coeffs[name] ?? 0'));
  const match=html.match(/cardiorenal:\s*\{\s*training:[\s\S]*?model:\s*\{"coefficients":\s*(\{[^}]*\})/);
  assert.ok(match,'default cardiorenal fitted model must be present');
  const coefficients=JSON.parse(match[1]);
  assert.equal(Object.keys(coefficients).length,19);
  return coefficients;
}
test('frozen March 2026 archive is pinned and remains immutable',()=>{
  const archive=JSON.parse(historical('archive'));
  assert.equal(archive.trials.length,25);
});
test('historical generator and browser used different selected regression models',()=>{
  const generator=historical('generator');
  const browser=historical('browser');
  const fixed=generatorCoefficients(generator);
  const fitted=browserCoefficients(browser);
  const oldKeys=new Set(Object.keys(fixed).filter(k=>k!=='intercept'));
  const browserKeys=new Set(Object.keys(fitted).filter(k=>k!=='intercept'));
  const absent=[...oldKeys].filter(k=>!browserKeys.has(k));
  assert.equal(absent.length,13,'documented missing coefficient-key count changed');
  assert.equal(fixed.is_industry,-0.08);
  assert.ok(fitted.is_industry>1.3 && fitted.is_industry<1.4);
  assert.equal(fixed.has_dsmb,0.15);
  assert.ok(fitted.has_dsmb<-.58 && fitted.has_dsmb>-.60);
  assert.notDeepEqual(fixed,fitted);
  assert.match(generator,/EXACT same meta-regression/i);
});
test('historical Bayesian algorithms were not identical',()=>{
  const generator=historical('generator');
  const browser=historical('browser');
  assert.match(generator,/const CLASS_PRIORS\s*=\s*\{/);
  assert.match(generator,/function bayesianPrior\(drugClass\)/);
  assert.match(browser,/function bayesianBorrowing\(/);
  assert.match(browser,/function computeSimilarity\(/);
  assert.match(browser,/const MODEL = DATA_LIBRARY\[window\._configKey\]\.model/);
});
// Tests documenting divergence do NOT certify either implementation's
// predictive accuracy, training labels, as-of source vintages or outcomes.

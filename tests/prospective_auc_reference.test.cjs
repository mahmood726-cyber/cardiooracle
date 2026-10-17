'use strict';
// Research-stage audit, not a deployed clinical model or outcome validation.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const cp = require('node:child_process');
const crypto = require('node:crypto');
const vm = require('node:vm');
const { tieAwareAuc } = require('../audit/prospective_auc_reference.cjs');

function pairwiseOracle(y, p) {
  const positive = y.flatMap((label, i) => label === 1 ? [p[i]] : []);
  const negative = y.flatMap((label, i) => label === 0 ? [p[i]] : []);
  if (!positive.length || !negative.length) return null;
  let wins = 0;
  for (const a of positive) for (const b of negative) {
    wins += a > b ? 1 : a === b ? 0.5 : 0;
  }
  return wins / (positive.length * negative.length);
}
function consistent(y, p) {
  const expected = pairwiseOracle(y, p);
  const result = tieAwareAuc(y, p);
  if (expected === null) { assert.equal(result, null); return; }
  assert.ok(Math.abs(result.auc - expected) < 1e-12,
    'tied ROC trapezoid must agree with independently paired Mann-Whitney AUC');
  assert.equal(result.roc[0].fpr, 0);
  assert.equal(result.roc[0].tpr, 0);
  assert.equal(result.roc.at(-1).fpr, 1);
  assert.equal(result.roc.at(-1).tpr, 1);
}
test('identical predictions always receive tie-correct AUC 0.5 regardless of row order', () => {
  for (const labels of [[1,1,0,0,0],[0,0,0,1,1],[1,0,1,0,0]]) {
    consistent(labels,[0.5,0.5,0.5,0.5,0.5]);
    assert.equal(tieAwareAuc(labels,Array(5).fill(0.5)).auc,0.5);
  }
});
test('perfect, reversed, partially tied and degenerate cases', () => {
  for (const [y,p] of [
    [[0,0,1,1],[0.1,0.2,0.8,0.9]],
    [[0,0,1,1],[0.8,0.9,0.1,0.2]],
    [[1,0,1,0],[0.5,0.5,0.75,0.25]],
    [[1,0],[0,1]], [[1,0],[1,0]], [[1,1,1],[0.1,0.5,0.9]],
    [[0,0],[0.1,0.9]]
  ]) consistent(y,p);
  assert.equal(tieAwareAuc([1],[0.5]),null);
});
test('reject malformed inputs rather than silently reporting a clinical statistic', () => {
  assert.throws(() => tieAwareAuc([1,0],[0.5]),TypeError);
  for (const p of [NaN,Infinity,-0.1,1.1,'0.5']) {
    assert.throws(() => tieAwareAuc([1,0],[p,0.2]),RangeError);
  }
  assert.throws(() => tieAwareAuc([1,2],[0.2,0.3]),RangeError);
});
test('seeded 400 diverse tie-heavy cohorts and reversals match independent pairwise oracle', () => {
  let state=0x27ac0917;
  function next() { state=(Math.imul(state,1664525)+1013904223)>>>0; return state; }
  for(let k=0;k<400;k++) {
    const n=2+(next()%19), y=[],p=[];
    for(let i=0;i<n;i++) { y.push(next()%2); p.push((next()%5)/4); }
    // Ensure both outcome classes, without using a probabilistic test pass.
    y[0]=0; y[1]=1;
    consistent(y,p);
    consistent([...y].reverse(),[...p].reverse());
  }
});
test('source-pinned deployed JS demonstrates original tie/order defect without modifying HTML', () => {
  const ref='e35c349d269743cc7cd7f8bc199e09470807fe86';
  const html=cp.execFileSync('git',['show',ref+':CardioOracle.html'],{
    stdio:['ignore','pipe','pipe'],timeout:20000,maxBuffer:16*1024*1024
  });
  const sha=crypto.createHash('sha1')
    .update(Buffer.from('blob '+html.length+'\\0')).update(html).digest('hex');
  assert.equal(sha,'a52f055dae8c5f672b9d8498f7e79e966458e414');
  const match=html.toString('utf8').match(/function pvComputeAUC\\(yTrue, yProb\\) \\{[\\s\\S]*?\\n\\}/);
  assert.ok(match,'exact historical prospective AUC function found');
  const old=vm.runInNewContext('('+match[0]+')');
  const probabilities=Array(5).fill(0.5);
  assert.equal(old([1,1,0,0,0],probabilities).auc,1);
  assert.equal(old([0,0,0,1,1],probabilities).auc,0);
  assert.equal(tieAwareAuc([1,1,0,0,0],probabilities).auc,0.5);
  assert.equal(tieAwareAuc([0,0,0,1,1],probabilities).auc,0.5);
});
test('actual 493-case frozen backtest sample confirms ties and order-invariant reference', () => {
  // Archived labels are mostly unadjudicated; this only checks arithmetic.
  const lines=fs.readFileSync('backtest/backtest_results.csv','utf8').trim().split(/\\r?\\n/);
  assert.equal(lines[0],'nct_id,year,actual,predicted,p_bayes,p_power,p_reg,drug_class,endpoint_type,n_train');
  const rows=lines.slice(1).map(line=>line.split(','));
  assert.equal(rows.length,493);
  const ids=rows.map(row=>row[0]);
  assert.equal(new Set(ids).size,493);
  const y=rows.map(row=>Number(row[2]));
  const p=rows.map(row=>Number(row[3]));
  assert.equal(y.filter(n=>n===1).length,343);
  assert.equal(y.filter(n=>n===0).length,150);
  let mixedTies=0;
  for(let i=0;i<493;i++)for(let j=0;j<493;j++){
    if(y[i]===1 && y[j]===0 && p[i]===p[j])mixedTies++;
  }
  assert.equal(mixedTies,91);
  consistent(y,p);
  consistent([...y].reverse(),[...p].reverse());
  assert.ok(Math.abs(tieAwareAuc(y,p).auc-0.7404567541302235)<1e-12);
});

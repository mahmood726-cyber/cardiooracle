'use strict';
// Research-only: NCT06307652 BalanceD-HF; source concordance is not outcome adjudication.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const crypto=require('node:crypto');
const path=require('node:path');
const originalBlob='d61e874de348d8840317417848b51514ae272c8f';
const asof='2026-03-25';
const hRA='https://www.hra.nhs.uk/planning-and-improving-research/application-summaries/research-summaries/balanced-hf/';
const ctis='https://ctis.eu/trial/2023-508162-15-00/';
const changes=[
  ['SM-30','2025-09-25','2026-01-15'],
  ['NSM-7','2026-01-20','2026-01-20'],
  ['SM-31','2026-01-21','2026-02-06'],
  ['SM-32','2026-01-22','2026-03-13'],
  ['SM-33','2026-02-06','2026-02-12'],
  ['SM-34','2026-03-06','2026-04-24'],
  ['NSM-8','2026-04-27','2026-04-27'],
  ['SM-35','2026-04-29','2026-08-10']
];
// Date of modification submission is NOT proof of decision or record availability.
function approvedBefore(rows,when) {
  if(!/^\d{4}-\d{2}-\d{2}$/.test(when)) throw new TypeError('ISO date required');
  return rows.filter(([id,submitted,decided])=>id&&submitted<=when&&decided<=when);
}
function armContrasts(n1,n2,nControl,variance=1){
  for(const v of [n1,n2,nControl,variance]) if(!Number.isFinite(v)||v<=0)
    throw new RangeError('finite positive sample size and variance required');
  const a=variance/n1+variance/nControl;
  const b=variance/n2+variance/nControl;
  const cov=variance/nControl;
  return {a,b,cov,trueVar:(a+b+2*cov)/4,naiveVar:(a+b)/4};
}
function firstComposite(e){
  if(!e||typeof e!=='object') throw new TypeError('event object required');
  for(const key of ['cvDeath','hfHospital','outpatientHf']){
    if(![0,1].includes(e[key])) throw new RangeError('invalid '+key);
  }
  return Number(e.cvDeath===1||e.hfHospital===1||e.outpatientHf===1);
}
test('current THIRD-PARTY CTIS timeline is not a signed as-of registry snapshot',()=>{
  assert.ok(hRA.includes('hra.nhs.uk'));
  assert.ok(ctis.includes('ctis.eu'));
  assert.deepEqual(approvedBefore(changes,asof).map(x=>x[0]),
    ['SM-30','NSM-7','SM-31','SM-32','SM-33']);
  assert.equal(approvedBefore(changes,asof).some(x=>x[0]==='SM-34'),false);
  assert.equal(changes.find(x=>x[0]==='SM-34')[1]<asof,true);
  assert.equal(changes.find(x=>x[0]==='SM-34')[2]>asof,true);
  assert.throws(()=>approvedBefore(changes,'2026/03/25'),TypeError);
});
test('shared active control creates covariance, NOT two independent studies',()=>{
  for(let n=25;n<=2025;n++){
    const c=armContrasts(n,n,n);
    assert.ok(c.trueVar>c.naiveVar);
    assert.ok(Math.abs(c.trueVar/c.naiveVar-1.5)<1e-12);
    assert.ok(Math.abs(c.cov/Math.sqrt(c.a*c.b)-.5)<1e-12);
  }
  assert.throws(()=>armContrasts(0,200,200),RangeError);
  assert.throws(()=>armContrasts(200,-10,200),RangeError);
});
test('mortality-only flag loses nonfatal primary composite components',()=>{
  const none={cvDeath:0,hfHospital:0,outpatientHf:0};
  for(let i=0;i<1000;i++){
    assert.equal(firstComposite(none),0);
    assert.equal(firstComposite({...none,hfHospital:1}),1);
    assert.equal(firstComposite({...none,outpatientHf:1}),1);
    assert.equal(firstComposite({...none,cvDeath:1}),1);
  }
  assert.throws(()=>firstComposite({...none,hfHospital:null}),RangeError);
});
test('immutable full frozen25 archive, prospective outcomes and BalanceD source features',()=>{
  const raw=fs.readFileSync(path.resolve(__dirname,'..','prospective_predictions_20260325.json'));
  const blob=crypto.createHash('sha1').update('blob '+raw.length+'\0').update(raw).digest('hex');
  assert.equal(blob,originalBlob);
  const archive=JSON.parse(raw.toString('utf8'));
  assert.equal(archive.generated,'2026-03-25T10:43:16.485Z'); // self-declared, not externally anchored
  assert.equal(archive.trials.length,25);
  assert.equal(new Set(archive.trials.map(x=>x.nct_id)).size,25);
  assert.equal(archive.trials.every(x=>x.outcome===null&&x.outcome_date===null&&x.outcome_source===null),true);
  const t=archive.trials.find(x=>x.nct_id==='NCT06307652');
  assert.ok(t);
  assert.equal(t.features.double_blind,false); // HRA 2024 says blinded; REVIEW, not correction
  assert.equal(t.features.placebo_controlled,false); // correct with ACTIVE comparator and double dummy
  assert.equal(t.features.comparator_type,'active');
  assert.equal(t.features.endpoint_type,'mortality'); // lossy first-event HF composite
  assert.equal(t.features.interventions.length,3);
  assert.equal(t.features.enrollment,4800);
  assert.equal(t.outcome,null);
  assert.ok(Math.abs(t.prediction.p_success-.887)<1e-12);
  assert.ok(Math.abs(.4*t.prediction.components.bayesian+.35*t.prediction.components.power+
    .25*t.prediction.components.regression-t.prediction.p_success)<.0002);
  // No clinical outcome is calculated and no human review is simulated.
});

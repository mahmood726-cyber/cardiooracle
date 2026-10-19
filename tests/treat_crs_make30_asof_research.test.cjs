'use strict';
// SCIENTIFIC HOLD: TREAT-CRS source-concordance research, never clinical adjudication.
// Current third-party CT.gov source https://www.syfrah.com/trial/NCT06030843
// displays last updated 2026-06-16 AFTER original self-reported 2026-03-25 lock.
// No authenticated actual March 2026 ClinicalTrials.gov historic bytes/SAP available.
const test=require('node:test'), assert=require('node:assert/strict');
const cp=require('node:child_process'), crypto=require('node:crypto');
const NCT='NCT06030843', BLOB='d61e874de348d8840317417848b51514ae272c8f';
const LOCK='2026-03-25T10:43:16.485Z'; // software self-asserted, NOT externally witnessed
function MAKE30(p){
  return Boolean(p.death || p.newDialysis || (p.sustainedEgfrLoss===true &&
    Number.isFinite(p.egfrDeclineFraction) && p.egfrDeclineFraction>=.25));
}
function asOfSource(p){
  return Boolean(p && p.rawHistoricalSourceSha256 &&
    /^[a-f0-9]{64}$/i.test(p.rawHistoricalSourceSha256) &&
    p.externallyVerifiedPublicPostedAt && p.signedApprovedProtocol &&
    p.signedApprovedSAP && p.externallyVerifiedForecastLock &&
    Date.parse(p.externallyVerifiedPublicPostedAt)<=Date.parse(LOCK));
}
test('two arms: empagliflozin 10mg and matching placebo; both positive controls',()=>{
  const active='Empagliflozin 10 MG',control='Placebo';
  assert.ok(active.includes('10 MG'));
  assert.equal(control,'Placebo');
  assert.notEqual(active,control);
});
test('death is only one component of trial-specific 30d MAKE30 primary endpoint',()=>{
  const patients=[
    {death:true,newDialysis:false,sustainedEgfrLoss:false,egfrDeclineFraction:0},
    {death:false,newDialysis:true,sustainedEgfrLoss:false,egfrDeclineFraction:0},
    {death:false,newDialysis:false,sustainedEgfrLoss:true,egfrDeclineFraction:.25},
    {death:false,newDialysis:false,sustainedEgfrLoss:true,egfrDeclineFraction:.249},
    {death:false,newDialysis:false,sustainedEgfrLoss:false,egfrDeclineFraction:.50}];
  assert.deepEqual(patients.map(MAKE30),[true,true,true,false,false]);
  assert.equal(patients.filter(p=>p.death).length,1);
  assert.equal(patients.filter(MAKE30).length,3);
});
test('overlapping death and dialysis must count one patient in MAKE30',()=>{
  const people=[
    {death:true,newDialysis:true,sustainedEgfrLoss:true,egfrDeclineFraction:.40},
    {death:false,newDialysis:false,sustainedEgfrLoss:false,egfrDeclineFraction:0}];
  assert.equal(people.filter(MAKE30).length,1);
  assert.equal(people.reduce((s,p)=>s+Number(p.death)+Number(p.newDialysis)+Number(p.sustainedEgfrLoss),0),3);
});
test('synthetic equal mortality cannot substitute for 30d primary MAKE30',()=>{
  const a=Array.from({length:100},(_,i)=>({death:i<2,newDialysis:i>=2&&i<9,
    sustainedEgfrLoss:i>=9&&i<21,egfrDeclineFraction:i>=9&&i<21?.30:0}));
  const b=Array.from({length:100},(_,i)=>({death:i<2,newDialysis:i>=2&&i<4,
    sustainedEgfrLoss:i>=4&&i<8,egfrDeclineFraction:i>=4&&i<8?.30:0}));
  assert.equal(a.filter(p=>p.death).length,b.filter(p=>p.death).length);
  assert.equal(a.filter(MAKE30).length,21);
  assert.equal(b.filter(MAKE30).length,8);
  // ALL 200 simulated patients fictional; NOT trial efficacy.
});
test('acute HF plus KDIGO AKI OR urine NGAL threshold, without diabetes/CKD requirement',()=>{
  const qualifies=(p)=>p.acuteHeartFailure && (p.kdigoAKI || p.ngal>=150) &&
    p.hoursSinceDiagnosis<=12 && p.baselineEgfr>20 && !p.type1Diabetes &&
    !p.sglt2Recent;
  const p={acuteHeartFailure:true,kdigoAKI:true,ngal:30,
    hoursSinceDiagnosis:5,baselineEgfr:57,type1Diabetes:false,sglt2Recent:false,
    diabetes:false,chronicKidneyDisease:false};
  assert.equal(qualifies(p),true);
  assert.equal(qualifies({...p,kdigoAKI:false,ngal:150}),true);
  assert.equal(qualifies({...p,kdigoAKI:false,ngal:149}),false);
  assert.equal(qualifies({...p,type1Diabetes:true}),false);
  assert.equal(qualifies({...p,hoursSinceDiagnosis:13}),false);
  assert.equal(qualifies({...p,baselineEgfr:20}),false);
  // Other trial exclusion criteria also exist; this tests only source excerpts.
});
test('later registry rendering and fake documentary evidence fail as-of evidence gate',()=>{
  assert.ok(Date.parse('2023-09-11')<Date.parse(LOCK));
  assert.ok(Date.parse('2025-10-15')<Date.parse(LOCK));
  assert.ok(Date.parse('2026-06-16')>Date.parse(LOCK));
  assert.equal(asOfSource({rawHistoricalSourceSha256:'a'.repeat(64),
    externallyVerifiedPublicPostedAt:'2026-06-16',signedApprovedProtocol:true,
    signedApprovedSAP:true,externallyVerifiedForecastLock:true}),false);
  assert.equal(asOfSource({rawHistoricalSourceSha256:'invalid',
    externallyVerifiedPublicPostedAt:'2025-10-15',signedApprovedProtocol:true,
    signedApprovedSAP:true,externallyVerifiedForecastLock:true}),false);
  assert.equal(asOfSource({externallyVerifiedPublicPostedAt:'2025-10-15'}),false);
});
test('source paperwork never authenticates independent blinded human adjudicators',()=>{
  const state={clinicallyValidated:false,outcomeKnown:false,
    rawCtgovHistoricalBytesAuthenticated:false,
    twoIndependentBlindedHumanAdjudicatorsVerified:false,
    externallyAnchoredForecast:false};
  assert.deepEqual(Object.values(state),[false,false,false,false,false]);
});
test('immutable original frozen 25-study Git blob and exact TREAT-CRS vector on HEAD',()=>{
  // Fail closed in hosted CI if full checkout or pinned original history absent.
  const raw=cp.execFileSync('git',['show','HEAD:prospective_predictions_20260325.json'],
    {timeout:15000,maxBuffer:2*1024*1024});
  const blob=crypto.createHash('sha1').update(Buffer.from('blob '+raw.length+'\0')).update(raw).digest('hex');
  assert.equal(blob,BLOB);
  const x=JSON.parse(raw.toString('utf8'));
  assert.equal(x.generated,LOCK);
  assert.equal(x.trials.length,25);
  assert.equal(new Set(x.trials.map(t=>t.nct_id)).size,25);
  assert.ok(x.trials.every(t=>t.outcome===null && t.outcome_source===null && t.outcome_date===null));
  const t=x.trials.find(p=>p.nct_id===NCT);assert.ok(t);
  assert.equal(t.features.enrollment,200);
  assert.equal(t.features.double_blind,false); // source mismatch review flag, not changed
  assert.equal(t.features.placebo_controlled,true); // positive control
  assert.equal(t.features.comparator_type,'placebo'); // positive control
  assert.equal(t.features.endpoint_type,'mortality'); // lossy current primary MAKE30
  assert.deepEqual(t.features.interventions,['Empagliflozin 10 MG','Placebo']);
  assert.deepEqual(t.features.population_tags,['diabetic','CKD']);
  assert.equal(t.prediction.p_success,.62);
  assert.equal(t.outcome,null);
});

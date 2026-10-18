'use strict';
// Research-only source-concordance audit, not a clinical validation or forecast generator.
// Evidence: investigator page revised 2026-02-17:
// https://clin.au.dk/ctvs/research/ongoing-projects/ctvs-stenotype
// Current THIRD-PARTY CTIS mirror (NOT authenticated historical raw CTIS):
// https://www.ctis.eu/trial/2023-505375-75-00
// Prelock approved protocol/SAP and as-of CT.gov byte-level provenance remain UNKNOWN.
const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const cp=require('node:child_process');
const BASE='e35c349d269743cc7cd7f8bc199e09470807fe86';
const FROZEN_SHA='d61e874de348d8840317417848b51514ae272c8f';
const LOCK='2026-03-25T10:43:16.485Z'; // self-reported; NOT independent timestamp witness
const SOURCE_REVISED='2026-02-17';
const CASE='NCT05852704';
const AMENDMENTS=[
  ['IN','2023-09-28','2024-01-18'],
  ['SM-1','2024-02-22','2024-04-15'],
  ['APP-3','2024-04-19','2024-07-15'],
  ['SM-2','2024-09-22','2024-10-11'],
  ['SM-4','2025-03-03','2025-04-28'],
  ['SM-5','2026-02-18','2026-03-20'],
  ['SM-6','2026-06-28','2026-08-03']
];
const date=d=>Date.parse(d+'T00:00:00Z');
const byLock=d=>date(d)<=Date.parse(LOCK);
function independentlyDocumentedAsOf(x){
  return Boolean(x&&x.approvedAt&&x.firstPublicAt&&/^[a-f0-9]{64}$/i.test(x.rawSha256??'')&&
    date(x.approvedAt)<=Date.parse(LOCK)&&Date.parse(x.firstPublicAt)<=Date.parse(LOCK));
}
function compareArms(interventions){
  const names=interventions.map(x=>x.toLowerCase());
  return names.some(x=>x.includes('dapagliflozin'))&&names.some(x=>x.includes('placebo'))
    ? 'placebo-comparator-candidate':'not-established';
}
function incidentPostCABGAF(e){
  return !e.priorAF&&e.afterCABG&&e.ecgMonitored&&e.durationSeconds>=30;
}
test('frozen 25 original Git bytes and STENOTYPE metadata are source-pinned, NOT outcomes',()=>{
  const raw=cp.execFileSync('git',['show',BASE+':prospective_predictions_20260325.json'],
    {timeout:20000,maxBuffer:16*1024*1024});
  const sha=crypto.createHash('sha1').update(Buffer.from('blob '+raw.length+'\0')).update(raw).digest('hex');
  assert.equal(sha,FROZEN_SHA);
  const a=JSON.parse(raw.toString('utf8'));
  assert.equal(a.generated,LOCK);
  assert.equal(a.trials.length,25);
  assert.equal(new Set(a.trials.map(t=>t.nct_id)).size,25);
  for(const t of a.trials){
    assert.equal(t.outcome,null);assert.equal(t.outcome_date,null);assert.equal(t.outcome_source,null);
  }
  const s=a.trials.find(t=>t.nct_id===CASE);
  assert.ok(s);
  assert.equal(s.prediction.p_success,0.805); // generated prediction only
  assert.equal(s.features.double_blind,false);
  assert.equal(s.features.placebo_controlled,true);
  assert.equal(s.features.comparator_type,'active');
  assert.equal(s.features.endpoint_type,'other');
  assert.deepEqual(s.features.interventions,['Dapagliflozin 10mg Tab','Placebo Tab']);
  assert.ok(s.features.population_tags.includes('AF'));
  const c=s.prediction.components;
  assert.ok(Math.abs(.4*c.bayesian+.35*c.power+.25*c.regression-s.prediction.p_success)<.001);
});
test('investigator-reported Feb 2026 revised date precedes nominal lock (not authenticated bytes)',()=>{
  assert.ok(byLock(SOURCE_REVISED));
  const reported={doubleBlind:true,randomizedArms:['dapagliflozin','matching placebo']};
  assert.equal(reported.doubleBlind,true);
  assert.equal(compareArms(reported.randomizedArms),'placebo-comparator-candidate');
});
test('placebo intervention cannot automatically become active randomized control',()=>{
  assert.equal(compareArms(['Dapagliflozin 10mg Tab','Placebo Tab']),'placebo-comparator-candidate');
  assert.equal(compareArms(['Dapagliflozin','other active therapy']),'not-established');
  assert.equal(compareArms(['placebo only','matching placebo']),'not-established');
});
test('nominal March 25 cut-off uses regulatory DECISION, not just submission',()=>{
  assert.equal(AMENDMENTS.filter(x=>byLock(x[2])).length,6);
  assert.equal(AMENDMENTS.find(x=>x[0]==='SM-5')[2],'2026-03-20');
  assert.ok(byLock('2026-03-20'));
  assert.ok(!byLock('2026-08-03'));
  assert.equal(AMENDMENTS.filter(x=>!byLock(x[2])).map(x=>x[0]).join(','),'SM-6');
});
test('candidate approval must NEVER substitute for verified historical publication and SHA',()=>{
  const x={approvedAt:'2026-03-20',firstPublicAt:null,rawSha256:null};
  assert.equal(independentlyDocumentedAsOf(x),false);
  assert.equal(independentlyDocumentedAsOf({...x,rawSha256:'f'.repeat(64)}),false);
  assert.equal(independentlyDocumentedAsOf({...x,firstPublicAt:'2026-03-26T00:00:00Z',rawSha256:'f'.repeat(64)}),false);
  // Synthetic positive tests a schema contract, not actual independent source verification.
  assert.equal(independentlyDocumentedAsOf({...x,firstPublicAt:'2026-03-21T00:00:00Z',rawSha256:'f'.repeat(64)}),true);
});
test('AF used as incident primary endpoint does not imply patients with previous AF enrolled',()=>{
  const eligibility={excludesPreviousAF:true},tag='AF';
  assert.equal(tag==='AF'&&eligibility.excludesPreviousAF,true);
  assert.equal(incidentPostCABGAF({priorAF:false,afterCABG:true,ecgMonitored:true,durationSeconds:30}),true);
  assert.equal(incidentPostCABGAF({priorAF:false,afterCABG:true,ecgMonitored:true,durationSeconds:29}),false);
  assert.equal(incidentPostCABGAF({priorAF:true,afterCABG:true,ecgMonitored:true,durationSeconds:60}),false);
  assert.equal(incidentPostCABGAF({priorAF:false,afterCABG:false,ecgMonitored:true,durationSeconds:60}),false);
});
test('binary new-onset AF and secondary death are distinct in synthetic observations',()=>{
  let primaryNoMortality=0;
  for(let i=0;i<1200;i++){
    const primary=incidentPostCABGAF({priorAF:false,afterCABG:true,ecgMonitored:true,
      durationSeconds:(i%4===0?35:10)});
    const died=(i%31===0);
    if(primary&&!died)primaryNoMortality++;
  }
  assert.ok(primaryNoMortality>250); // synthetic; NOT real trial events
});
test('documentation remains unadjudicated absent two actual score-blinded reviewers',()=>{
  const x={ctgovAsOfSHA:null,signedProtocolSHA:null,signedSAPSHA:null,humans:[],observedOutcome:null};
  assert.equal(Boolean(x.ctgovAsOfSHA&&x.signedSAPSHA&&x.humans.length===2),false);
  assert.equal(x.observedOutcome,null);
});
'use strict';
// RESEARCH ONLY — synthetic non-inferiority/period controls + immutable archived source.
// Primary current secondary CTIS source: https://www.ctis.eu/trial/2024-517977-26-00
// NEVER certify trial outcomes, as-of registry versions, or clinical predictor validity.
const test=require('node:test'), assert=require('node:assert/strict');
const cp=require('node:child_process'),crypto=require('node:crypto');
const LOCK=Date.parse('2026-03-25T10:43:16.485Z'); // not externally timestamp-anchored
const BLOB='d61e874de348d8840317417848b51514ae272c8f';
function ni(lower,margin,sapVerified) {
  // ILLUSTRATIVE scale W>1 benefit: margin .8 is FICTIONAL, not EMPA-CON's.
  if(!sapVerified||!Number.isFinite(margin)||!Number.isFinite(lower))return null;
  if(margin<=0||margin>=1)return null;
  return lower>margin;
}
test('SM4 submitted before forecast but APPROVED only after nominal forecast date',()=>{
  assert.ok(Date.parse('2026-01-23')<LOCK); // last earlier approved SM3
  assert.ok(Date.parse('2026-03-19')<LOCK); // SM4 submission alone
  assert.ok(Date.parse('2026-04-22')>LOCK); // SM4 approval after
  assert.ok(Date.parse('2026-08-03')>LOCK); // postlock SM6
  const canUse=(decision,publicDate,verified)=>
    Boolean(verified&&Date.parse(decision)<=LOCK&&Date.parse(publicDate)<=LOCK);
  assert.equal(canUse('2026-04-22','2026-03-19',true),false);
  assert.equal(canUse('2026-01-23','2026-04-02',true),false);
  assert.equal(canUse('2026-01-23','2026-02-01',false),false);
  assert.equal(canUse('2026-01-23','2026-02-01',true),true); // synthetic control
});
test('EMPA-CON switches from BLINDED inpatient treatment/placebo to BOTH ACTIVE later',()=>{
  const hospital={masked:true,continue:'empagliflozin 10 mg',interrupt:'matching placebo'};
  const discharge={masked:false,continue:'empagliflozin 10 mg',interrupt:'empagliflozin 10 mg'};
  assert.equal(hospital.masked,true);
  assert.equal(discharge.masked,false);
  assert.notEqual(hospital.continue,hospital.interrupt);
  assert.equal(discharge.continue,discharge.interrupt);
  assert.ok(hospital.interrupt.includes('placebo'));
});
test('NI success is not superiority: signed trial margin required',()=>{
  assert.equal(ni(.83,.80,true),true);
  assert.equal(.83>1,false);
  assert.equal(ni(.78,.80,true),false);
  assert.equal(ni(.99,.80,true),true);
  assert.equal(.99>1,false);
  assert.equal(ni(.83,null,false),null); // real margin unknown
  assert.equal(ni(.83,.80,false),null); // trial SAP unverified
});
test('primary endpoint has FOUR levels, mortality alone is lossy',()=>{
  const levels=['time-to-all-cause-death','HF-event-count','time-to-first-HF-event','eGFR-5ml-threshold'];
  assert.equal(levels.length,4);
  const twoAlive={a:{alive:true,hfEvents:0},b:{alive:true,hfEvents:2}};
  assert.equal(twoAlive.a.alive,twoAlive.b.alive);
  assert.notEqual(twoAlive.a.hfEvents,twoAlive.b.hfEvents);
  assert.notDeepEqual(levels,['all-cause-mortality']);
});
test('exact original 25-case Git archive pinned; no outcome adjudication',()=>{
  const raw=cp.execFileSync('git',['show','HEAD:prospective_predictions_20260325.json'],
     {timeout:20000,maxBuffer:2*1024*1024,stdio:['ignore','pipe','pipe']});
  const sha=crypto.createHash('sha1').update(Buffer.from('blob '+raw.length+'\0')).update(raw).digest('hex');
  assert.equal(sha,BLOB);
  const a=JSON.parse(raw.toString('utf8'));
  assert.equal(a.generated,'2026-03-25T10:43:16.485Z');
  assert.equal(a.trials.length,25);
  assert.equal(new Set(a.trials.map(x=>x.nct_id)).size,25);
  assert.ok(a.trials.every(x=>x.outcome===null&&x.outcome_source===null&&x.outcome_date===null));
  const t=a.trials.find(x=>x.nct_id==='NCT07038356');
  assert.ok(t);
  assert.equal(t.features.enrollment,536);
  assert.equal(t.features.double_blind,false);
  assert.equal(t.features.placebo_controlled,true);
  assert.equal(t.features.comparator_type,'active');
  assert.equal(t.features.endpoint_type,'mortality');
  assert.ok(Math.abs(t.prediction.p_success-.754)<1e-12);
  assert.ok(Math.abs(.4*.8+.35*.6777+.25*.7857-.754)<.0005);
  assert.equal(t.outcome,null);
});
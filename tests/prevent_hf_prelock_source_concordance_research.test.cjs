'use strict';
// Research-stage, source-pinned *concordance* tests only. Do not interpret as
// human endpoint adjudication, a historical CT.gov version, or clinical validity.
// Primary-source candidate: UK HRA IRAS 1010949 / REC 25/LO/0020,
// https://www.hra.nhs.uk/planning-and-improving-research/application-summaries/research-summaries/baxduo-prevent-hf/
// REC opinion dated 27 Feb 2025; CURRENT page retrieved 18 Oct 2026.
// HRA page authenticity now does not prove as-of public availability in 2025.
// Original 25-forecast creation time is self-declared, NOT independently witnessed.
const test=require('node:test');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const FROZEN_SHA='d61e874de348d8840317417848b51514ae272c8f';
const LOCK='2026-03-25T10:43:16.485Z';
const NCT='NCT06677060';
const HRA=Object.freeze({
  rec:'25/LO/0020', recOpinionDate:'2025-02-27',
  randomized:true, doubleBlindedBaxdrostat:true, placeboBaxdrostatComparator:true,
  openLabelCommonDapagliflozin:true, firstHFEventPrimary:true, cvDeathPrimary:true
});
function frozen(){
  const raw=fs.readFileSync(path.join(__dirname,'..','prospective_predictions_20260325.json'));
  const sha=crypto.createHash('sha1').update('blob '+raw.length+'\0').update(raw).digest('hex');
  assert.equal(sha,FROZEN_SHA,'original 25-study Git blob must be byte-exact');
  return JSON.parse(raw.toString('utf8'));
}
function candidate(evidence,flags,opinionDate,lock=LOCK){
  const at=Date.parse(opinionDate+'T23:59:59Z');
  const temporal=Number.isFinite(at)&&at<Date.parse(lock);
  return {
    prelockEthicsDate:temporal,
    possibleBlindingDiscordance:temporal&&evidence.randomized&&evidence.doubleBlindedBaxdrostat&&flags.double_blind===false,
    possiblePlaceboDiscordance:temporal&&evidence.placeboBaxdrostatComparator&&flags.placebo_controlled===false,
    // A dated ethics opinion is NOT a cryptographic/public-as-of CT.gov version.
    approvedPrelockFullProtocolAuthenticated:false,
    prelockCTgovHistoryAuthenticated:false,
    statisticalAnalysisPlanAuthenticated:false,
    clinicalPredictionValidated:false,
  };
}
function isPrimaryCompositeEvent(row){
  return Boolean(row.hf_hospitalization||row.nonhospital_hf||row.cv_death);
}
test('positive/negative chronological source eligibility controls',()=>{
  const flags={double_blind:false,placebo_controlled:false};
  const x=candidate(HRA,flags,HRA.recOpinionDate);
  assert.equal(x.prelockEthicsDate,true);
  assert.equal(x.possibleBlindingDiscordance,true);
  assert.equal(x.possiblePlaceboDiscordance,true);
  const future=candidate(HRA,flags,'2026-04-01');
  assert.equal(future.prelockEthicsDate,false);
  assert.equal(future.possibleBlindingDiscordance,false);
  assert.equal(future.possiblePlaceboDiscordance,false);
});
test('open-label COMMON dapagliflozin does not unblind randomized baxdrostat',()=>{
  assert.equal(HRA.openLabelCommonDapagliflozin,true);
  assert.equal(HRA.doubleBlindedBaxdrostat,true);
  const e={...HRA,doubleBlindedBaxdrostat:false};
  assert.equal(candidate(e,{double_blind:false},HRA.recOpinionDate).possibleBlindingDiscordance,false);
  const blindedAssessorsOnly={...HRA,doubleBlindedBaxdrostat:false,blindedEndpointAssessors:true};
  assert.equal(candidate(blindedAssessorsOnly,{double_blind:false},HRA.recOpinionDate).possibleBlindingDiscordance,false);
});
test('matching randomized add-on placebo, not a mere background placebo pack',()=>{
  const flags={placebo_controlled:false};
  assert.equal(candidate(HRA,flags,HRA.recOpinionDate).possiblePlaceboDiscordance,true);
  assert.equal(candidate({...HRA,placeboBaxdrostatComparator:false},flags,HRA.recOpinionDate).possiblePlaceboDiscordance,false);
});
test('first-event HF/CV death primary is not a death-only outcome',()=>{
  const death={hf_hospitalization:false,nonhospital_hf:false,cv_death:true};
  const hospitalizedHF={hf_hospitalization:true,nonhospital_hf:false,cv_death:false};
  const nonhospitalHF={hf_hospitalization:false,nonhospital_hf:true,cv_death:false};
  const none={hf_hospitalization:false,nonhospital_hf:false,cv_death:false};
  assert.equal(isPrimaryCompositeEvent(death),true);
  assert.equal(isPrimaryCompositeEvent(hospitalizedHF),true);
  assert.equal(isPrimaryCompositeEvent(nonhospitalHF),true);
  assert.equal(isPrimaryCompositeEvent(none),false);
  assert.equal(hospitalizedHF.cv_death,false);
  assert.equal(nonhospitalHF.cv_death,false);
});
test('real March 25 frozen archive census, NCT field discordances and scientific HOLD',()=>{
  const archive=frozen();
  assert.equal(archive.generated,LOCK);
  assert.equal(archive.trials.length,25);
  assert.equal(new Set(archive.trials.map(t=>t.nct_id)).size,25);
  assert.equal(archive.trials.filter(t=>t.outcome===null&&t.outcome_source===null&&t.outcome_date===null).length,25);
  const t=archive.trials.find(t=>t.nct_id===NCT);
  assert.ok(t,'PREVENT-HF is one of original 25');
  assert.equal(t.features.double_blind,false);
  assert.equal(t.features.placebo_controlled,false);
  assert.equal(t.features.comparator_type,'placebo');
  assert.equal(t.features.endpoint_type,'mortality');
  assert.deepEqual(t.features.interventions,['Baxdrostat and dapagliflozin','Placebo and dapagliflozin']);
  assert.equal(t.prediction.p_success,0.892); // generated, NOT an outcome
  const {bayesian,power,regression}=t.prediction.components;
  assert.ok(Math.abs(.4*bayesian+.35*power+.25*regression-t.prediction.p_success)<.001);
  const review=candidate(HRA,t.features,HRA.recOpinionDate);
  assert.equal(review.possibleBlindingDiscordance,true);
  assert.equal(review.possiblePlaceboDiscordance,true);
  assert.equal(review.prelockCTgovHistoryAuthenticated,false);
  assert.equal(review.approvedPrelockFullProtocolAuthenticated,false);
  assert.equal(review.statisticalAnalysisPlanAuthenticated,false);
  assert.equal(review.clinicalPredictionValidated,false);
});
// No intervention-arm outcomes, historic registry bytes, independent reviewer
// identities, or predictive accuracy are computed or imputed here.
'use strict';
// RESEARCH-STAGE FAILURE WITNESS, NOT A FORECAST VALIDATION OR CLINICAL OUTCOME TEST.
// No changes to the deployed model, HTML, historical predictions or adjudications.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');
const HTML_SHA = 'a52f055dae8c5f672b9d8498f7e79e966458e414';
const html = fs.readFileSync('CardioOracle.html', 'utf8');
const blob = crypto.createHash('sha1')
  .update(Buffer.from('blob ' + Buffer.byteLength(html) + '\0'))
  .update(html).digest('hex');
assert.equal(blob, HTML_SHA, 'must execute the exact historically audited HTML Git blob');

function originalFunction(name) {
  const re = new RegExp('(?:async\\s+)?function\\s+' + name + '\\s*\\(');
  const match = re.exec(html);
  assert.ok(match, 'original deployed function missing: ' + name);
  const start = match.index;
  const brace = html.indexOf('{', start);
  let depth = 0;
  for (let i = brace; i < html.length; i++) {
    if (html[i] === '{') depth++;
    if (html[i] === '}' && --depth === 0) return html.slice(start, i + 1);
  }
  throw new Error('unbalanced function: ' + name);
}
const names = ['pvHandleAddTrial','pvAssessPredictability','pvInferArea',
  'pvApproveFromQueue','pvPredictAndLock','pvComputeEntryHash','pvVerifyChain'];
const exactFunctions = names.map(originalFunction).join('\n');
const clone = value => JSON.parse(JSON.stringify(value));
const sha256Hex = async s => crypto.createHash('sha256').update(String(s)).digest('hex');

function scenario(i, knownResults) {
  const nct = 'NCT' + String(80000000 + i);
  const study = {
    protocolSection: {
      identificationModule: { nctId: nct },
      designModule: { phases: ['PHASE3'] },
      conditionsModule: { conditions: ['Heart Failure'] },
      statusModule: {
        overallStatus: knownResults ? 'COMPLETED' : 'RECRUITING',
        startDateStruct: { date: '2021-01-01', type: 'ACTUAL' },
        primaryCompletionDateStruct: { date: knownResults ? '2023-01-01' : '2030-01-01',
          type: knownResults ? 'ACTUAL' : 'ESTIMATED' },
        resultsFirstPostDateStruct: knownResults ? { date: '2023-08-01' } : undefined
      }
    },
    hasResults: knownResults,
    resultsSection: knownResults ?
      { outcomeMeasuresModule: { outcomeMeasures: [{type:'PRIMARY',title:'Mortality'}] } } :
      undefined
  };
  let cohort = [], queue = [], fetches = 0;
  const input = { value: nct };
  const ctx = {
    document: { getElementById: () => input },
    fetchTrialFromCTGov: async () => { fetches++; return study; },
    extractFeatures: () => ({ title:'Synthetic trial',drug_class:'sglt2i',
      endpoint_type:'mortality',enrollment:1000,duration:48,year:2021 }),
    pvGetCohort: () => clone(cohort), pvSaveCohort: x => { cohort = clone(x); },
    pvGetQueue: () => clone(queue), pvSaveQueue: x => { queue = clone(x); },
    pvRenderReviewQueue: () => {}, pvRenderCohortTable: () => {},
    pvShowStatus: () => {},
    computeSimilarity: () => 0.5, bayesianBorrowing: () => ({ p:0.6 }),
    conditionalPower: () => ({ power:0.6 }),
    metaRegressionPredict: () => ({ p:0.6 }),
    ensemblePredict: () => ({ p:0.6,levelLabel:'High' }),
    sha256Hex, TRAINING_DATA: { trials:[{ nct_id:'NCT10000000' }] },
    PV_MODEL_VERSION:'audit-v1'
  };
  const f = new Function(...Object.keys(ctx),
    exactFunctions + '\nreturn {pvHandleAddTrial,pvApproveFromQueue,pvVerifyChain};'
  )(...Object.values(ctx));
  return {
    nct,study,f,
    async run() {
      await f.pvHandleAddTrial();
      assert.equal(queue.length,1);
      assert.equal(queue[0]._ctgovData.hasResults,knownResults);
      await f.pvApproveFromQueue(nct);
      assert.equal(fetches,1);
      assert.equal(queue.length,0);
      assert.equal(cohort.length,1);
      return clone(cohort[0]);
    },
    verify: () => f.pvVerifyChain(cohort)
  };
}

test('original source is pinned, with admission and hash verification functions present', () => {
  assert.equal(names.length,7);
  assert.ok(exactFunctions.includes('const features = extractFeatures(ctgovData)'));
  assert.ok(exactFunctions.includes("status: 'RECRUITING'"));
});

test('retrospective outcome-known Phase III trial can enter prospective locked cohort', async () => {
  for (let i=0; i<50; i++) {
    const s=scenario(i,true);
    const entry=await s.run();
    const status=s.study.protocolSection.statusModule;
    assert.equal(status.overallStatus,'COMPLETED');
    assert.equal(s.study.hasResults,true);
    assert.ok(s.study.resultsSection);
    assert.ok(Date.parse(status.primaryCompletionDateStruct.date)<Date.parse(entry.locked_at));
    assert.ok(Date.parse(status.resultsFirstPostDateStruct.date)<Date.parse(entry.locked_at));
    assert.equal(entry.status,'RECRUITING'); // demonstrated failure, not desired future contract
    assert.equal(entry.prediction.p_ensemble,0.6);
    assert.equal((await s.verify()).valid,true); // valid hash does not prove prospective design
  }
});

test('future-result recruiting Phase III positive controls still pass the same route', async () => {
  for (let i=50; i<100; i++) {
    const s=scenario(i,false);
    const entry=await s.run();
    assert.equal(s.study.hasResults,false);
    assert.equal(s.study.resultsSection,undefined);
    assert.ok(Date.parse(s.study.protocolSection.statusModule.primaryCompletionDateStruct.date)>Date.parse(entry.locked_at));
    assert.equal(entry.status,'RECRUITING');
    assert.equal((await s.verify()).valid,true);
  }
});

test('test controls distinguish source chronology from SHA-256 integrity', async () => {
  const late=scenario(103,true), future=scenario(104,false);
  const e1=await late.run(), e2=await future.run();
  assert.notEqual(e1.nct_id,e2.nct_id);
  assert.equal((await late.verify()).valid,true);
  assert.equal((await future.verify()).valid,true);
  const posted=Date.parse(late.study.protocolSection.statusModule.resultsFirstPostDateStruct.date);
  assert.ok(posted<Date.parse(e1.locked_at));
  assert.ok(Date.parse(future.study.protocolSection.statusModule.primaryCompletionDateStruct.date)>Date.parse(e2.locked_at));
});

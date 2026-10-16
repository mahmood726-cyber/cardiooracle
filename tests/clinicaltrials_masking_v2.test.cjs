'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { MASKING_COUNTS, PATH, extractMaskingV2, requireAdjudicatedMasking } =
  require('../src/clinicaltrials_masking_v2.cjs');
const ID = 'NCT06307652';
const WHO = ['PARTICIPANT', 'CARE_PROVIDER', 'INVESTIGATOR', 'OUTCOMES_ASSESSOR'];
const make = masking => ({ protocolSection: {
  identificationModule: { nctId: ID },
  designModule: { studyType: 'INTERVENTIONAL', designInfo: { maskingInfo: { masking } } }
}});
const masked = r => r.protocolSection.designModule.designInfo.maskingInfo;

for (const [name, number] of Object.entries(MASKING_COUNTS)) {
  test(`v2 ${name} has correct distinction`, () => {
    const result = extractMaskingV2(make(name), ID);
    assert.equal(result.status, 'EXTRACTED_UNVERIFIED_VINTAGE');
    assert.equal(result.double_blind, number >= 2);
    assert.equal(result.historical_source_verified, false);
    assert.equal(result.source_path, PATH);
    assert.throws(() => requireAdjudicatedMasking(result), /SCIENTIFIC_HOLD/);
  });
  test(`v2 ${name} validates whoMasked count`, () => {
    const r = make(name); masked(r).whoMasked = WHO.slice(0, number);
    assert.equal(extractMaskingV2(r, ID).masked_role_count, number);
    masked(r).whoMasked = WHO.slice(0, (number + 1) % 5);
    assert.equal(extractMaskingV2(r, ID).status, 'HOLD');
  });
}
const malformed = [
  ['no record', null, ID],
  ['no protocol', {}, ID],
  ['array protocol', { protocolSection: [] }, ID],
  ['wrong trial id', make('DOUBLE'), 'NCT00000001'],
  ['invalid id', make('DOUBLE'), 'NCTwrong'],
  ['noninterventional', (()=>{const r=make('DOUBLE');r.protocolSection.designModule.studyType='OBSERVATIONAL';return r;})(), ID],
  ['missing design info', (()=>{const r=make('DOUBLE');delete r.protocolSection.designModule.designInfo;return r;})(), ID],
  ['missing masking info', (()=>{const r=make('DOUBLE');delete r.protocolSection.designModule.designInfo.maskingInfo;return r;})(), ID],
  ['bad enum', make('FIVEFOLD'), ID],
  ['bad case', make('double'), ID],
  ['null masking', make(null), ID],
  ['empty masking', make(''), ID],
  ['missing nested but legacy field', (()=>{const r=make('DOUBLE');delete r.protocolSection.designModule.designInfo;r.protocolSection.designModule.maskingInfo={masking:'DOUBLE'};return r;})(), ID],
  ['legacy field conflict', (()=>{const r=make('DOUBLE');r.protocolSection.designModule.maskingInfo={masking:'NONE'};return r;})(), ID],
  ['unknown whoMasked role', (()=>{const r=make('DOUBLE');masked(r).whoMasked=['UNKNOWN','PARTICIPANT'];return r;})(), ID],
  ['duplicate whoMasked role', (()=>{const r=make('DOUBLE');masked(r).whoMasked=['PARTICIPANT','PARTICIPANT'];return r;})(), ID],
  ['whoMasked wrong type', (()=>{const r=make('DOUBLE');masked(r).whoMasked='PARTICIPANT';return r;})(), ID],
];
for (const [description, record, id] of malformed) {
  test(`fail-closed: ${description}`, () => {
    const result = extractMaskingV2(record, id);
    assert.equal(result.status, 'HOLD');
    assert.equal(result.double_blind, null);
    assert.throws(() => requireAdjudicatedMasking(result), /SCIENTIFIC_HOLD/);
  });
}
test('cannot turn missing masking into an unblinded result', () => {
  const r=make('DOUBLE'); delete r.protocolSection.designModule.designInfo;
  assert.notEqual(extractMaskingV2(r, ID).double_blind, false);
});
test('no direct mutation of source record', () => {
  const r=make('QUADRUPLE'); const before=JSON.stringify(r);
  extractMaskingV2(r, ID); assert.equal(JSON.stringify(r), before);
});
test('historical provenance not auto-verified by current record', () => {
  const r=make('SINGLE'); r.studyFirstPostDate='2020-01-01';
  assert.equal(extractMaskingV2(r, ID).historical_source_verified, false);
});

test('caller cannot forge adjudication using status/provenance flags', () => {
  assert.throws(() => requireAdjudicatedMasking({
    status: 'ADJUDICATED_HISTORICAL_FEATURE', historical_source_verified: true,
    double_blind: true
  }), /SCIENTIFIC_HOLD/);
});

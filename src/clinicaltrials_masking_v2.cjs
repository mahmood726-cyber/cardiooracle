'use strict';

// Read-only ClinicalTrials.gov v2 protocol shape adapter. This is NOT a
// prediction model and never certifies that the record was publicly available
// at a historical forecast cutoff. See issue #3 before using a trial feature.
const MASKING_COUNTS = Object.freeze({ NONE: 0, SINGLE: 1, DOUBLE: 2, TRIPLE: 3, QUADRUPLE: 4 });
const MASKED_ROLES = new Set(['PARTICIPANT', 'CARE_PROVIDER', 'INVESTIGATOR', 'OUTCOMES_ASSESSOR']);
const PATH = 'protocolSection.designModule.designInfo.maskingInfo.masking';
const NCT_RE = /^NCT\d{8}$/;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

function hold(reason, nctId = null) {
  return Object.freeze({ status: 'HOLD', reason, nct_id: nctId, masking: null,
    double_blind: null, source_path: PATH, historical_source_verified: false });
}

/** Parse structure only. No value returned here is an authenticated as-of feature. */
function extractMaskingV2(record, expectedNctId) {
  if (typeof expectedNctId !== 'string' || !NCT_RE.test(expectedNctId)) {
    return hold('INVALID_EXPECTED_NCT');
  }
  if (!object(record) || !object(record.protocolSection)) return hold('INVALID_PROTOCOL');
  const protocol = record.protocolSection;
  if (protocol.identificationModule?.nctId !== expectedNctId) return hold('NCT_ID_MISMATCH');
  const design = protocol.designModule;
  if (!object(design)) return hold('MISSING_DESIGN', expectedNctId);
  if (design.studyType !== 'INTERVENTIONAL') return hold('NOT_INTERVENTIONAL', expectedNctId);
  const maskingInfo = design.designInfo?.maskingInfo;
  if (!object(maskingInfo)) return hold('MISSING_V2_MASKING', expectedNctId);
  const masking = maskingInfo.masking;
  if (typeof masking !== 'string' || !Object.prototype.hasOwnProperty.call(MASKING_COUNTS, masking)) {
    return hold('UNKNOWN_MASKING', expectedNctId);
  }
  // Reject contradictory root-level legacy data instead of trusting either.
  if (design.maskingInfo != null && design.maskingInfo.masking !== masking) {
    return hold('CONTRADICTORY_LEGACY_FIELD', expectedNctId);
  }
  const roles = maskingInfo.whoMasked;
  if (roles !== undefined) {
    if (!Array.isArray(roles) || roles.some(role => !MASKED_ROLES.has(role)) ||
        new Set(roles).size !== roles.length) {
      return hold('INVALID_MASKED_ROLES', expectedNctId);
    }
    if (roles.length !== MASKING_COUNTS[masking]) {
      return hold('MASKED_ROLE_COUNT_MISMATCH', expectedNctId);
    }
  }
  return Object.freeze({ status: 'EXTRACTED_UNVERIFIED_VINTAGE', reason: null,
    nct_id: expectedNctId, masking, double_blind: MASKING_COUNTS[masking] >= 2,
    masked_role_count: roles?.length ?? null, source_path: PATH,
    historical_source_verified: false });
}

/** Never allow a current registry parse to authorize a success forecast. */
function requireAdjudicatedMasking() {
  // This module has no trusted historical record store or human-review signature.
  // Caller-provided flags MUST NOT be treated as proof of adjudication.
  throw new Error('SCIENTIFIC_HOLD: historical masking source and reviewer adjudication required');
}

module.exports = { MASKING_COUNTS, PATH, extractMaskingV2, requireAdjudicatedMasking };

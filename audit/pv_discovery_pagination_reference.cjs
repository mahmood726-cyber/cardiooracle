'use strict';
// Research-stage ClinicalTrials.gov cursor-pagination reference.
// This is NOT connected to the deployed predictor or its frozen forecasts.
// A search with nextPageToken is incomplete until all further pages are read.
async function collectStudyPages(fetchPage, { maxPages = 40, maxStudies = 2000 } = {}) {
  if (typeof fetchPage !== 'function') throw new TypeError('fetchPage must be a function');
  if (!Number.isSafeInteger(maxPages) || maxPages < 1 ||
      !Number.isSafeInteger(maxStudies) || maxStudies < 1) {
    throw new RangeError('positive integer pagination bounds required');
  }
  const studies = [];
  const ids = new Set();
  const tokens = new Set();
  let pageToken = null;
  let pagesFetched = 0;
  while (true) {
    if (pagesFetched >= maxPages) throw new Error('incomplete study search: page limit reached');
    const page = await fetchPage(pageToken);
    pagesFetched++;
    if (!page || !Array.isArray(page.studies)) {
      throw new TypeError('invalid ClinicalTrials.gov studies response');
    }
    for (const study of page.studies) {
      const id = study?.protocolSection?.identificationModule?.nctId;
      if (typeof id !== 'string' || !/^NCT\d{8}$/.test(id)) {
        throw new Error('incomplete study search: invalid NCT identifier');
      }
      if (ids.has(id)) throw new Error('incomplete study search: repeated NCT identifier');
      ids.add(id);
      if (studies.length >= maxStudies) throw new Error('incomplete study search: study limit reached');
      studies.push(study);
    }
    if (page.nextPageToken == null || page.nextPageToken === '') {
      return { studies, pagesFetched, complete: true };
    }
    const token = page.nextPageToken;
    if (typeof token !== 'string' || tokens.has(token)) {
      throw new Error('incomplete study search: invalid/repeated pagination token');
    }
    tokens.add(token);
    pageToken = token;
  }
}
module.exports = { collectStudyPages };

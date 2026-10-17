'use strict';

// Research-stage statistical reference only; NOT wired into CardioOracle.html.
// Correct ROC AUC for binary outcomes: a tied positive/negative pair gets 1/2 credit.
// No clinical validity, calibration or source-adjudication claim is implied.
function tieAwareAuc(yTrue, yProb) {
  if (!Array.isArray(yTrue) || !Array.isArray(yProb) || yTrue.length !== yProb.length) {
    throw new TypeError('labels and probabilities must be arrays of identical length');
  }
  const n = yTrue.length;
  if (n < 2) return null;
  for (let i = 0; i < n; i++) {
    if (yTrue[i] !== 0 && yTrue[i] !== 1) throw new RangeError('binary label required at ' + i);
    if (typeof yProb[i] !== 'number' || !Number.isFinite(yProb[i]) ||
        yProb[i] < 0 || yProb[i] > 1) throw new RangeError('finite probability in [0,1] required at ' + i);
  }
  const nPos = yTrue.filter(y => y === 1).length;
  const nNeg = n - nPos;
  if (!nPos || !nNeg) return null;
  const sorted = yTrue.map((y, i) => ({ y, p: yProb[i] })).sort((a, b) => b.p - a.p);
  const roc = [{ fpr: 0, tpr: 0 }];
  let tp = 0, fp = 0;
  // Move all observations at a given threshold simultaneously. Otherwise
  // an arbitrary stable sort of ties can change the trapezoidal AUC.
  for (let i = 0; i < n;) {
    let j = i;
    while (j < n && sorted[j].p === sorted[i].p) {
      if (sorted[j].y === 1) tp++;
      else fp++;
      j++;
    }
    roc.push({ fpr: fp / nNeg, tpr: tp / nPos });
    i = j;
  }
  let auc = 0;
  for (let i = 1; i < roc.length; i++) {
    auc += (roc[i].fpr - roc[i - 1].fpr) * (roc[i].tpr + roc[i - 1].tpr) / 2;
  }
  return { auc, roc };
}

module.exports = { tieAwareAuc };

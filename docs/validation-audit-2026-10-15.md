# CardioOracle validation audit — 15 October 2026

## Audit disposition

The previously published "temporal test" AUC 0.745 and Brier 0.196
cannot be interpreted as independent held-out predictive performance.
In the original `curate/fit_model.py`, `main()` fitted coefficients on **all**
labeled trials, then passed those coefficients to
`compute_temporal_split_metrics()`. Trials labeled as "test" had therefore
already contributed their labels to coefficient estimation. An outcome-derived
`historical_class_rate` could also encode future/test outcomes.

**Those numbers and the existing website-embedded model have not been corrected
by this source-code fix alone. Do not claim new validation performance until a
fresh data/model rebuild and independent outcome audit are complete.**

## Source-code corrections in this change

1. Held-out evaluation now refits the regression on records with a known
   primary-completion date strictly before the specified cutoff.
2. The holdout labels never enter model training, feature target encoding,
   or class-rate computation. Each training row receives a leave-one-out
   drug-class rate. Holdout rows use rates computed exclusively from training.
3. Missing completion dates are excluded from time-based evaluation rather
   than automatically mislabelled post-cutoff.
4. ROC AUC awards half a concordant pair for tied predicted scores.
5. Logistic calibration slope is fitted as outcome versus logit(prediction),
   replacing an inappropriate ordinary-least-squares surrogate.
6. Held-out evaluation returns explicit status when there are insufficient
   training rows, only one training class, or only one test class.
7. Automated regression tests challenge the holdout with deliberately
   label-encoded features and flipped future outcomes.

## Outstanding scientific and engineering risks

- **Outcome labels:** The automatic extractor does not establish trial
  superiority/noninferiority hypotheses, intervention–comparator contrast,
  numerator direction, or whether higher/lower event values represent benefit.
  In `label_outcomes.py` a significant non-ratio p-value currently defaults
  to "success", and `Hazard Ratio (HR)` is not recognised by an exact-string
  ratio checker. This can yield false labels. Require independent adjudication,
  arm mapping and a prespecified endpoint/direction policy before retraining.
- **Temporal information availability:** Primary-completion date does not
  establish when results were publicly available. A stricter historical
  backtest needs timestamped result publications/registry postings and only
  covariates knowable before the trial outcome.
- **Data products:** Rebuild and audit `data/model_coefficients.json`,
  `data/model_cad_coefficients.json`, figures, the browser bundle and
  prospective prediction artefacts. They are not automatically patched by
  code updates. Freeze hashes for the pre- and post-audit releases.
- **Uncertainty:** Browser probability intervals and ensemble component
  weights need calibration and external prospective validation. AUC alone
  cannot establish clinical or investment-grade reliability.

## Reproduction and acceptance criteria

From a fresh clone on Python 3.11:

```sh
python -m pip install -r curate/requirements.txt pytest
python -m pytest -q tests/test_curation.py tests/test_reproducibility.py tests/test_temporal_validation.py backtest/test_backtest.py
```

Next, rerun curation and model fitting on independently adjudicated labels,
recalculate metrics on the pre-declared holdout, and compare predicted versus
observed success without recalibrating against the holdout. Publish the exact
trial IDs, label evidence, split dates, fit coefficients, prediction scores,
ROC AUC (ties handled), Brier score, calibration intercept/slope, and confidence
intervals, together with contamination checks.

**Operational rule:** Do not replace the historical headline metrics with new
numbers or claim clinical-grade validation unless these acceptance checks pass.

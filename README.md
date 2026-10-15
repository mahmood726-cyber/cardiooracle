# CardioOracle

**An open-access tool for predicting cardiovascular trial outcomes.**

CardioOracle is a browser-based prediction tool that estimates the probability a cardiovascular clinical trial will meet its primary endpoint. It combines Bayesian historical borrowing, conditional power analysis, and logistic meta-regression into a transparent, validated ensemble.

## Features

- **Predict:** Enter any NCT ID to get an instant success probability with confidence interval
- **Design:** Interactive trial designer with live probability feedback as you adjust parameters
- **Training Data:** Explore all 784+ labeled training trials with sortable, filterable table and CSV export
- **Calibration:** ROC curve (AUC=0.787), Brier score, per-trial validation predictions
- **WebR Validation:** In-browser R cross-validation of all statistical computations
- **Multi-Config:** Cardiorenal (784 trials) and CAD (90 trials) therapeutic areas
- **Patient Mode:** Plain-language explanations for non-specialists
- **TruthCert:** Export prediction bundles with full provenance
- **PDF Export:** Print-optimized reports

## Quick Start

1. Download `CardioOracle.html`
2. Open in any modern browser (Chrome, Firefox, Edge, Safari)
3. Enter an NCT ID (e.g., `NCT06033950`) or switch to the Design tab

No installation, no server, no dependencies. Everything runs in your browser.

## How It Works

### Prediction Model (3-component ensemble)

| Component | Weight | Method |
|-----------|--------|--------|
| Bayesian Historical Borrowing | 40% | Beta-Binomial posterior from K most similar completed trials |
| Conditional Power | 35% | Schoenfeld/arcsine/SMD formulas by endpoint type |
| Design Feature Meta-Regression | 25% | L2-regularized logistic regression on 18 features |

### Training Data

- **Source:** AACT database (ClinicalTrials.gov)
- **Scope:** Phase 2/3 and Phase 3 cardiovascular RCTs with posted results
- **Size:** 784 cardiorenal + 90 CAD labeled trials
- **Labeling:** 3-tier system (p-value automated, CI-based heuristic, 29 landmark manual)

### Validation status (under correction)

**Important methodological notice, 15 October 2026:** The historical numbers below are
**not independent temporal-validation estimates**. An earlier implementation fitted
regression coefficients using **all trials** before evaluating the nominal post-2020
cohort; outcome-derived historical class rates could also leak labels. This must
not be presented as a genuinely out-of-sample or prospective result.

| Reported historical metric | Value | Status |
|----------------------------|-------|--------|
| In-sample AUC (n=784) | 0.787 | Apparent performance only |
| Earlier so-called temporal AUC (n=133) | 0.745 | **Invalid as held-out validation; superseded** |
| Earlier so-called temporal Brier score | 0.196 | **Invalid as held-out validation; superseded** |

The updated source pipeline now refits on pre-cutoff data only, uses training-only
historical rates, correctly handles ROC ties, and calculates a logistic calibration
slope. The existing checked-in JSON, HTML-embedded predictions and figures were
produced before these corrections and **have not yet been regenerated or independently
validated**. Treat all displayed probabilities as experimental, not clinically
validated estimates. See [validation audit](docs/validation-audit-2026-10-15.md).

## Technology

- Single-file HTML (~4,200 lines), vanilla JavaScript
- Plotly.js for interactive charts
- WebR v0.4.4 for in-browser R validation
- ClinicalTrials.gov API v2 for live trial lookup
- No backend, no build step, no dependencies

## Curation Pipeline

The `curate/` directory contains the Python pipeline for refreshing training data.
Register a free AACT account at https://aact.ctti-clinicaltrials.org/users/sign_up,
then copy `.env.example` to `.env` and fill in `AACT_USER` / `AACT_PASSWORD`.
Run from the repo root so `curate` resolves as a package:

```bash
pip install -r curate/requirements.txt
cp .env.example .env   # then edit .env with your AACT credentials
python -m curate.extract_aact --output data/raw_trials.json
python -m curate.label_outcomes --input data/raw_trials.json --output data/labeled_trials.json
python -m curate.fit_model --input data/labeled_trials.json --output data/model_coefficients.json
python -m curate.export_training --labeled data/labeled_trials.json --output data/training_data.json
```

## Tests

```bash
# Curation pipeline tests (30 tests)
python -m pytest tests/test_curation.py -v

# Selenium browser tests (15 tests)
python -m pytest tests/test_prediction.py -v --timeout=120
```

## Citation

> [Author]. CardioOracle: An Open-Access Tool for Predicting Cardiovascular Trial Outcomes Using Bayesian Historical Borrowing and Design Feature Analysis. 2026.

## License

Open access. Data source: ClinicalTrials.gov (public domain).

# CardioOracle

**The first open-access tool for predicting cardiovascular trial outcomes.**

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

### Validation

| Metric | In-sample (n=784) | Temporal test (n=133, post-2020) |
|--------|-------------------|----------------------------------|
| AUC | 0.787 | 0.745 |
| Brier | 0.169 | 0.196 |

## Technology

- Single-file HTML (~4,200 lines), vanilla JavaScript
- Plotly.js for interactive charts
- WebR v0.4.4 for in-browser R validation
- ClinicalTrials.gov API v2 for live trial lookup
- No backend, no build step, no dependencies

## Curation Pipeline

The `curate/` directory contains the Python pipeline for refreshing training data:

```bash
pip install -r curate/requirements.txt
python curate/extract_aact.py --output data/raw_trials.json
python curate/label_outcomes.py --input data/raw_trials.json --output data/labeled_trials.json
python curate/fit_model.py --input data/labeled_trials.json --output data/model_coefficients.json
python curate/export_training.py --labeled data/labeled_trials.json --output data/training_data.json
```

Requires free AACT credentials from the official AACT sign-up page.

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

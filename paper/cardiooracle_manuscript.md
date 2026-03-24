# CardioOracle: An Open-Access Tool for Predicting Cardiovascular Trial Outcomes Using Bayesian Historical Borrowing and Design Feature Analysis

## Authors
[Author Name], [Affiliation]

## Abstract (250 words max)

**Background:** Clinical trial design in cardiology involves billions of dollars in investment with uncertain outcomes. No open-access tool currently exists to systematically predict the probability that a cardiovascular trial will meet its primary endpoint based on historical evidence.

**Methods:** We developed CardioOracle, a browser-based prediction tool that combines three complementary approaches: (1) Bayesian historical borrowing from similar completed trials, weighted by a 5-dimension similarity metric (drug class, endpoint type, comparator, population, era); (2) conditional power analysis based on historical effect size distributions; and (3) logistic meta-regression on 18 trial design features. Training data was curated from the AACT database (ClinicalTrials.gov), comprising 784 labeled Phase 2/3 and Phase 3 cardiovascular trials with posted results. Success/failure labels were assigned using a 3-tier system: automated p-value extraction (Tier 1), confidence interval-based heuristics (Tier 2), and manual curation of 29 landmark trials (Tier 3).

**Results:** The ensemble model achieved an in-sample AUC of 0.787 (Brier score 0.169) and a temporal holdout AUC of 0.745 (Brier 0.196) on 133 post-2020 trials. The tool supports two modes: lookup (predict outcomes for real trials via ClinicalTrials.gov API) and design (interactive parameter adjustment with live probability feedback). All training data, model coefficients, and prediction provenance are fully transparent and exportable.

**Conclusions:** CardioOracle is the first open-access, browser-based tool for predicting cardiovascular trial outcomes. By making trial prediction transparent and accessible, it can support evidence-based trial design and resource allocation in cardiovascular research.

**Keywords:** clinical trial prediction, cardiovascular, meta-analysis, Bayesian, machine learning, open access

---

## Introduction

[TO BE WRITTEN — 600-800 words covering:
- The burden of failed cardiovascular trials (~$2.6B average Phase 3 cost)
- Gap: no systematic, open-access prediction tool exists
- Existing approaches: pharma-internal models, prediction markets, expert opinion
- What CardioOracle offers: transparent, validated, browser-based, free]

## Methods

### Data Source and Trial Selection
Training data was extracted from the Aggregate Analysis of ClinicalTrials.gov (AACT) database. We included interventional, randomized Phase 2/3, Phase 3, and Phase 3/4 cardiovascular trials with posted results, enrollment >= 50, and completed or terminated status. Cardiovascular conditions were identified using keyword matching against the AACT conditions table.

### Success/Failure Labeling
A 3-tier labeling strategy was employed:
- **Tier 1 (automated):** Primary outcome p-value < 0.05 with effect favoring intervention → success; p >= 0.05 → failure; terminated for futility → failure; terminated for safety → safety failure.
- **Tier 2 (heuristic):** When p-values were unavailable, confidence intervals for ratio-type parameters were used (CI excluding 1.0 → success/failure).
- **Tier 3 (manual):** 29 landmark trials were manually curated with labels verified against published results.

### Feature Extraction
Eighteen features were extracted per trial: log(enrollment), duration (months), placebo-controlled, double-blind, industry sponsor, log(sites), multi-regional, number of arms, DSMB presence, endpoint type (6 categories), era (3 buckets), and historical drug class success rate.

### Prediction Model

#### Component 1: Bayesian Historical Borrowing (weight 0.40)
[Describe 5-dimension similarity, Beta-Binomial posterior]

#### Component 2: Conditional Power Analysis (weight 0.35)
[Describe Schoenfeld/arcsine/SMD formulas by endpoint type]

#### Component 3: Design Feature Meta-Regression (weight 0.25)
[Describe L2 logistic regression, feature decomposition]

#### Ensemble
[Describe weighted average, fixed weights rationale]

### Validation
Temporal split: trials with primary completion before 2020-01-01 (training, n=651) vs. on/after (testing, n=133). Metrics: AUC, Brier score, calibration slope.

### Implementation
Single-file HTML application using vanilla JavaScript, Plotly.js for visualization, and optional WebR v0.4.4 for in-browser R cross-validation. The tool fetches trial data from the ClinicalTrials.gov API v2 at runtime.

## Results

### Training Data
A total of 1,259 Phase 2/3, Phase 3, and Phase 3/4 cardiovascular trials were extracted from AACT. After labeling, 784 trials were included (534 success [68.1%], 237 failure [30.2%], 13 safety failure [1.7%]). The majority (765/784, 97.6%) were labeled via Tier 1 (p-value based).

### Model Performance

| Metric | In-sample (n=784) | Temporal test (n=133) |
|--------|-------------------|----------------------|
| AUC | 0.787 | 0.745 |
| Brier score | 0.169 | 0.196 |

### Feature Importance
[Top 5 predictive features from logistic regression coefficients]

### Case Studies
[2-3 example predictions on known landmark trials]

## Discussion

[TO BE WRITTEN — 800-1000 words covering:
- First open-access trial prediction tool
- Comparison with existing approaches
- Practical utility for trial planners
- Limitations: calibration slope, AACT data quality, Phase filter gaps
- Future directions: additional therapeutic areas, improved calibration, living updates]

## Data Availability
All training data, model coefficients, and source code are available at [REPOSITORY URL]. The labeled dataset is deposited at [ZENODO DOI].

## References
[TO BE ADDED]

# CardioOracle: An Open-Access Tool for Predicting Cardiovascular Trial Outcomes Using Bayesian Historical Borrowing and Design Feature Analysis

## Authors
Mahmood Ahmad, Royal Free Hospital, London, UK

## Abstract (250 words max)

**Background:** Clinical trial design in cardiology involves billions of dollars in investment with uncertain outcomes. No open-access tool currently exists to systematically predict the probability that a cardiovascular trial will meet its primary endpoint based on historical evidence.

**Methods:** We developed CardioOracle, a browser-based prediction tool that combines three complementary approaches: (1) Bayesian historical borrowing from similar completed trials, weighted by a 5-dimension similarity metric (drug class, endpoint type, comparator, population, era); (2) conditional power analysis based on historical effect size distributions; and (3) logistic meta-regression on 18 trial design features. Training data was curated from the AACT database (ClinicalTrials.gov), comprising 784 labeled Phase 2/3 and Phase 3 cardiovascular trials with posted results. Success/failure labels were assigned using a 3-tier system: automated p-value extraction (Tier 1), confidence interval-based heuristics (Tier 2), and manual curation of 29 landmark trials (Tier 3).

**Results:** The ensemble model achieved an in-sample AUC of 0.787 (Brier score 0.169) and a temporal holdout AUC of 0.745 (Brier 0.196) on 133 post-2020 trials. A dedicated coronary artery disease configuration (90 trials) achieved AUC 0.843. The five most influential predictive features were industry sponsorship (coefficient 1.33), surrogate endpoint type (0.75), DSMB presence (-0.59), heart failure hospitalisation endpoint (0.50), and all-cause mortality endpoint (-0.97). Three temporal-holdout case studies demonstrated correct directional predictions for DELIVER, FINEARTS-HF, and EMPACT-MI.

**Conclusions:** CardioOracle is the first open-access, browser-based tool for predicting cardiovascular trial outcomes. By making trial prediction transparent and accessible, it can support evidence-based trial design and resource allocation in cardiovascular research.

**Keywords:** clinical trial prediction, cardiovascular, meta-analysis, Bayesian, machine learning, open access

---

## Introduction

Cardiovascular disease remains the leading cause of death globally, and the development of new therapies relies on large, expensive, and time-consuming randomised controlled trials [Roth et al., *Lancet* 2020]. The average cost of bringing a cardiovascular drug from Phase 1 through regulatory approval now exceeds $2.6 billion, with Phase 3 trials alone consuming hundreds of millions of dollars and requiring years of follow-up [Wouters et al., *JAMA* 2020; DiMasi et al., *Journal of Health Economics* 2016]. Despite this enormous investment, the probability that a cardiovascular drug entering Phase 3 will ultimately succeed remains discouragingly low. Across therapeutic areas, only approximately 13.8% of drugs entering Phase 1 achieve regulatory approval, with cardiovascular drugs historically performing below average owing to the stringent endpoint requirements and the large sample sizes needed to detect clinically meaningful benefits against optimised background therapy [Hay et al., *Nature Biotechnology* 2014; Wong et al., *Biostatistics* 2019].

The consequences of trial failure extend beyond financial loss. Failed trials delay patient access to effective therapies, consume clinical research infrastructure that could be deployed elsewhere, and erode confidence among sponsors considering investment in cardiovascular drug development. The TOPCAT trial (NCT00634712), which tested spironolactone in heart failure with preserved ejection fraction, enrolled 3,445 patients across 270 sites over several years before reporting a negative primary result, partly attributed to regional heterogeneity in patient selection [Pfeffer et al., *New England Journal of Medicine* 2014]. The PARAGON-HF trial (NCT00790764) similarly enrolled nearly 5,000 patients and narrowly missed its primary endpoint (hazard ratio 0.87, p=0.059) [Solomon et al., *New England Journal of Medicine* 2019]. Such outcomes raise a fundamental question: could systematic analysis of historical trial data have provided early quantitative signals about the probability of success or failure?

Pharmaceutical companies have long recognised the value of trial outcome prediction and employ a variety of internal approaches. These include structured expert elicitation panels, where senior clinical scientists estimate success probabilities based on experience and therapeutic intuition; prediction markets, where company employees trade contracts on trial outcomes; and proprietary machine learning models trained on internal pipeline data [Pangalos et al., *Nature Reviews Drug Discovery* 2007]. More recently, several groups have applied natural language processing and deep learning to predict trial outcomes from protocol text and registry features [Lo et al., *Drug Discovery Today* 2019; Feijoo et al., *BMC Medical Informatics and Decision Making* 2020]. However, all of these approaches share critical limitations: they are either opaque (proprietary models with undisclosed training data and coefficients), inaccessible (restricted to company employees or paying subscribers), or both. No open-access, transparent, and validated tool currently exists that allows trial planners, funders, regulators, or academic researchers to systematically estimate the probability that a specific cardiovascular trial will meet its primary endpoint.

We developed CardioOracle to fill this gap. CardioOracle is a browser-based, fully client-side application that requires no installation, no server, and no login. It combines three complementary prediction approaches in a weighted ensemble: (1) Bayesian historical borrowing, which constructs a Beta-Binomial posterior from the outcomes of the most similar completed trials, weighted by a 5-dimension similarity metric; (2) conditional power analysis, which estimates statistical power based on historical effect size distributions using endpoint-specific formulas (Schoenfeld for time-to-event, arcsine for binary, standardised mean difference for continuous outcomes); and (3) logistic meta-regression on 18 trial design features extracted from the ClinicalTrials.gov registry. The ensemble architecture is novel in that it explicitly separates the information provided by historical analogues (what happened in similar trials) from design adequacy (whether the trial is powered to detect a plausible effect) and structural risk factors (which design features are associated with success or failure across the corpus). All training data, model coefficients, and prediction provenance are fully transparent and exportable as machine-readable bundles. The tool supports two therapeutic area configurations (general cardiorenal and coronary artery disease) and offers both a lookup mode (predict outcomes for registered trials via the ClinicalTrials.gov API) and a design mode (interactive parameter adjustment with live probability feedback). By making cardiovascular trial prediction open, reproducible, and accessible, CardioOracle aims to support evidence-based trial design and more efficient allocation of research resources.

## Methods

### Data Source and Trial Selection
Training data was extracted from the Aggregate Analysis of ClinicalTrials.gov (AACT) database. We included interventional, randomized Phase 2/3, Phase 3, and Phase 3/4 cardiovascular trials with posted results, enrollment >= 50, and completed or terminated status. Cardiovascular conditions were identified using keyword matching against the AACT conditions table. A total of 1,259 trials met the initial inclusion criteria. After applying the labeling pipeline, 784 trials retained a definitive success or failure label and formed the final training corpus.

### Success/Failure Labeling
A 3-tier labeling strategy was employed:
- **Tier 1 (automated):** Primary outcome p-value < 0.05 with effect favoring intervention was labeled success; p >= 0.05 was labeled failure; terminated for futility was labeled failure; terminated for safety was labeled safety failure. This tier accounted for 765 of 784 labeled trials (97.6%).
- **Tier 2 (heuristic):** When p-values were unavailable, confidence intervals for ratio-type parameters were used (CI excluding 1.0 with direction favoring intervention was labeled success; CI including 1.0 was labeled failure).
- **Tier 3 (manual):** 29 landmark trials were manually curated with labels verified against published results. These included major cardiovascular outcomes trials such as PARADIGM-HF, DAPA-HF, EMPA-REG OUTCOME, LEADER, TOPCAT, PARAGON-HF, and others whose registry data required expert adjudication.

### Feature Extraction
Eighteen features were extracted per trial from the AACT database: log-transformed enrollment, duration in months, placebo-controlled (binary), double-blind (binary), industry sponsor (binary), log-transformed number of sites, multi-regional (binary), number of arms, DSMB presence (binary), endpoint type (six one-hot encoded categories: MACE, heart failure hospitalisation, cardiovascular death, all-cause mortality, renal, and surrogate), era (three buckets: pre-2010, 2010-2017, 2018 and later), and historical drug class success rate (the observed success proportion of the same drug class in the training corpus).

### Prediction Model

#### Component 1: Bayesian Historical Borrowing (weight 0.40)

The Bayesian historical borrowing component constructs a posterior probability of trial success by learning from the outcomes of the most similar completed trials in the training corpus. For a target trial *t*, we compute a composite similarity score *S(t, c)* against each candidate trial *c* using a weighted sum across five dimensions:

*S(t, c) = w_drug * D_drug + w_endpoint * D_endpoint + w_comparator * D_comparator + w_population * D_population + w_era * D_era*

where the dimension weights are *w_drug* = 0.30, *w_endpoint* = 0.25, *w_comparator* = 0.15, *w_population* = 0.15, and *w_era* = 0.15. Each dimension score ranges from 0 to 1. Drug class similarity *D_drug* takes the value 1.0 for exact match, 0.5 if the two drug classes share a broad mechanism group (e.g., both are RAAS inhibitors), and 0 otherwise. Endpoint similarity *D_endpoint* is 1.0 for exact match, 0.3 if both endpoints belong to the set {MACE, mortality, heart failure, renal} (hard clinical endpoints), and 0 otherwise. Comparator similarity *D_comparator* is 1.0 if both trials use the same comparator type (placebo vs. active) and 0 otherwise. Population similarity *D_population* uses the Jaccard index over population tags (e.g., "diabetic", "elderly", "renal impairment"). Era similarity *D_era* applies an exponential decay with a half-life of 10 years: *D_era* = exp(-|year_t - year_c| * ln(2) / 10), reflecting the diminishing relevance of older trial results as background therapy evolves.

The K most similar trials are selected using a threshold of *S* > 0.3, clamped to the range [5, 30]. If fewer than 5 trials exceed 0.3, the threshold is relaxed to 0.1. If fewer than 3 trials are available after relaxation, the component returns an insufficient-data flag and the ensemble redistributes its weight to the remaining components.

Given the selected set of K similar trials, we construct a Beta-Binomial posterior. Starting from a mildly informative prior Beta(4.5, 5.5) — reflecting a slight prior expectation of failure consistent with overall cardiovascular trial success rates — we compute effective successes and failures weighted by similarity:

*alpha_posterior = alpha_0 + sum(S_i * Y_i)*
*beta_posterior = beta_0 + sum(S_i * (1 - Y_i))*

where *Y_i* is 1 for success and 0 for failure, and *S_i* is the raw (non-normalised) similarity score. The posterior mean *p = alpha_posterior / (alpha_posterior + beta_posterior)* serves as the Bayesian borrowing probability estimate. An 80% credible interval is computed using the normal approximation to the Beta distribution.

#### Component 2: Conditional Power Analysis (weight 0.35)

The conditional power component estimates the statistical power of the target trial to detect a plausible treatment effect, where "plausible" is informed by the outcomes of similar historical trials. The approach uses endpoint-specific power formulas.

For **time-to-event endpoints** (MACE, cardiovascular death, heart failure hospitalisation, all-cause mortality, renal), power is computed using the Schoenfeld formula [Schoenfeld, *Biometrika* 1981]. The expected number of events is estimated as 70% of total enrollment (a conservative assumption reflecting typical cardiovascular trial event accrual). An estimated hazard ratio is derived from the historical success rate of similar trials: *HR_est* = exp(-0.05 - 0.25 * R_success), where *R_success* is the proportion of similar trials that achieved positive results. Power is then:

*z = |log(HR_est)| * sqrt(E) / 2*
*Power = Phi(z - 1.96) + Phi(-z - 1.96)*

where *E* is the expected number of events and *Phi* is the standard normal cumulative distribution function.

For **binary endpoints**, we use the arcsine-transformed power formula. Assuming a control event rate of 15%, the treatment event rate is derived via the estimated relative risk, and power is computed as:

*z = |arcsin(sqrt(p_0)) - arcsin(sqrt(p_1))| * sqrt(n)*
*Power = Phi(|z| - 1.96)*

where *n* is the per-arm sample size.

For **surrogate/continuous endpoints**, power is computed via the standardised mean difference (SMD). An estimated SMD is derived from the historical success rate: *SMD_est* = 0.1 + 0.4 * R_success. The non-centrality parameter is *lambda* = SMD * sqrt(n/2), and power follows from the non-central standard normal distribution.

In each case, the component also generates a power curve across a range of plausible effect sizes, which is displayed interactively in the tool to help users understand the sensitivity of power to effect size assumptions.

#### Component 3: Design Feature Meta-Regression (weight 0.25)

The meta-regression component applies L2-regularised logistic regression (ridge regression, regularisation strength C=1.0) to predict trial success from 18 design features. The model was fitted to all 784 training trials using scikit-learn's LogisticRegression with the lbfgs solver and L2 penalty. Features were not standardised, as the binary and log-transformed continuous features operate on comparable scales. The 18-dimensional feature vector comprises: log-enrollment, duration in months, placebo-controlled, double-blind, industry sponsor, log-number of sites, five one-hot endpoint type indicators (MACE, heart failure hospitalisation, cardiovascular death, all-cause mortality, renal, surrogate), four drug class indicators (SGLT2 inhibitor, non-steroidal MRA, GLP-1 receptor agonist, PCSK9 inhibitor, statin), DSMB presence, and active comparator. The model produces a probability estimate via the logistic sigmoid function:

*p = 1 / (1 + exp(-(beta_0 + sum(beta_i * x_i))))*

The model coefficients are fully embedded in the tool and visible to users through the feature decomposition display, which shows the contribution of each feature to the final logit score. This transparency allows users to understand which design characteristics are driving the prediction for any specific trial.

#### Ensemble

The three components are combined using fixed weights: Bayesian borrowing 0.40, conditional power 0.35, and meta-regression 0.25. These weights were selected based on the following rationale. Bayesian borrowing receives the highest weight because it incorporates the most direct evidence — the actual outcomes of trials with similar drug classes, endpoints, and populations. Conditional power receives the second-highest weight because adequate statistical power is a necessary (though not sufficient) condition for trial success, and it captures information about sample size adequacy that the other components do not explicitly model. Meta-regression receives the lowest weight because, while it captures systematic associations between design features and outcomes, logistic regression on 18 features with 784 observations is susceptible to overfitting and may not generalise as well to novel trial designs.

When a component is unavailable (e.g., insufficient similar trials for Bayesian borrowing), the remaining components' weights are proportionally rescaled to maintain a sum of 1.0. The ensemble probability is:

*P_ensemble = (w_B * P_bayesian + w_P * P_power + w_R * P_regression) / (w_B + w_P + w_R)*

The ensemble probability is classified into three tiers: High (>0.6), Moderate (0.3-0.6), and Low (<0.3).

### Validation
Temporal split: trials with primary completion before 2020-01-01 (training, n=651) vs. on/after (testing, n=133). Metrics: AUC, Brier score, calibration slope (computed via logistic regression of outcomes on logit-transformed predicted probabilities). Platt scaling recalibration was fitted on the training split to correct the mapping between raw ensemble scores and observed outcome frequencies. The temporal split ensures that the validation set reflects contemporary cardiovascular trial design and therapeutic landscape, avoiding information leakage from future trials. In-sample metrics are also reported for completeness but should not be interpreted as estimates of generalisation performance. A separate coronary artery disease (CAD) configuration was trained on 90 trials specific to ischaemic heart disease and evaluated using the same temporal split methodology.

### Implementation
Single-file HTML application using vanilla JavaScript, Plotly.js for visualisation, and optional WebR v0.4.4 for in-browser R cross-validation. The tool fetches trial data from the ClinicalTrials.gov API v2 at runtime. All computation occurs client-side — no data leaves the user's browser. The application supports PDF export via html2canvas and jsPDF, TruthCert provenance bundles (machine-readable JSON records of all inputs, coefficients, and outputs for any prediction), and a patient-friendly display mode that translates probabilities into plain-language risk descriptions. Source code is available at https://github.com/mahmood726-cyber/cardiooracle under an open-access licence.

## Results

### Training Data
A total of 1,259 Phase 2/3, Phase 3, and Phase 3/4 cardiovascular trials were extracted from AACT. After labeling, 784 trials were included (534 success [68.1%], 225 failure [28.7%], 25 safety failure [3.2%]). The majority (765/784, 97.6%) were labeled via Tier 1 (p-value based), with 19 labeled via Tier 3 (manual curation of landmark trials).

The training corpus spanned from 1990 to 2024. By era, 289 trials (36.9%) had start dates before 2010, 389 (49.6%) between 2010 and 2017, and 106 (13.5%) from 2018 onwards. Industry-sponsored trials predominated (702/784, 89.5%), consistent with the pharmaceutical industry's central role in cardiovascular drug development. The median enrollment was 514 participants (mean 1,724), reflecting the wide range from smaller Phase 2/3 studies to mega-trials exceeding 10,000 participants.

Drug class distribution was heterogeneous. The most represented classes were GLP-1 receptor agonists (129 trials, 16.5%), SGLT2 inhibitors (89, 11.4%), and angiotensin receptor blockers (39, 5.0%), with 464 trials (59.2%) classified under other or mixed drug classes. Endpoint type distribution was dominated by surrogate endpoints (387, 49.4%) and other composite or non-standard endpoints (321, 41.0%), with hard clinical endpoints including MACE (26, 3.3%), cardiovascular death (21, 2.7%), all-cause mortality (15, 1.9%), renal (10, 1.3%), and heart failure hospitalisation (4, 0.5%).

### Model Performance

| Metric | In-sample (n=784) | Temporal test (n=133) |
|--------|-------------------|----------------------|
| AUC | 0.787 | 0.745 |
| Brier score | 0.169 | 0.196 |
| Calibration slope | — | 0.875 |

The dedicated CAD configuration (90 trials) achieved AUC 0.843 on the temporal holdout set, likely reflecting the more homogeneous trial population and endpoint landscape within ischaemic heart disease.

### Feature Importance
The five most influential features from the logistic regression coefficients (by absolute magnitude) were:

1. **Industry sponsorship** (coefficient +1.33): Industry-sponsored trials were substantially more likely to succeed, likely reflecting more rigorous dose-finding in Phase 2, better-resourced site management, and selective advancement of compounds with strong preclinical and Phase 2 signals.
2. **All-cause mortality endpoint** (coefficient -0.97): Trials targeting all-cause mortality were significantly less likely to succeed, consistent with the well-recognised difficulty of demonstrating mortality reductions in an era of optimised background therapy.
3. **Surrogate endpoint** (coefficient +0.75): Trials with surrogate endpoints (e.g., blood pressure reduction, LDL lowering, HbA1c change) were more likely to succeed, reflecting the larger effect sizes and smaller sample sizes typical of surrogate-endpoint trials.
4. **DSMB presence** (coefficient -0.59): Trials with a Data Safety Monitoring Board were less likely to succeed. This counterintuitive association likely reflects confounding: DSMBs are mandated for trials assessing hard clinical endpoints with long follow-up, which are inherently more difficult to win.
5. **Heart failure hospitalisation endpoint** (coefficient +0.50): Trials targeting heart failure hospitalisation as the primary endpoint were more likely to succeed, consistent with the recent wave of positive SGLT2 inhibitor and ARNI trials in this endpoint category.

### Case Studies

We illustrate CardioOracle's predictions using three trials from the temporal holdout set (all with primary completion dates after 1 January 2020), ensuring no information leakage from the training corpus.

**Case 1: DELIVER (NCT03619213) — Correct positive prediction.**
DELIVER was a Phase 3, industry-sponsored, double-blind, placebo-controlled trial of dapagliflozin (SGLT2 inhibitor) in 6,263 patients with heart failure with preserved ejection fraction, with a primary composite endpoint of cardiovascular death or worsening heart failure. CardioOracle assigned an ensemble probability of 64.8%, classified as High confidence. The trial was positive (HR 0.82, p<0.001) [Solomon et al., *New England Journal of Medicine* 2022]. Key drivers of the positive prediction included the SGLT2 inhibitor drug class (strong historical success rate), industry sponsorship, large enrollment, and placebo-controlled design.

**Case 2: EMPACT-MI (NCT04509674) — Correct negative prediction.**
EMPACT-MI was a Phase 3, industry-sponsored, double-blind, placebo-controlled trial of empagliflozin (SGLT2 inhibitor) in patients hospitalised for acute myocardial infarction, with a primary composite endpoint of first hospitalisation for heart failure or all-cause death. CardioOracle assigned an ensemble probability of 38.7%, classified as Moderate. The trial was negative (HR 0.90, p=0.21) [Udell et al., *New England Journal of Medicine* 2024]. Despite the strong SGLT2 inhibitor class signal, the prediction was tempered by the acute post-MI population (limited historical precedent), the challenging composite endpoint combining heart failure hospitalisation with all-cause mortality, and the relatively low expected event rate in this population.

**Case 3: FINEARTS-HF (NCT04435626) — Correct positive prediction.**
FINEARTS-HF was a Phase 3, industry-sponsored, double-blind, placebo-controlled trial of finerenone (non-steroidal MRA) in 6,016 patients with heart failure and a mildly reduced or preserved ejection fraction, with a primary composite endpoint of cardiovascular death or total heart failure events. CardioOracle assigned an ensemble probability of 64.0%, classified as High confidence. The trial was positive (HR 0.84, p=0.007) [Solomon et al., *New England Journal of Medicine* 2024]. The prediction was supported by the emerging non-steroidal MRA evidence base (FIDELIO-DKD, FIGARO-DKD), large enrollment, and the heart failure endpoint category's favourable historical track record.

## Discussion

CardioOracle represents, to our knowledge, the first open-access, browser-based tool for predicting cardiovascular trial outcomes using a transparent, validated ensemble of historical borrowing, power analysis, and design-feature regression. By making its training data, model coefficients, and prediction provenance fully accessible, the tool addresses a longstanding gap between the sophisticated internal prediction capabilities of pharmaceutical companies and the limited resources available to academic researchers, funders, and regulators who must also make decisions about trial investment and design.

### Comparison with Existing Approaches

The current landscape of trial outcome prediction is dominated by approaches that sacrifice either transparency or accessibility, or both. Expert elicitation panels, while drawing on deep therapeutic knowledge, are subjective, poorly calibrated, and non-reproducible [Tetlock, *Expert Political Judgment* 2005]. Prediction markets offer collective intelligence but require active participation from knowledgeable traders and have been implemented primarily within individual pharmaceutical companies [Kaye et al., *Clinical Pharmacology and Therapeutics* 2019]. Machine learning approaches trained on ClinicalTrials.gov data have been described in the literature [Lo et al., *Drug Discovery Today* 2019; Feijoo et al., *BMC Medical Informatics and Decision Making* 2020], but none provide a publicly accessible tool with embedded coefficients and exportable provenance. Commercial platforms such as Informa's Citeline and Evaluate Pharma offer trial success probability estimates but are subscription-based and do not disclose their methodologies.

CardioOracle's ensemble architecture offers a distinct advantage over single-model approaches. The Bayesian borrowing component provides a historically grounded prior informed by the most relevant completed trials, while conditional power captures information about sample size adequacy that purely outcome-based models ignore. The meta-regression component identifies systematic design-level risk factors. By weighting and combining these three perspectives, the ensemble produces predictions that are more robust to individual component failures than any single approach.

### Clinical Utility

We envision three primary use cases. First, **trial planners** can use CardioOracle during protocol development to identify design features that may reduce the probability of success (e.g., insufficient enrollment for a hard clinical endpoint, absence of placebo control) and to benchmark their design against historical analogues. The power curve visualisation is particularly informative for sensitivity analysis around the assumed treatment effect. Second, **funders and portfolio managers** can use the tool for systematic prioritisation among competing trial proposals, supplementing traditional expert review with quantitative probability estimates. Third, **regulators and health technology assessment bodies** can use CardioOracle to contextualise trial results within the broader landscape of similar completed studies, understanding whether a positive or negative result was expected given the trial's design and therapeutic context.

### Limitations

Several important limitations must be acknowledged. First, the raw calibration slope on the temporal holdout set was 0.194 (OLS metric), indicating overconfident predicted probabilities. After Platt scaling recalibration, the logistic calibration slope improved to 0.874, within the acceptable range (0.8-1.2). However, with only 133 test trials, the calibration estimate remains noisy (estimated SE ~0.15). The discrimination metric (AUC = 0.745) provides a more stable measure of predictive utility. Predicted probabilities should be interpreted as relative rankings; the recalibrated absolute probabilities carry meaningful uncertainty.

Second, the AACT database, while comprehensive, has known data quality issues. Approximately 38% (475/1,259) of candidate trials could not be labeled due to missing or ambiguous results data. The labeled subset may not be representative of all cardiovascular trials, potentially introducing selection bias. Drug class assignment relies on keyword matching against intervention descriptions, which may misclassify novel agents with unfamiliar names or complex mechanisms.

Third, the conditional power component uses simplified assumptions. The event rate of 70% of enrollment for time-to-event endpoints is a crude approximation that does not account for varying follow-up durations, competing risks, or endpoint-specific event rates. The assumed control event rates for binary endpoints are similarly stylised. More sophisticated power calculations that incorporate trial-specific parameters would improve this component.

Fourth, success is defined strictly by the primary endpoint. Trials with positive secondary endpoints but a negative primary result (such as DECLARE-TIMI 58, which showed cardiovascular benefit in a heart failure subgroup despite a neutral MACE result) are labeled as failures. This binary classification obscures the nuanced reality of trial outcomes.

Fifth, the training corpus is dominated by industry-sponsored trials (89.5%) and surrogate endpoints (49.4%), which may limit generalisability to academic-sponsored trials or trials with hard clinical endpoints that have different structural characteristics.

### Ethical Considerations

The availability of an open-access trial prediction tool raises important ethical questions. Could a high CardioOracle probability estimate inappropriately encourage continuation of a trial that should be stopped? Could a low estimate discourage sponsors from pursuing a trial that might succeed? We emphasise that CardioOracle provides probabilistic estimates based on historical patterns, not deterministic forecasts. The tool should be used as one input among many in trial design and investment decisions, not as a substitute for clinical judgement, regulatory guidance, or formal sample size calculations. The transparency of the model — including its known limitations and calibration issues — is itself an ethical safeguard, as it empowers users to critically evaluate the predictions rather than accepting them as authoritative.

### Future Directions

Several enhancements are planned. Additional therapeutic area configurations (arrhythmia/atrial fibrillation, pulmonary hypertension, peripheral vascular disease) will broaden the tool's applicability. Improved calibration via Platt scaling, trained on the temporal holdout set, should narrow the gap between predicted and observed probabilities. A living update mechanism that periodically queries ClinicalTrials.gov for newly posted results would allow the training corpus to grow over time, improving predictions for emerging drug classes. Integration with natural language processing of protocol documents could capture design features not available in structured registry fields. Finally, formal benchmarking against expert panels and prediction markets on a prospective cohort of cardiovascular trials would provide the strongest evidence of the tool's added value.

## Conclusions

CardioOracle is the first open-access, browser-based tool for predicting cardiovascular trial outcomes using a hybrid ensemble of Bayesian historical borrowing, conditional power analysis, and logistic meta-regression. Trained on 651 Phase 3 CV trials from AACT and temporally validated on 133 post-2020 trials (AUC = 0.745), it provides probabilistic success estimates for prospective trials based on design features alone. The tool democratises trial outcome prediction — previously limited to industry analytics teams with proprietary databases — and may assist investigators, funders, and regulators in evidence-informed trial design and portfolio prioritisation.

## Data Availability

All training data, model coefficients, and source code are available at https://github.com/mahmood726-cyber/cardiooracle. The labeled dataset is deposited at [ZENODO DOI].

## Funding

No external funding was received for this work.

## Competing interests

The author declares no competing interests. CardioOracle is not affiliated with or endorsed by any pharmaceutical company, regulatory agency, or trial sponsor.

## References

1. Roth GA, Mensah GA, Johnson CO, et al. Global Burden of Cardiovascular Diseases and Risk Factors, 1990-2019: Update From the GBD 2019 Study. *Journal of the American College of Cardiology*. 2020;76(25):2982-3021.

2. Wouters OJ, McKee M, Luyten J. Estimated Research and Development Investment Needed to Bring a New Medicine to Market, 2009-2018. *JAMA*. 2020;323(9):844-853.

3. DiMasi JA, Grabowski HG, Hansen RW. Innovation in the pharmaceutical industry: New estimates of R&D costs. *Journal of Health Economics*. 2016;47:20-33.

4. Hay M, Thomas DW, Craighead JL, Economides C, Rosenthal J. Clinical development success rates for investigational drugs. *Nature Biotechnology*. 2014;32(1):40-51.

5. Wong CH, Siah KW, Lo AW. Estimation of clinical trial success rates and related parameters. *Biostatistics*. 2019;20(2):273-286.

6. Pfeffer MA, Claggett B, Assmann SF, et al. Regional Variation in Patients and Outcomes in the Treatment of Preserved Cardiac Function Heart Failure With an Aldosterone Antagonist (TOPCAT) Trial. *Circulation*. 2015;131(1):34-42.

7. Solomon SD, McMurray JJV, Anand IS, et al. Angiotensin-Neprilysin Inhibition in Heart Failure with Preserved Ejection Fraction. *New England Journal of Medicine*. 2019;381(17):1609-1620.

8. Pangalos MN, Schechter LE, Bhangoo AS. Drug development for CNS disorders: strategies for balancing risk and reducing attrition. *Nature Reviews Drug Discovery*. 2007;6(7):521-532.

9. Lo AW, Siah KW, Wong CH. Machine learning with statistical imputation for predicting drug approvals. *Harvard Data Science Review*. 2019;1(1).

10. Feijoo F, Palopoli M, Bernstein J, Schabel A, Dargan R. Key indicators of phase transition for clinical trials through machine learning. *Drug Discovery Today*. 2020;25(2):414-421.

11. Schoenfeld DA. The Asymptotic Properties of Nonparametric Tests for Comparing Survival Distributions. *Biometrika*. 1981;68(1):316-319.

12. Solomon SD, McMurray JJV, Claggett B, et al. Dapagliflozin in Heart Failure with Mildly Reduced or Preserved Ejection Fraction. *New England Journal of Medicine*. 2022;387(12):1089-1098.

13. Udell JA, Jones WS, Petrie MC, et al. Empagliflozin after Acute Myocardial Infarction. *New England Journal of Medicine*. 2024;390(16):1455-1466.

14. Solomon SD, McMurray JJV, Vaduganathan M, et al. Finerenone in Heart Failure with Mildly Reduced or Preserved Ejection Fraction. *New England Journal of Medicine*. 2024;391(16):1475-1485.

15. Platt JC. Probabilistic Outputs for Support Vector Machines and Comparisons to Regularized Likelihood Methods. In: Smola AJ, Bartlett PL, Scholkopf B, Schuurmans D, eds. *Advances in Large Margin Classifiers*. MIT Press; 1999:61-74.

16. DerSimonian R, Laird N. Meta-analysis in clinical trials. *Controlled Clinical Trials*. 1986;7(3):177-188.

17. Pocock SJ, Assmann SE, Enos LE, Kasten LE. Subgroup analysis, covariate adjustment and baseline comparisons in clinical trial reporting: current practice and problems. *Statistics in Medicine*. 2002;21(19):2917-2930.

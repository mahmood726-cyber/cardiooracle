[DATE]

The Editor
The Lancet Digital Health

Dear Editor,

We submit the manuscript **"CardioOracle: An Open-Access Browser-Based Cardiovascular Trial Outcome Predictor Using Hybrid Bayesian-Machine Learning Ensemble Modelling"** for consideration in *The Lancet Digital Health*.

**The problem:** Over 60% of Phase 3 cardiovascular trials fail, costing billions in resources and exposing patients to ineffective interventions. Predicting trial outcomes before they conclude could inform better trial design, resource allocation, and go/no-go decisions — but existing prediction tools are proprietary and inaccessible.

**Our solution:** CardioOracle is the first open-access, browser-based tool that predicts cardiovascular trial success using a hybrid ensemble of three complementary approaches: Bayesian historical borrowing (weight 0.40), conditional power analysis (0.30), and logistic meta-regression (0.30). Users enter an NCT ID or design parameters and receive a probabilistic prediction with component-level transparency.

**Key results:**
- Training corpus: 651 labeled Phase 3 CV trials from the AACT database
- Temporal validation (post-2020 holdout, n=133): AUC = 0.745, Brier score = 0.196
- Three therapeutic area configurations: cardiorenal, coronary artery disease, atrial fibrillation
- Case studies on DELIVER, FINEARTS-HF, and EMPACT-MI demonstrate clinical utility
- 25 prospective predictions on currently recruiting Phase 3 CV trials filed with timestamps for future validation

**Lancet Digital Health fit:** This tool addresses the journal's focus on digital innovation that improves health outcomes. By democratising trial outcome prediction — currently available only to industry analytics teams with proprietary databases — CardioOracle enables evidence-informed trial design for academic investigators, funders, and regulators worldwide.

The manuscript has not been submitted elsewhere. The tool and all data are freely available at https://github.com/mahmood726-cyber/cardiooracle.

Yours sincerely,

Mahmood Ahmad
Royal Free Hospital, London, UK
mahmood.ahmad2@nhs.net

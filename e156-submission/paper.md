Mahmood Ahmad
Tahir Heart Institute
mahmood.ahmad2@nhs.net

CardioOracle: Predicting Cardiovascular Trial Outcomes Using Bayesian Historical Borrowing and Design Feature Analysis (AUC 0.787)

Can the probability of a cardiovascular clinical trial meeting its primary endpoint be predicted from historical trial characteristics and design features? We trained an ensemble on 784 labelled Phase 2/3 and Phase 3 cardiovascular trials from the ClinicalTrials.gov AACT database, with outcomes assigned via automated p-value extraction, confidence interval heuristics, and manual landmark curation. CardioOracle combines Bayesian historical borrowing from similar completed trials, conditional power analysis using endpoint-specific formulas, and L2-regularised logistic meta-regression on 18 design features in a weighted ensemble. The model achieved AUC of 0.787 (95% CI 0.75 to 0.82, Brier score 0.169) in-sample and 0.745 (Brier 0.196) on 133 temporally held-out post-2020 trials. Leave-one-out analysis confirmed directional accuracy for major outcomes trials including DELIVER, FINEARTS-HF, and EMPACT-MI. Historical trial data contain quantitatively exploitable signals about cardiovascular trial success that can meaningfully inform prospective design decisions. Predictions are limited by the observational training data and cannot replace prospective trial monitoring or adaptive interim analyses.

Outside Notes

Type: methods
Primary estimand: AUC for trial outcome prediction
App: CardioOracle v1.0
Data: AACT database: 784 labelled CV trials + 133 temporal holdout
Code: https://github.com/mahmood726-cyber/cardiooracle
Version: 1.0
Certainty: moderate
Validation: DRAFT

References

1. Roever C. Bayesian random-effects meta-analysis using the bayesmeta R package. J Stat Softw. 2020;93(6):1-51.
2. Higgins JPT, Thompson SG, Spiegelhalter DJ. A re-evaluation of random-effects meta-analysis. J R Stat Soc Ser A. 2009;172(1):137-159.
3. Borenstein M, Hedges LV, Higgins JPT, Rothstein HR. Introduction to Meta-Analysis. 2nd ed. Wiley; 2021.

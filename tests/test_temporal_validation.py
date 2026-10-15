"""Regression tests for temporal leakage, ROC ties, and calibration.

No AACT access is required; all fixtures are synthetic.
"""
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from curate.fit_model import (
    FEATURE_NAMES,
    _compute_auc,
    _calibration_slope,
    _historical_rates_from_reference,
    compute_temporal_split_metrics,
)


def trial(i, year, success, cls="sglt2i", completion=True):
    return {
        "nct_id": f"NCT{i:08d}",
        "label": "success" if success else "failure",
        "primary_completion_date": f"{year}-06-30" if completion else None,
        "start_year": year - 3,
        "enrollment": 180 + 91 * i,
        "duration_months": 10 + 3 * (i % 5),
        "placebo_controlled": i % 2 == 0,
        "double_blind": i % 3 == 0,
        "is_industry": i % 3 != 0,
        "num_sites": 3 + 7 * i,
        "multi_regional": i % 4 == 0,
        "num_arms": 2,
        "has_dsmb": i % 2 == 0,
        "endpoint_type": "mace" if i % 2 else "hf_hosp",
        "drug_class": cls,
        # Deliberately adversarial: precomputed feature contains the label.
        "historical_class_rate": float(success),
    }


def make_trials():
    training = [trial(i, 2012 + i, i % 2 == 0,
                      "sglt2i" if i % 2 else "arni") for i in range(8)]
    testing = [trial(i, 2020 + (i - 8), i % 2 == 0,
                     "sglt2i" if i % 2 else "arni") for i in range(8, 12)]
    return training + testing


def test_roc_auc_ties_equal_half_and_independent_of_row_order():
    assert _compute_auc(np.array([1, 0]), np.array([0.5, 0.5])) == 0.5
    assert _compute_auc(np.array([0, 1]), np.array([0.5, 0.5])) == 0.5
    assert _compute_auc(np.array([0, 1, 0, 1]),
                        np.array([0.1, 0.5, 0.5, 0.9])) == pytest.approx(0.875)
    assert _compute_auc(np.array([1, 0]), np.array([0.9, 0.1])) == 1.0
    assert _compute_auc(np.array([1, 0]), np.array([0.1, 0.9])) == 0.0
    assert np.isnan(_compute_auc(np.array([1, 1]), np.array([0.4, 0.6])))


@pytest.mark.parametrize("scores", [[0.5, float("nan")], [0.3, float("inf")]])
def test_roc_auc_rejects_nonfinite_scores(scores):
    with pytest.raises(ValueError, match="finite"):
        _compute_auc(np.array([1, 0]), np.array(scores))


def test_historical_rates_exclude_own_outcome_and_external_target_encoding():
    baseline = [
        trial(0, 2018, True, "sglt2i"),
        trial(1, 2018, False, "sglt2i"),
    ]
    loo = _historical_rates_from_reference(baseline, baseline, leave_one_out=True)
    assert [t["historical_class_rate"] for t in loo] == [0.0, 1.0]
    new = [trial(3, 2025, False, "sglt2i")]
    predicted = _historical_rates_from_reference(baseline, new)
    assert predicted[0]["historical_class_rate"] == 0.5


def test_test_labels_and_all_cohort_coefficients_cannot_leak_into_predictions():
    base = make_trials()
    v1 = compute_temporal_split_metrics(base, {"intercept": 10000},
                                        FEATURE_NAMES)
    modified = [dict(t) for t in base]
    for t in modified:
        if int(t["primary_completion_date"][:4]) >= 2020:
            t["label"] = "failure" if t["label"] == "success" else "success"
            t["historical_class_rate"] = 100.0  # tainted external feature
    v2 = compute_temporal_split_metrics(modified, {"intercept": -10000},
                                        FEATURE_NAMES)
    assert v1["validation_status"] == "ok"
    assert v1["n_train"] == 8
    assert v1["n_test"] == 4
    p1 = [v["y_prob"] for v in v1["trial_predictions"] if v["split"] == "test"]
    p2 = [v["y_prob"] for v in v2["trial_predictions"] if v["split"] == "test"]
    assert p1 == pytest.approx(p2, abs=1e-12)
    assert all(0 < p < 1 for p in p1)


def test_missing_completion_date_excluded_from_temporal_validation():
    trials = make_trials()
    trials.append(trial(20, 2025, True, completion=False))
    report = compute_temporal_split_metrics(trials, {}, FEATURE_NAMES)
    assert report["n_train"] == 8
    assert report["n_test"] == 4
    assert report["n_excluded_missing_date"] == 1
    assert len(report["trial_predictions"]) == 12


def test_single_class_test_reports_auc_unavailable():
    trials = make_trials()
    for t in trials:
        if t["primary_completion_date"] >= "2020-01-01":
            t["label"] = "failure"
    report = compute_temporal_split_metrics(trials, {}, FEATURE_NAMES)
    assert report["validation_status"] == "single_class_test_cohort"
    assert report["test_metrics"]["auc"] is None
    assert report["test_metrics"]["brier"] is not None


def test_calibration_slope_is_logistic_not_ordinary_least_squares():
    actual = np.array([0, 1, 0, 1, 0, 1, 0, 1], dtype=float)
    probabilities = np.array([.12, .64, .42, .82, .32, .55, .27, .71])
    logits = np.log(probabilities / (1 - probabilities))
    expected = LogisticRegression(penalty=None, solver="lbfgs",
                                  max_iter=2000, tol=1e-9)
    expected.fit(logits.reshape(-1, 1), actual)
    observed = _calibration_slope(actual, probabilities)
    assert observed == pytest.approx(float(expected.coef_[0][0]), abs=1e-6)
    assert _calibration_slope(np.array([1, 1]), np.array([.4, .7])) is None

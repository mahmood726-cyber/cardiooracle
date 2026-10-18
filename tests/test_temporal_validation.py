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


# ---------------------------------------------------------------------------
# Original March 2026 frozen 25-study cohort: documentary scientific hold.
#
# These tests document NECESSARY evidence fields for eventual independent
# adjudication. They neither authenticate reviewers/sources/timestamps nor
# establish clinical validity; the frozen 25 predictions remain immutable.
# ---------------------------------------------------------------------------

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

_FROZEN_25_BLOB = "d61e874de348d8840317417848b51514ae272c8f"
_REVIEW_REQUIRED = (
    "adjudicated_outcome", "tested_intervention", "tested_comparator",
    "prespecified_primary_endpoint", "hypothesis", "effect_direction",
    "multiplicity_plan", "protocol_url", "protocol_sha256",
    "registry_vintage_url", "registry_vintage_sha256",
    "registry_vintage_posted_at", "results_url", "results_sha256",
    "results_first_public_at", "reviewer_one", "reviewer_two",
    "external_forecast_anchor_url",
)
_OUTCOME_LABELS = {"success", "failure", "safety_failure"}


def _parse_utc_timestamp(raw):
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        return None


def _source_documentation_gate(archive, reviews):
    """Screen completeness of prospective-adjudication PAPERWORK only.

    Passing this function does not authenticate sources, prove blinded
    adjudication, or establish clinical prediction validity.
    """
    trials = archive["trials"]
    ids = [t["nct_id"] for t in trials]
    if (len(ids) != 25 or len(set(ids)) != 25 or
            any(not re.fullmatch(r"NCT[0-9]{8}", n) for n in ids)):
        raise ValueError("the original, unique 25-trial census is required")
    if not isinstance(reviews, dict) or set(reviews) - set(ids):
        raise ValueError("reviews must refer only to the original 25 trials")
    lock = _parse_utc_timestamp(archive["generated"])
    if lock is None:
        raise ValueError("original forecast timestamp is malformed")
    documented = 0
    prelock_disclosures = 0
    for nct_id in ids:
        record = reviews.get(nct_id)
        if not isinstance(record, dict):
            continue
        if any(not isinstance(record.get(k), str) or
               not record[k].strip() for k in _REVIEW_REQUIRED):
            continue
        if record["adjudicated_outcome"] not in _OUTCOME_LABELS:
            continue
        if record["reviewer_one"] == record["reviewer_two"]:
            continue
        if any(not re.fullmatch(r"[a-fA-F0-9]{64}", record[k]) for k in
               ("protocol_sha256", "registry_vintage_sha256", "results_sha256")):
            continue
        if any(not record[k].startswith("https://") for k in
               ("protocol_url", "registry_vintage_url", "results_url",
                "external_forecast_anchor_url")):
            continue
        version_date = _parse_utc_timestamp(record["registry_vintage_posted_at"])
        disclosure_date = _parse_utc_timestamp(record["results_first_public_at"])
        if version_date is None or disclosure_date is None:
            continue
        if version_date > lock:
            continue  # later registry versions are not as-of evidence
        if disclosure_date <= lock:
            prelock_disclosures += 1
            continue  # already public outcomes cannot support prospective accuracy
        documented += 1
    return {
        "total_frozen_trials": len(ids),
        "documented_source_records": documented,
        "unresolved_or_ineligible": len(ids) - documented,
        "prelock_results_flagged": prelock_disclosures,
        "ready_for_independent_evidence_review": documented == len(ids),
        # Source authenticity, independent human review and external timestamp
        # authority are NOT verified by this structural screen.
        "clinically_validated": False,
    }


def _frozen25_archive():
    raw = (Path(__file__).resolve().parent.parent /
           "prospective_predictions_20260325.json").read_bytes()
    git_blob = hashlib.sha1(
        f"blob {len(raw)}\0".encode("ascii") + raw
    ).hexdigest()
    assert git_blob == _FROZEN_25_BLOB
    return json.loads(raw)


def test_frozen25_predictions_are_not_observed_trial_successes():
    archive = _frozen25_archive()
    trials = archive["trials"]
    assert archive["generated"] == "2026-03-25T10:43:16.485Z"
    assert len(trials) == archive["summary"]["total_trials"] == 25
    # "successful_predictions" counts generated forecasts, not clinical wins.
    assert archive["summary"]["successful_predictions"] == 25
    assert all(t["outcome"] is None and t["outcome_source"] is None and
               t["outcome_date"] is None for t in trials)
    assert all(0 <= t["prediction"]["p_success"] <= 1 for t in trials)
    report = _source_documentation_gate(archive, {})
    assert report["documented_source_records"] == 0
    assert report["unresolved_or_ineligible"] == 25
    assert not report["ready_for_independent_evidence_review"]
    assert not report["clinically_validated"]


def _fictional_review_metadata():
    # Deliberately fictitious fields only test the STRUCTURAL schema, not truth.
    return {
        "adjudicated_outcome": "success",
        "tested_intervention": "fictional intervention",
        "tested_comparator": "fictional comparator",
        "prespecified_primary_endpoint": "fictional endpoint",
        "hypothesis": "superiority",
        "effect_direction": "lower_is_better",
        "multiplicity_plan": "prespecified familywise plan",
        "protocol_url": "https://example.invalid/protocol",
        "protocol_sha256": "a" * 64,
        "registry_vintage_url": "https://example.invalid/registry-vintage",
        "registry_vintage_sha256": "b" * 64,
        "registry_vintage_posted_at": "2026-02-01T00:00:00Z",
        "results_url": "https://example.invalid/results",
        "results_sha256": "c" * 64,
        "results_first_public_at": "2026-06-01T00:00:00Z",
        "reviewer_one": "fictional-reviewer-one",
        "reviewer_two": "fictional-reviewer-two",
        "external_forecast_anchor_url": "https://example.invalid/anchor",
    }


def test_outcome_gate_abstains_on_p_value_only_prelock_or_late_vintage():
    archive = _frozen25_archive()
    nct_id = archive["trials"][0]["nct_id"]
    assert _source_documentation_gate(
        archive, {nct_id: {"p_value": "0.01", "adjudicated_outcome": "success"}}
    )["documented_source_records"] == 0
    fictional = _fictional_review_metadata()
    report = _source_documentation_gate(archive, {nct_id: fictional})
    assert report["documented_source_records"] == 1
    assert report["unresolved_or_ineligible"] == 24
    assert not report["clinically_validated"]
    prelock = dict(fictional, results_first_public_at="2026-01-01T00:00:00Z")
    report = _source_documentation_gate(archive, {nct_id: prelock})
    assert report["documented_source_records"] == 0
    assert report["prelock_results_flagged"] == 1
    late_vintage = dict(fictional, registry_vintage_posted_at="2026-07-01T00:00:00Z")
    assert _source_documentation_gate(archive, {nct_id: late_vintage})[
        "documented_source_records"
    ] == 0
    same_person = dict(fictional, reviewer_two="fictional-reviewer-one")
    assert _source_documentation_gate(archive, {nct_id: same_person})[
        "documented_source_records"
    ] == 0


def test_outcome_gate_requires_full_frozen_census_without_selection():
    archive = _frozen25_archive()
    with pytest.raises(ValueError, match="original"):
        _source_documentation_gate(dict(archive, trials=archive["trials"][:-1]), {})
    with pytest.raises(ValueError, match="original"):
        _source_documentation_gate(dict(archive, trials=archive["trials"][:-1] +
                                        [archive["trials"][0]]), {})
    with pytest.raises(ValueError, match="only"):
        _source_documentation_gate(archive, {"NCT99999999": _fictional_review_metadata()})
    # Even 25 superficially complete forms are NOT independent clinical review.
    all_fictional = {
        t["nct_id"]: _fictional_review_metadata() for t in archive["trials"]
    }
    report = _source_documentation_gate(archive, all_fictional)
    assert report["ready_for_independent_evidence_review"]
    assert not report["clinically_validated"]

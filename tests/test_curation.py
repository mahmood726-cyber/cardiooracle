"""
test_curation.py — Unit tests for CardioOracle curation helpers.

Tests cover only pure functions that require no database connection:
  - classify_drug         (from curate/shared.py)
  - classify_endpoint     (from curate/shared.py)
  - months_between        (from curate/extract_aact.py)
  - extract_population_tags (from curate/extract_aact.py)
  - label_trial           (from curate/label_outcomes.py)
"""

import sys
import os
from datetime import date
from pathlib import Path

import numpy as np

# Make both curate/ modules importable regardless of working directory.
_CURATE_DIR = str(Path(__file__).resolve().parent.parent / "curate")
if _CURATE_DIR not in sys.path:
    sys.path.insert(0, _CURATE_DIR)

from shared import classify_drug, classify_endpoint
from extract_aact import months_between, extract_population_tags
from label_outcomes import (
    label_trial,
    LABEL_SUCCESS,
    LABEL_FAILURE,
    LABEL_SAFETY_FAIL,
)
from fit_model import prepare_feature_matrix, fit_logistic_model, FEATURE_NAMES

import pytest


# ---------------------------------------------------------------------------
# TestClassifyDrug
# ---------------------------------------------------------------------------

class TestClassifyDrug:
    def test_empagliflozin(self):
        assert classify_drug("Empagliflozin 10 mg") == "sglt2i"

    def test_dapagliflozin(self):
        assert classify_drug("Dapagliflozin") == "sglt2i"

    def test_finerenone(self):
        assert classify_drug("finerenone 20 mg tablet") == "ns_mra"

    def test_sacubitril_valsartan(self):
        # "sacubitril" is in the arni drug list; slash-form also works
        assert classify_drug("sacubitril/valsartan") == "arni"

    def test_unknown(self):
        assert classify_drug("XYZ-9999 investigational compound") == "other"

    def test_case_insensitive(self):
        assert classify_drug("ATORVASTATIN") == "statin"

    def test_placebo(self):
        # Placebo contains no known drug name → "other"
        assert classify_drug("Placebo") == "other"


# ---------------------------------------------------------------------------
# TestClassifyEndpoint
# ---------------------------------------------------------------------------

class TestClassifyEndpoint:
    def test_mace(self):
        assert classify_endpoint("Major Adverse Cardiovascular Events (MACE)") == "mace"

    def test_hf_hospitalization(self):
        # Must return "hf_hosp", not any other category
        assert classify_endpoint("Heart failure hospitalization or CV death") == "hf_hosp"

    def test_cv_death(self):
        assert classify_endpoint("Cardiovascular death at 24 months") == "cv_death"

    def test_renal(self):
        assert classify_endpoint("Sustained decrease in eGFR of ≥40%") == "renal"

    def test_surrogate(self):
        assert classify_endpoint("Change in NT-proBNP from baseline") == "surrogate"

    def test_unknown(self):
        assert classify_endpoint("Quality of life score (EQ-5D)") == "other"

    def test_priority_mace_over_hf(self):
        # Text contains both MACE and heart failure; MACE must win (higher priority)
        text = "Composite of MACE including heart failure hospitalization"
        assert classify_endpoint(text) == "mace"


# ---------------------------------------------------------------------------
# TestMonthsBetween
# ---------------------------------------------------------------------------

class TestMonthsBetween:
    def test_one_year(self):
        start = date(2020, 1, 1)
        end = date(2021, 1, 1)
        result = months_between(start, end)
        assert result is not None
        assert abs(result - 12.0) <= 0.5

    def test_none_start(self):
        assert months_between(None, date(2021, 1, 1)) is None

    def test_same_date(self):
        d = date(2021, 6, 15)
        assert months_between(d, d) == 0.0


# ---------------------------------------------------------------------------
# TestExtractPopulationTags
# ---------------------------------------------------------------------------

class TestExtractPopulationTags:
    def test_hfref(self):
        text = (
            "Inclusion Criteria: Patients with reduced ejection fraction "
            "(LVEF ≤ 40%) and symptomatic heart failure."
        )
        tags = extract_population_tags(text)
        assert "HFrEF" in tags

    def test_diabetic_and_ckd(self):
        text = (
            "Patients with type 2 diabetes mellitus and chronic kidney disease "
            "(eGFR 25–60 mL/min/1.73 m²)."
        )
        tags = extract_population_tags(text)
        assert "diabetic" in tags
        assert "CKD" in tags

    def test_empty_string(self):
        assert extract_population_tags("") == []

    def test_none(self):
        assert extract_population_tags(None) == []


# ---------------------------------------------------------------------------
# TestLabelTrial
# ---------------------------------------------------------------------------

class TestLabelTrial:
    def _make_trial(
        self,
        status="Completed",
        why_stopped=None,
        p_value=None,
        param_type="Hazard Ratio",
        param_value=None,
        ci_lower=None,
        ci_upper=None,
    ):
        """Build a minimal trial dict for label_trial tests."""
        outcome = {
            "title": "Primary composite endpoint",
            "p_value": p_value,
            "param_type": param_type,
            "param_value": param_value,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "method": None,
        }
        return {
            "nct_id": "NCT00000000",
            "status": status,
            "why_stopped": why_stopped,
            "primary_outcomes": [outcome],
        }

    def test_tier1_significant_p(self):
        """p=0.001, HR=0.80, CI [0.65, 0.90] → SUCCESS, tier=1."""
        trial = self._make_trial(
            p_value=0.001,
            param_type="Hazard Ratio",
            param_value=0.80,
            ci_lower=0.65,
            ci_upper=0.90,
        )
        label, tier, reason = label_trial(trial)
        assert label == LABEL_SUCCESS
        assert tier == 1

    def test_tier1_nonsignificant(self):
        """p=0.42, HR=1.01, CI [0.85, 1.20] → FAILURE, tier=1."""
        trial = self._make_trial(
            p_value=0.42,
            param_type="Hazard Ratio",
            param_value=1.01,
            ci_lower=0.85,
            ci_upper=1.20,
        )
        label, tier, reason = label_trial(trial)
        assert label == LABEL_FAILURE
        assert tier == 1

    def test_terminated_futility(self):
        """Stopped for futility → FAILURE, tier=1."""
        trial = self._make_trial(
            status="Terminated",
            why_stopped="Stopped for futility based on interim analysis",
        )
        label, tier, reason = label_trial(trial)
        assert label == LABEL_FAILURE
        assert tier == 1

    def test_terminated_safety(self):
        """Stopped for safety → SAFETY_FAIL, tier=1."""
        trial = self._make_trial(
            status="Terminated",
            why_stopped="Safety concerns: increased adverse events observed",
        )
        label, tier, reason = label_trial(trial)
        assert label == LABEL_SAFETY_FAIL
        assert tier == 1

    def test_tier2_ci_excludes_one(self):
        """p=None, HR=0.75, CI [0.60, 0.95] → SUCCESS, tier=2."""
        trial = self._make_trial(
            p_value=None,
            param_type="Hazard Ratio",
            param_value=0.75,
            ci_lower=0.60,
            ci_upper=0.95,
        )
        label, tier, reason = label_trial(trial)
        assert label == LABEL_SUCCESS
        assert tier == 2

    def test_tier2_ci_includes_one(self):
        """p=None, HR=0.94, CI [0.80, 1.10] → FAILURE, tier=2."""
        trial = self._make_trial(
            p_value=None,
            param_type="Hazard Ratio",
            param_value=0.94,
            ci_lower=0.80,
            ci_upper=1.10,
        )
        label, tier, reason = label_trial(trial)
        assert label == LABEL_FAILURE
        assert tier == 2

    def test_unlabelable(self):
        """All None outcome fields → label=None, tier=None."""
        trial = {
            "nct_id": "NCT00000001",
            "status": "Completed",
            "why_stopped": None,
            "primary_outcomes": [
                {
                    "title": "Primary outcome",
                    "p_value": None,
                    "param_type": None,
                    "param_value": None,
                    "ci_lower": None,
                    "ci_upper": None,
                    "method": None,
                }
            ],
        }
        label, tier, reason = label_trial(trial)
        assert label is None
        assert tier is None


# ---------------------------------------------------------------------------
# Shared helper: build a minimal synthetic trial dict for model tests
# ---------------------------------------------------------------------------

def _make_synthetic_trial(label: str, seed_offset: int = 0) -> dict:
    """Return a minimal trial dict with all fields needed by prepare_feature_matrix."""
    rng = np.random.default_rng(42 + seed_offset)
    return {
        "nct_id": f"NCT{seed_offset:08d}",
        "label": label,
        "enrollment": int(rng.integers(50, 5000)),
        "duration_months": float(rng.integers(12, 72)),
        "placebo_controlled": bool(rng.integers(0, 2)),
        "double_blind": bool(rng.integers(0, 2)),
        "is_industry": bool(rng.integers(0, 2)),
        "num_sites": int(rng.integers(1, 300)),
        "multi_regional": bool(rng.integers(0, 2)),
        "num_arms": int(rng.integers(2, 4)),
        "has_dsmb": bool(rng.integers(0, 2)),
        "endpoint_type": rng.choice(["mace", "hf_hosp", "cv_death", "renal", "surrogate", "other"]),
        "drug_class": rng.choice(["sglt2i", "arni", "ns_mra", "statin", "other"]),
        "comparator_type": "placebo",
        "start_year": int(rng.integers(2000, 2023)),
        "population_tags": [],
        "historical_class_rate": float(rng.uniform(0.2, 0.7)),
    }


# ---------------------------------------------------------------------------
# TestFeatureMatrix
# ---------------------------------------------------------------------------

class TestFeatureMatrix:
    def test_basic_shape(self):
        """2 trials → X.shape[0]==2, len(feature_names)==X.shape[1], y[0]==1, y[1]==0."""
        trial_success = _make_synthetic_trial("success", seed_offset=0)
        trial_failure = _make_synthetic_trial("failure", seed_offset=1)

        X, y, feature_names = prepare_feature_matrix([trial_success, trial_failure])

        assert X.shape[0] == 2, f"Expected 2 rows, got {X.shape[0]}"
        assert X.shape[1] == len(FEATURE_NAMES), (
            f"Expected {len(FEATURE_NAMES)} columns, got {X.shape[1]}"
        )
        assert len(feature_names) == X.shape[1], (
            f"feature_names length {len(feature_names)} != X.shape[1] {X.shape[1]}"
        )
        assert y[0] == 1, "First trial (success) should have y=1"
        assert y[1] == 0, "Second trial (failure) should have y=0"
        assert X.dtype == float


# ---------------------------------------------------------------------------
# TestFitModel
# ---------------------------------------------------------------------------

class TestFitModel:
    def test_returns_coefficients(self):
        """100 synthetic trials → intercept + N named coefficients returned."""
        np.random.seed(42)

        trials = []
        for i in range(50):
            trials.append(_make_synthetic_trial("success", seed_offset=i))
        for i in range(50, 100):
            trials.append(_make_synthetic_trial("failure", seed_offset=i))

        X, y, feature_names = prepare_feature_matrix(trials)
        result = fit_logistic_model(X, y, feature_names)

        assert "coefficients" in result
        coef = result["coefficients"]

        # Must have intercept
        assert "intercept" in coef, "Missing 'intercept' in coefficients"

        # Must have one entry per feature
        assert len(coef) == len(FEATURE_NAMES) + 1, (
            f"Expected {len(FEATURE_NAMES) + 1} coefficients (intercept + features), "
            f"got {len(coef)}"
        )

        # All feature names must be present
        for fn in FEATURE_NAMES:
            assert fn in coef, f"Missing coefficient for feature '{fn}'"

        # In-sample metrics must be present and valid
        assert "insample_metrics" in result
        metrics = result["insample_metrics"]
        assert "auc" in metrics
        assert "brier" in metrics
        assert "n" in metrics
        assert metrics["n"] == 100
        assert 0.0 <= metrics["brier"] <= 1.0

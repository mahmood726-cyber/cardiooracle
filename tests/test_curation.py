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

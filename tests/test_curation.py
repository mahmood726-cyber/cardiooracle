"""
test_curation.py — Unit tests for CardioOracle curation helpers.

Tests cover only pure functions that require no database connection:
  - classify_drug   (from curate/shared.py)
  - classify_endpoint (from curate/shared.py)
  - months_between  (from curate/extract_aact.py)
  - extract_population_tags (from curate/extract_aact.py)
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

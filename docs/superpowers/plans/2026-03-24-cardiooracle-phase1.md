# CardioOracle Phase 1 (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working MVP — Python curation pipeline that extracts and labels CV trials from AACT, exports training data, and a single-file HTML app with the Predict tab (NCT ID lookup → P(success) prediction with Bayesian + conditional power + meta-regression ensemble).

**Architecture:** Two independent tracks. Track A: Python scripts query AACT PostgreSQL, label outcomes, fit logistic regression, export `training_data.json` + `model_coefficients.json`. Track B: Single-file HTML app embeds the exported data, fetches recruiting trials from CT.gov API v2, runs the 3-component prediction engine in JS, displays results with Plotly charts. Track B can start immediately using placeholder training data.

**Tech Stack:** Python 3.11+ (psycopg2, scikit-learn, pandas), single-file HTML (vanilla JS, Plotly.js CDN, CT.gov API v2), Selenium for testing.

**Spec:** `docs/superpowers/specs/2026-03-24-cardiooracle-design.md`

---

## File Map

| File | Responsibility | Track |
|------|---------------|-------|
| `curate/extract_aact.py` | Query AACT PostgreSQL, extract raw trial data | A |
| `curate/label_outcomes.py` | Tier 1/2/3 success/failure labeling | A |
| `curate/fit_model.py` | Fit logistic regression, compute priors + calibration | A |
| `curate/export_training.py` | Produce training_data.json + model_coefficients.json | A |
| `curate/validate_labels.py` | Cross-check labels against landmark_trials.json | A |
| `curate/shared.py` | DRUG_CLASS_MAP, ENDPOINT_TYPE_MAP, connection helpers | A |
| `data/landmark_trials.json` | Manually curated ~80 gold-standard trials with known outcomes | A |
| `data/configs/cardiorenal.json` | Therapeutic area config (drug classes, priors, endpoint types) | A+B |
| `data/training_data.json` | Exported labeled trials (output of pipeline) | A→B |
| `data/model_coefficients.json` | Exported model weights (output of pipeline) | A→B |
| `CardioOracle.html` | Single-file app: UI + prediction engine + CT.gov API | B |
| `tests/test_curation.py` | Unit tests for Python curation pipeline | A |
| `tests/test_prediction.py` | Selenium tests for HTML app Predict tab | B |
| `CLAUDE.md` | Project-level coding rules | - |

---

## Task 1: Project Scaffold + Configuration

**Files:**
- Create: `CLAUDE.md`
- Create: `curate/shared.py`
- Create: `data/configs/cardiorenal.json`
- Create: `curate/requirements.txt`

- [ ] **Step 1: Create CLAUDE.md**

```markdown
# CardioOracle — CLAUDE.md

## What this is
Browser-based cardiovascular trial outcome predictor. Hybrid Bayesian + ML model.
Single-file HTML app (~15-20K lines at maturity) + Python curation pipeline.

## Non-negotiables
- OA-only: all data from CT.gov / AACT (public domain)
- No secrets: AACT credentials in .env only, never in HTML or committed code
- Fail-closed: if similar trial count < 3, output INSUFFICIENT DATA
- Determinism: fixed similarity weights, reproducible predictions
- Test before done: run full test suite before declaring any task complete

## Key patterns
- Python: use `python` not `python3` (Windows)
- Template literals: never write literal `</script>` inside script blocks
- localStorage keys: prefix `cardiooracle_`
- Stats: use `?? fallback` not `|| fallback` for numeric values (zero is valid)

## File roles
- `curate/` — Python pipeline, runs offline, queries AACT, produces JSON
- `data/` — Pipeline outputs + configs, embedded into HTML
- `CardioOracle.html` — The app. Pure JS. No Python dependency at runtime.
- `tests/` — Python tests (pytest + Selenium)
```

- [ ] **Step 2: Create curate/requirements.txt**

```
psycopg2-binary>=2.9
pandas>=2.0
scikit-learn>=1.3
python-dotenv>=1.0
```

- [ ] **Step 3: Create curate/shared.py with DRUG_CLASS_MAP and ENDPOINT_TYPE_MAP**

```python
"""Shared constants and helpers for CardioOracle curation pipeline."""

import os
import re
from dotenv import load_dotenv

load_dotenv()

# --- AACT Connection ---
def get_aact_connection():
    """Return psycopg2 connection to AACT PostgreSQL."""
    import psycopg2
    return psycopg2.connect(
        host="aact-db.ctti-clinicaltrials.org",
        port=5432,
        database="aact",
        user=os.environ["AACT_USER"],
        password=os.environ["AACT_PASSWORD"],
    )


# --- Drug Class Taxonomy ---
DRUG_CLASS_MAP = {
    "sglt2i": {
        "label": "SGLT2 inhibitor",
        "drugs": ["empagliflozin", "dapagliflozin", "canagliflozin", "ertugliflozin",
                  "sotagliflozin", "ipragliflozin", "tofogliflozin", "luseogliflozin"],
    },
    "mra": {
        "label": "MRA (steroidal)",
        "drugs": ["spironolactone", "eplerenone"],
    },
    "ns_mra": {
        "label": "MRA (non-steroidal)",
        "drugs": ["finerenone", "esaxerenone", "apararenone", "ocedurenone"],
    },
    "arni": {
        "label": "ARNi",
        "drugs": ["sacubitril", "entresto", "sacubitril/valsartan"],
    },
    "arb": {
        "label": "ARB",
        "drugs": ["valsartan", "losartan", "candesartan", "irbesartan",
                  "telmisartan", "olmesartan", "azilsartan"],
    },
    "acei": {
        "label": "ACEi",
        "drugs": ["enalapril", "ramipril", "lisinopril", "perindopril",
                  "captopril", "quinapril", "benazepril", "fosinopril"],
    },
    "bb": {
        "label": "Beta-blocker",
        "drugs": ["carvedilol", "bisoprolol", "metoprolol", "nebivolol", "atenolol"],
    },
    "glp1ra": {
        "label": "GLP-1 RA",
        "drugs": ["semaglutide", "liraglutide", "dulaglutide", "exenatide",
                  "albiglutide", "lixisenatide", "tirzepatide"],
    },
    "pcsk9i": {
        "label": "PCSK9 inhibitor",
        "drugs": ["evolocumab", "alirocumab", "inclisiran"],
    },
    "statin": {
        "label": "Statin",
        "drugs": ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin",
                  "lovastatin", "fluvastatin", "pitavastatin"],
    },
    "anticoag": {
        "label": "Anticoagulant",
        "drugs": ["apixaban", "rivaroxaban", "edoxaban", "dabigatran", "warfarin"],
    },
    "antiplat": {
        "label": "Antiplatelet",
        "drugs": ["ticagrelor", "prasugrel", "clopidogrel", "aspirin", "cangrelor"],
    },
    "other": {
        "label": "Other/novel",
        "drugs": [],
    },
}


def classify_drug(intervention_name):
    """Map an intervention name to a drug class ID."""
    name = re.sub(r'\d+\s*(mg|mcg|ml|iu|units?)\b', '', intervention_name.lower()).strip()
    for class_id, info in DRUG_CLASS_MAP.items():
        if class_id == "other":
            continue
        for drug in info["drugs"]:
            if drug in name:
                return class_id
    return "other"


# --- Endpoint Type Taxonomy (priority-ordered) ---
ENDPOINT_TYPE_MAP = [
    ("mace", ["mace", "major adverse cardiovascular", "composite cardiovascular"]),
    ("hf_hosp", ["heart failure hospitalization", "hf hospitalization",
                 "worsening heart failure", "hf hospitalisation"]),
    ("cv_death", ["cardiovascular death", "cardiac death", "cv death",
                  "cardiovascular mortality"]),
    ("acm", ["all-cause mortality", "all cause mortality", "overall survival",
             "death from any cause"]),
    ("renal", ["egfr", "kidney", "renal", "dialysis", "eskd",
               "doubling of creatinine", "sustained decrease"]),
    ("surrogate", ["blood pressure", "ldl", "hba1c", "nt-probnp",
                   "ejection fraction", "6-minute walk", "biomarker"]),
]


def classify_endpoint(measure_text):
    """Map primary outcome measure text to endpoint type. Priority order."""
    text = measure_text.lower()
    for etype, keywords in ENDPOINT_TYPE_MAP:
        for kw in keywords:
            if kw in text:
                return etype
    return "other"
```

- [ ] **Step 4: Create data/configs/cardiorenal.json**

```json
{
  "id": "cardiorenal",
  "label": "Cardiorenal / Heart Failure",
  "description": "HF, CKD, MRA, SGLT2i, finerenone, ARNi",
  "condition_query": "heart failure OR cardiomyopathy OR chronic kidney disease OR cardiorenal",
  "mesh_terms": ["Heart Failure", "Cardiomyopathies", "Renal Insufficiency, Chronic",
                  "Diabetic Nephropathies", "Cardio-Renal Syndrome"],
  "priors": {
    "alpha": 4.5,
    "beta": 5.5,
    "comment": "~45% base success rate, equivalent to ~10 pseudo-trials"
  },
  "similarity_weights": {
    "drug_class": 0.30,
    "endpoint_type": 0.25,
    "comparator_type": 0.15,
    "population": 0.15,
    "era": 0.15
  },
  "ensemble_weights": {
    "bayesian": 0.40,
    "conditional_power": 0.35,
    "meta_regression": 0.25
  },
  "acceptance_criteria": {
    "min_auc": 0.65,
    "max_brier": 0.25,
    "calibration_slope_range": [0.8, 1.2]
  }
}
```

- [ ] **Step 5: Create .gitignore**

```
.env
__pycache__/
data/raw_trials.json
data/labeled_trials.json
*.pyc
```

- [ ] **Step 6: Commit scaffold**

```bash
cd /c/Models/CardioOracle
git init
git add CLAUDE.md curate/shared.py curate/requirements.txt data/configs/cardiorenal.json .gitignore
git commit -m "feat: project scaffold with CLAUDE.md, drug/endpoint taxonomy, cardiorenal config"
```

---

## Task 2: AACT Extraction Script

**Files:**
- Create: `curate/extract_aact.py`
- Test: `tests/test_curation.py` (first tests)

- [ ] **Step 1: Write failing test for extraction**

Create `tests/test_curation.py`:

```python
"""Tests for the CardioOracle curation pipeline."""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'curate'))

from shared import classify_drug, classify_endpoint


class TestClassifyDrug:
    def test_empagliflozin(self):
        assert classify_drug("Empagliflozin 10mg") == "sglt2i"

    def test_dapagliflozin(self):
        assert classify_drug("Dapagliflozin") == "sglt2i"

    def test_finerenone(self):
        assert classify_drug("Finerenone 20 mg") == "ns_mra"

    def test_sacubitril_valsartan(self):
        assert classify_drug("Sacubitril/Valsartan") == "arni"

    def test_unknown_drug(self):
        assert classify_drug("Experimental compound XYZ-999") == "other"

    def test_case_insensitive(self):
        assert classify_drug("EMPAGLIFLOZIN") == "sglt2i"

    def test_placebo(self):
        assert classify_drug("Placebo") == "other"


class TestClassifyEndpoint:
    def test_mace(self):
        assert classify_endpoint("Time to first MACE event") == "mace"

    def test_hf_hospitalization(self):
        assert classify_endpoint("Heart failure hospitalization or CV death") == "hf_hosp"

    def test_cv_death_standalone(self):
        assert classify_endpoint("Cardiovascular death") == "cv_death"

    def test_renal(self):
        assert classify_endpoint("Sustained decrease in eGFR") == "renal"

    def test_surrogate(self):
        assert classify_endpoint("Change in LDL cholesterol") == "surrogate"

    def test_unknown(self):
        assert classify_endpoint("Quality of life assessment") == "other"

    def test_priority_mace_over_hf(self):
        """MACE composites that mention HF should classify as MACE."""
        assert classify_endpoint("Major adverse cardiovascular events including HF hospitalization") == "mace"
```

- [ ] **Step 2: Run test to verify classify functions work**

```bash
cd /c/Models/CardioOracle
python -m pytest tests/test_curation.py -v
```
Expected: ALL PASS (shared.py already has the implementations from Task 1)

- [ ] **Step 3: Write extract_aact.py**

```python
"""Extract cardiovascular Phase 3 trial data from AACT PostgreSQL.

Usage: python curate/extract_aact.py [--output data/raw_trials.json] [--limit N]
"""
import argparse
import json
import sys
from datetime import date

from shared import get_aact_connection, classify_drug, classify_endpoint

EXTRACTION_QUERY = """
SELECT DISTINCT
    s.nct_id,
    s.brief_title,
    s.overall_status,
    s.phase,
    s.enrollment,
    s.enrollment_type,
    s.start_date,
    s.primary_completion_date,
    s.completion_date,
    s.study_type,
    s.source AS sponsor_name,
    s.source_class AS sponsor_class,
    s.has_dmc,
    s.why_stopped,
    d.allocation,
    d.masking,
    d.masking_description,
    d.intervention_model,
    d.number_of_arms
FROM ctgov.studies s
JOIN ctgov.designs d ON s.nct_id = d.nct_id
JOIN ctgov.conditions c ON s.nct_id = c.nct_id
WHERE s.study_type = 'Interventional'
  AND d.allocation = 'Randomized'
  AND (s.phase LIKE '%%Phase 3%%')
  AND s.enrollment >= 50
  AND (s.overall_status IN ('Completed', 'Terminated'))
  AND s.results_first_posted_date IS NOT NULL
  AND c.downcase_name SIMILAR TO %s
ORDER BY s.nct_id;
"""

CV_CONDITION_PATTERN = (
    '%(heart failure|cardiomyopath|myocardial infarction|coronary|'
    'atrial fibrillation|hypertension|atherosclero|angina|'
    'stroke|cerebrovascular|peripheral arter|aortic|'
    'chronic kidney|diabetic nephro|cardio.?renal)%'
)

OUTCOMES_QUERY = """
SELECT o.nct_id, o.outcome_type, o.title, o.time_frame,
       oa.p_value, oa.ci_lower_limit, oa.ci_upper_limit,
       oa.param_type, oa.method, oa.param_value_num
FROM ctgov.outcomes o
LEFT JOIN ctgov.outcome_analyses oa ON o.id = oa.outcome_id
WHERE o.nct_id = ANY(%s)
  AND o.outcome_type = 'Primary'
ORDER BY o.nct_id, o.id;
"""

INTERVENTIONS_QUERY = """
SELECT nct_id, intervention_type, name
FROM ctgov.interventions
WHERE nct_id = ANY(%s);
"""

FACILITIES_QUERY = """
SELECT nct_id, country, COUNT(*) as site_count
FROM ctgov.facilities
WHERE nct_id = ANY(%s)
GROUP BY nct_id, country;
"""

ELIGIBILITY_QUERY = """
SELECT nct_id, criteria
FROM ctgov.eligibilities
WHERE nct_id = ANY(%s);
"""


def parse_date(d):
    """Parse AACT date to ISO string. Returns None if unparseable."""
    if d is None:
        return None
    return d.isoformat() if isinstance(d, date) else str(d)


def months_between(start, end):
    """Compute months between two dates. Returns None if either is None."""
    if start is None or end is None:
        return None
    if isinstance(start, str):
        from datetime import datetime
        try:
            start = datetime.strptime(start[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    if isinstance(end, str):
        from datetime import datetime
        try:
            end = datetime.strptime(end[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    delta = end - start
    return round(delta.days / 30.44, 1)


def extract_population_tags(criteria_text):
    """Parse eligibility criteria text into population tags."""
    if not criteria_text:
        return []
    text = criteria_text.lower()
    tags = []
    if ("reduced ejection fraction" in text or "hfref" in text or
            ("lvef" in text and ("40" in text or "35" in text))):
        tags.append("HFrEF")
    if "preserved ejection fraction" in text or "hfpef" in text:
        tags.append("HFpEF")
    if "diabetes" in text or "diabetic" in text or "type 2" in text:
        tags.append("diabetic")
    if "chronic kidney" in text or "ckd" in text or "egfr" in text:
        tags.append("CKD")
    if any(age in text for age in ["65 years", "70 years", "75 years", "elderly"]):
        tags.append("elderly")
    if "atrial fibrillation" in text or "afib" in text:
        tags.append("AF")
    return tags


def run_extraction(output_path, limit=None):
    """Main extraction pipeline."""
    conn = get_aact_connection()
    cur = conn.cursor()

    print(f"Querying AACT for Phase 3 CV trials...")
    cur.execute(EXTRACTION_QUERY, (CV_CONDITION_PATTERN,))
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]
    studies = [dict(zip(cols, row)) for row in rows]
    print(f"  Found {len(studies)} candidate trials")

    if limit:
        studies = studies[:limit]

    nct_ids = [s["nct_id"] for s in studies]

    # Fetch outcomes
    print("Fetching primary outcomes...")
    cur.execute(OUTCOMES_QUERY, (nct_ids,))
    outcome_rows = cur.fetchall()
    outcome_cols = [desc[0] for desc in cur.description]
    outcomes_by_nct = {}
    for row in outcome_rows:
        od = dict(zip(outcome_cols, row))
        outcomes_by_nct.setdefault(od["nct_id"], []).append(od)

    # Fetch interventions
    print("Fetching interventions...")
    cur.execute(INTERVENTIONS_QUERY, (nct_ids,))
    interv_rows = cur.fetchall()
    interventions_by_nct = {}
    for nct_id, itype, name in interv_rows:
        interventions_by_nct.setdefault(nct_id, []).append({
            "type": itype, "name": name
        })

    # Fetch facilities
    print("Fetching facility data...")
    cur.execute(FACILITIES_QUERY, (nct_ids,))
    fac_rows = cur.fetchall()
    facilities_by_nct = {}
    for nct_id, country, count in fac_rows:
        entry = facilities_by_nct.setdefault(nct_id, {"countries": set(), "total_sites": 0})
        entry["countries"].add(country)
        entry["total_sites"] += count

    # Fetch eligibility
    print("Fetching eligibility criteria...")
    cur.execute(ELIGIBILITY_QUERY, (nct_ids,))
    elig_rows = cur.fetchall()
    eligibility_by_nct = {nct_id: criteria for nct_id, criteria in elig_rows}

    cur.close()
    conn.close()

    # Assemble records
    print("Assembling trial records...")
    records = []
    for s in studies:
        nct = s["nct_id"]
        interventions = interventions_by_nct.get(nct, [])
        drug_names = [i["name"] for i in interventions if i["type"] == "Drug"]
        drug_classes = [classify_drug(name) for name in drug_names]
        primary_class = next((c for c in drug_classes if c != "other"), "other")

        primary_outcomes = outcomes_by_nct.get(nct, [])
        endpoint_texts = [o["title"] for o in primary_outcomes if o["title"]]
        endpoint_type = classify_endpoint(endpoint_texts[0]) if endpoint_texts else "other"

        fac = facilities_by_nct.get(nct, {"countries": set(), "total_sites": 0})
        countries = list(fac["countries"]) if isinstance(fac["countries"], set) else fac["countries"]

        elig_text = eligibility_by_nct.get(nct, "")
        pop_tags = extract_population_tags(elig_text)

        has_placebo = any(
            i["type"] == "Drug" and "placebo" in (i["name"] or "").lower()
            for i in interventions
        ) or any(
            i["type"] == "Other" and "placebo" in (i["name"] or "").lower()
            for i in interventions
        )

        is_double_blind = "double" in (s.get("masking") or "").lower()

        duration = months_between(s["start_date"], s["primary_completion_date"])
        start_year = s["start_date"].year if hasattr(s.get("start_date"), "year") else None

        record = {
            "nct_id": nct,
            "title": s["brief_title"],
            "status": s["overall_status"],
            "why_stopped": s["why_stopped"],
            "enrollment": s["enrollment"],
            "start_date": parse_date(s["start_date"]),
            "primary_completion_date": parse_date(s["primary_completion_date"]),
            "start_year": start_year,
            "duration_months": duration,
            "sponsor_name": s["sponsor_name"],
            "sponsor_class": s["sponsor_class"],
            "is_industry": s["sponsor_class"] == "INDUSTRY",
            "has_dsmb": s["has_dmc"],
            "num_arms": s["number_of_arms"],
            "placebo_controlled": has_placebo,
            "comparator_type": "placebo" if has_placebo else "active",
            "double_blind": is_double_blind,
            "drug_class": primary_class,
            "endpoint_type": endpoint_type,
            "endpoint_text": endpoint_texts[0] if endpoint_texts else None,
            "num_sites": fac["total_sites"],
            "num_countries": len(countries),
            "multi_regional": len(countries) > 1,
            "population_tags": pop_tags,
            "primary_outcomes": [
                {
                    "title": o["title"],
                    "p_value": float(o["p_value"]) if o["p_value"] is not None else None,
                    "ci_lower": float(o["ci_lower_limit"]) if o["ci_lower_limit"] is not None else None,
                    "ci_upper": float(o["ci_upper_limit"]) if o["ci_upper_limit"] is not None else None,
                    "param_type": o["param_type"],
                    "param_value": float(o["param_value_num"]) if o["param_value_num"] is not None else None,
                    "method": o["method"],
                }
                for o in primary_outcomes
            ],
        }
        records.append(record)

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

    print(f"Extracted {len(records)} trials to {output_path}")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract CV trials from AACT")
    parser.add_argument("--output", default="data/raw_trials.json")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run_extraction(args.output, args.limit)
```

- [ ] **Step 4: Add extraction tests**

Append to `tests/test_curation.py`:

```python
from extract_aact import months_between, extract_population_tags
from datetime import date


class TestMonthsBetween:
    def test_one_year(self):
        assert abs(months_between(date(2020, 1, 1), date(2021, 1, 1)) - 12.0) < 0.5

    def test_none_start(self):
        assert months_between(None, date(2021, 1, 1)) is None

    def test_same_date(self):
        assert months_between(date(2020, 6, 1), date(2020, 6, 1)) == 0.0


class TestExtractPopulationTags:
    def test_hfref(self):
        text = "Patients with reduced ejection fraction (LVEF <= 40%)"
        assert "HFrEF" in extract_population_tags(text)

    def test_diabetic_ckd(self):
        text = "Type 2 diabetes mellitus with chronic kidney disease stage 3-4"
        tags = extract_population_tags(text)
        assert "diabetic" in tags
        assert "CKD" in tags

    def test_empty_string(self):
        assert extract_population_tags("") == []

    def test_none(self):
        assert extract_population_tags(None) == []
```

- [ ] **Step 5: Run tests (no AACT connection needed)**

```bash
python -m pytest tests/test_curation.py -v
```
Expected: ALL PASS (these test pure functions, not DB queries)

- [ ] **Step 6: Commit extraction script**

```bash
git add curate/extract_aact.py tests/test_curation.py
git commit -m "feat: AACT extraction script with population tag parsing and drug/endpoint classification"
```

---

## Task 3: Outcome Labeling Script

**Files:**
- Create: `curate/label_outcomes.py`
- Create: `data/landmark_trials.json`
- Test: `tests/test_curation.py` (new tests)

- [ ] **Step 1: Write failing tests for labeling**

Append to `tests/test_curation.py`:

```python
from label_outcomes import label_trial, LABEL_SUCCESS, LABEL_FAILURE, LABEL_SAFETY_FAIL


class TestLabelTrial:
    def test_tier1_significant_p(self):
        trial = {
            "status": "Completed",
            "why_stopped": None,
            "primary_outcomes": [{"p_value": 0.001, "ci_lower": 0.65, "ci_upper": 0.90,
                                  "param_type": "Hazard Ratio", "param_value": 0.80}],
        }
        label, tier, reason = label_trial(trial)
        assert label == LABEL_SUCCESS
        assert tier == 1

    def test_tier1_nonsignificant(self):
        trial = {
            "status": "Completed",
            "why_stopped": None,
            "primary_outcomes": [{"p_value": 0.42, "ci_lower": 0.85, "ci_upper": 1.20,
                                  "param_type": "Hazard Ratio", "param_value": 1.01}],
        }
        label, tier, reason = label_trial(trial)
        assert label == LABEL_FAILURE
        assert tier == 1

    def test_terminated_futility(self):
        trial = {
            "status": "Terminated",
            "why_stopped": "Stopped for futility based on interim analysis",
            "primary_outcomes": [],
        }
        label, tier, reason = label_trial(trial)
        assert label == LABEL_FAILURE
        assert tier == 1

    def test_terminated_safety(self):
        trial = {
            "status": "Terminated",
            "why_stopped": "Safety concerns: increased adverse events",
            "primary_outcomes": [],
        }
        label, tier, reason = label_trial(trial)
        assert label == LABEL_SAFETY_FAIL
        assert tier == 1

    def test_tier2_ci_excludes_one(self):
        trial = {
            "status": "Completed",
            "why_stopped": None,
            "primary_outcomes": [{"p_value": None, "ci_lower": 0.60, "ci_upper": 0.95,
                                  "param_type": "Hazard Ratio", "param_value": 0.75}],
        }
        label, tier, reason = label_trial(trial)
        assert label == LABEL_SUCCESS
        assert tier == 2

    def test_tier2_ci_includes_one(self):
        trial = {
            "status": "Completed",
            "why_stopped": None,
            "primary_outcomes": [{"p_value": None, "ci_lower": 0.80, "ci_upper": 1.10,
                                  "param_type": "Hazard Ratio", "param_value": 0.94}],
        }
        label, tier, reason = label_trial(trial)
        assert label == LABEL_FAILURE
        assert tier == 2

    def test_unlabelable(self):
        trial = {
            "status": "Completed",
            "why_stopped": None,
            "primary_outcomes": [{"p_value": None, "ci_lower": None, "ci_upper": None,
                                  "param_type": None, "param_value": None}],
        }
        label, tier, reason = label_trial(trial)
        assert label is None
        assert tier is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_curation.py::TestLabelTrial -v
```
Expected: FAIL with "cannot import name 'label_trial'"

- [ ] **Step 3: Write label_outcomes.py**

```python
"""Tier 1/2/3 success/failure labeling for CardioOracle training data.

Usage: python curate/label_outcomes.py --input data/raw_trials.json --output data/labeled_trials.json
"""
import argparse
import json

LABEL_SUCCESS = "success"
LABEL_FAILURE = "failure"
LABEL_SAFETY_FAIL = "safety_failure"

FUTILITY_KEYWORDS = ["futility", "lack of efficacy", "unlikely to demonstrate",
                     "no benefit", "insufficient efficacy"]
SAFETY_KEYWORDS = ["safety", "adverse", "harm", "toxicity", "increased mortality",
                   "increased risk"]

# Param types where value < 1.0 favors intervention
RATIO_PARAMS = {"hazard ratio", "odds ratio", "relative risk", "risk ratio", "rate ratio"}


def _is_ratio_param(param_type):
    """Check if this param type is a ratio where <1 favors intervention."""
    if param_type is None:
        return False
    return param_type.lower().strip() in RATIO_PARAMS


def _effect_favors_intervention(outcome):
    """Determine if the effect direction favors the intervention."""
    pt = outcome.get("param_type")
    pv = outcome.get("param_value")
    if pt is None or pv is None:
        return None  # Can't determine
    if _is_ratio_param(pt):
        return pv < 1.0
    # For difference-type params (mean diff, etc.), assume negative = favors intervention
    # This is a simplification; some outcomes are positive-good (e.g., LVEF improvement)
    return True  # Conservative: if p<0.05 and param exists, assume directional


def label_trial(trial):
    """Label a trial as success/failure with tier and reason.

    Returns: (label, tier, reason) where label is LABEL_SUCCESS/LABEL_FAILURE/
             LABEL_SAFETY_FAIL/None, tier is 1/2/3/None, reason is a string.
    """
    status = trial.get("status", "")
    why_stopped = (trial.get("why_stopped") or "").lower()
    outcomes = trial.get("primary_outcomes", [])

    # --- Tier 1: Terminated trials ---
    if status == "Terminated":
        if any(kw in why_stopped for kw in FUTILITY_KEYWORDS):
            return LABEL_FAILURE, 1, f"Terminated for futility: {trial.get('why_stopped')}"
        if any(kw in why_stopped for kw in SAFETY_KEYWORDS):
            return LABEL_SAFETY_FAIL, 1, f"Terminated for safety: {trial.get('why_stopped')}"
        # Terminated for other reasons (funding, enrollment) - can't label
        if why_stopped:
            return None, None, f"Terminated (non-efficacy): {trial.get('why_stopped')}"
        return None, None, "Terminated with no reason given"

    # --- Tier 1: Clear p-value ---
    for outcome in outcomes:
        p = outcome.get("p_value")
        if p is not None:
            if p < 0.05 and _effect_favors_intervention(outcome) is not False:
                return LABEL_SUCCESS, 1, f"Primary endpoint p={p:.4f}, effect favors intervention"
            elif p >= 0.05:
                return LABEL_FAILURE, 1, f"Primary endpoint p={p:.4f}, not significant"

    # --- Tier 2: CI-based ---
    for outcome in outcomes:
        ci_lo = outcome.get("ci_lower")
        ci_hi = outcome.get("ci_upper")
        pt = outcome.get("param_type")
        if ci_lo is not None and ci_hi is not None and _is_ratio_param(pt):
            if ci_hi < 1.0:
                return LABEL_SUCCESS, 2, f"CI [{ci_lo:.3f}, {ci_hi:.3f}] excludes 1.0 (ratio)"
            elif ci_lo > 1.0:
                return LABEL_FAILURE, 2, f"CI [{ci_lo:.3f}, {ci_hi:.3f}] > 1.0 (harm direction)"
            else:
                return LABEL_FAILURE, 2, f"CI [{ci_lo:.3f}, {ci_hi:.3f}] includes 1.0"

    # --- Tier 2: Multiple primary endpoints (any significant) ---
    if len(outcomes) > 1:
        any_sig = any(
            o.get("p_value") is not None and o["p_value"] < 0.05
            for o in outcomes
        )
        if any_sig:
            return LABEL_SUCCESS, 2, "At least one primary endpoint significant (partial)"

    # --- Unlabelable ---
    return None, None, "Insufficient data to determine outcome"


def label_all(raw_trials, landmark_overrides=None):
    """Label all trials, applying landmark overrides for Tier 3."""
    labeled = []
    stats = {"tier1": 0, "tier2": 0, "tier3": 0, "unlabeled": 0}

    overrides = {}
    if landmark_overrides:
        for lt in landmark_overrides:
            overrides[lt["nct_id"]] = lt

    for trial in raw_trials:
        nct = trial["nct_id"]

        # Tier 3: Landmark override takes priority
        if nct in overrides:
            lm = overrides[nct]
            trial["label"] = lm["label"]
            trial["label_tier"] = 3
            trial["label_reason"] = f"Landmark override: {lm.get('source', 'manual')}"
            stats["tier3"] += 1
            labeled.append(trial)
            continue

        label, tier, reason = label_trial(trial)
        trial["label"] = label
        trial["label_tier"] = tier
        trial["label_reason"] = reason

        if tier == 1:
            stats["tier1"] += 1
        elif tier == 2:
            stats["tier2"] += 1
        else:
            stats["unlabeled"] += 1

        if label is not None:
            labeled.append(trial)

    return labeled, stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw_trials.json")
    parser.add_argument("--landmarks", default="data/landmark_trials.json")
    parser.add_argument("--output", default="data/labeled_trials.json")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        raw = json.load(f)

    landmarks = None
    try:
        with open(args.landmarks, encoding="utf-8") as f:
            landmarks = json.load(f)
    except FileNotFoundError:
        print(f"No landmark file at {args.landmarks}, skipping Tier 3")

    labeled, stats = label_all(raw, landmarks)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(labeled, f, indent=2, default=str)

    print(f"Labeled {len(labeled)} trials:")
    print(f"  Tier 1 (automated):  {stats['tier1']}")
    print(f"  Tier 2 (heuristic):  {stats['tier2']}")
    print(f"  Tier 3 (landmark):   {stats['tier3']}")
    print(f"  Unlabelable:         {stats['unlabeled']}")
```

- [ ] **Step 4: Create data/landmark_trials.json (initial ~30 landmark trials)**

```json
[
  {"nct_id": "NCT01920711", "name": "PARADIGM-HF", "label": "success", "source": "NEJM 2014; HR 0.80, p<0.001"},
  {"nct_id": "NCT03036124", "name": "DAPA-HF", "label": "success", "source": "NEJM 2019; HR 0.74, p<0.001"},
  {"nct_id": "NCT03057977", "name": "EMPEROR-Reduced", "label": "success", "source": "NEJM 2020; HR 0.75, p<0.001"},
  {"nct_id": "NCT02540993", "name": "CREDENCE", "label": "success", "source": "NEJM 2019; HR 0.70, p=0.00001"},
  {"nct_id": "NCT02484092", "name": "FIDELIO-DKD", "label": "success", "source": "NEJM 2020; HR 0.82, p=0.001"},
  {"nct_id": "NCT02545049", "name": "FIGARO-DKD", "label": "success", "source": "NEJM 2021; HR 0.87, p=0.0014"},
  {"nct_id": "NCT01035255", "name": "EMPA-REG OUTCOME", "label": "success", "source": "NEJM 2015; HR 0.86, p=0.04"},
  {"nct_id": "NCT01986881", "name": "LEADER", "label": "success", "source": "NEJM 2016; HR 0.87, p=0.01"},
  {"nct_id": "NCT01720446", "name": "SUSTAIN-6", "label": "success", "source": "NEJM 2016; HR 0.74, p=0.02"},
  {"nct_id": "NCT01394342", "name": "DECLARE-TIMI 58", "label": "failure", "source": "NEJM 2019; HR 0.93, p=0.17 for MACE"},
  {"nct_id": "NCT00968708", "name": "SAVOR-TIMI 53", "label": "failure", "source": "NEJM 2013; HR 1.00, p=0.99 for MACE"},
  {"nct_id": "NCT01032629", "name": "EXAMINE", "label": "failure", "source": "NEJM 2013; HR 0.96, noninferiority only"},
  {"nct_id": "NCT01897532", "name": "CANVAS", "label": "success", "source": "NEJM 2017; HR 0.86, p=0.02"},
  {"nct_id": "NCT01243424", "name": "ELIXA", "label": "failure", "source": "NEJM 2015; HR 1.02, p=0.81"},
  {"nct_id": "NCT03057951", "name": "EMPEROR-Preserved", "label": "success", "source": "NEJM 2021; HR 0.79, p<0.001"},
  {"nct_id": "NCT03619213", "name": "DELIVER", "label": "success", "source": "NEJM 2022; HR 0.82, p<0.001"},
  {"nct_id": "NCT01615770", "name": "SELECT", "label": "success", "source": "NEJM 2023; HR 0.80, p<0.001"},
  {"nct_id": "NCT03036150", "name": "DAPA-CKD", "label": "success", "source": "NEJM 2020; HR 0.61, p<0.001"},
  {"nct_id": "NCT04000165", "name": "FINEARTS-HF", "label": "success", "source": "NEJM 2024; HR 0.84, p=0.007"},
  {"nct_id": "NCT00634712", "name": "TOPCAT", "label": "failure", "source": "NEJM 2014; HR 0.89, p=0.14"},
  {"nct_id": "NCT01730534", "name": "ATMOSPHERE", "label": "failure", "source": "Lancet 2016; HR 1.00 aliskiren vs enalapril"},
  {"nct_id": "NCT02653482", "name": "SCORED", "label": "success", "source": "NEJM 2021; HR 0.74, p<0.001"},
  {"nct_id": "NCT02531035", "name": "SOLOIST-WHF", "label": "success", "source": "NEJM 2021; HR 0.67, p<0.001"},
  {"nct_id": "NCT00790764", "name": "PARAGON-HF", "label": "failure", "source": "NEJM 2019; RR 0.87, p=0.059"},
  {"nct_id": "NCT01035242", "name": "FOURIER", "label": "success", "source": "NEJM 2017; HR 0.85, p<0.001"},
  {"nct_id": "NCT01663402", "name": "ODYSSEY Outcomes", "label": "success", "source": "NEJM 2018; HR 0.85, p<0.001"},
  {"nct_id": "NCT00174707", "name": "EMPHASIS-HF", "label": "success", "source": "NEJM 2011; HR 0.63, p<0.001"},
  {"nct_id": "NCT00634309", "name": "ARISTOTLE", "label": "success", "source": "NEJM 2011; HR 0.79, p<0.001"},
  {"nct_id": "NCT03982381", "name": "STEP-HFpEF", "label": "success", "source": "NEJM 2023; mean diff -7.8, p<0.001 KCCQ"}
]
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_curation.py -v
```
Expected: ALL PASS

- [ ] **Step 6: Commit labeling script + landmarks**

```bash
git add curate/label_outcomes.py data/landmark_trials.json
git commit -m "feat: 3-tier outcome labeling with 29 landmark cardiorenal trials"
```

---

## Task 4: Model Fitting + Export

**Files:**
- Create: `curate/fit_model.py`
- Create: `curate/export_training.py`

- [ ] **Step 1: Write failing test for model fitting**

Append to `tests/test_curation.py`:

```python
from fit_model import prepare_feature_matrix, fit_logistic_model
import numpy as np


class TestFeatureMatrix:
    def test_basic_shape(self):
        trials = [
            {"enrollment": 1000, "duration_months": 24, "placebo_controlled": True,
             "double_blind": True, "is_industry": True, "num_sites": 100,
             "multi_regional": True, "endpoint_type": "mace", "drug_class": "sglt2i",
             "comparator_type": "placebo", "num_arms": 2, "has_dsmb": True,
             "start_year": 2015, "label": "success"},
            {"enrollment": 500, "duration_months": 12, "placebo_controlled": False,
             "double_blind": False, "is_industry": False, "num_sites": 10,
             "multi_regional": False, "endpoint_type": "surrogate", "drug_class": "other",
             "comparator_type": "active", "num_arms": 3, "has_dsmb": False,
             "start_year": 2010, "label": "failure"},
        ]
        X, y, feature_names = prepare_feature_matrix(trials)
        assert X.shape[0] == 2
        assert len(feature_names) == X.shape[1]
        assert y[0] == 1  # success
        assert y[1] == 0  # failure


class TestFitModel:
    def test_returns_coefficients(self):
        # Synthetic data: large enrollment + industry = success
        np.random.seed(42)
        n = 100
        trials = []
        for i in range(n):
            is_big = np.random.random() > 0.5
            is_industry = np.random.random() > 0.5
            success_prob = 0.3 + 0.2 * is_big + 0.15 * is_industry
            trials.append({
                "enrollment": 5000 if is_big else 200,
                "duration_months": 24, "placebo_controlled": True,
                "double_blind": True, "is_industry": is_industry,
                "num_sites": 50, "multi_regional": True,
                "endpoint_type": "mace", "drug_class": "sglt2i",
                "comparator_type": "placebo", "num_arms": 2, "has_dsmb": True,
                "start_year": 2015,
                "label": "success" if np.random.random() < success_prob else "failure",
            })
        X, y, names = prepare_feature_matrix(trials)
        model_info = fit_logistic_model(X, y, names)
        assert "intercept" in model_info["coefficients"]
        assert len(model_info["coefficients"]) == len(names) + 1  # +1 for intercept
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_curation.py::TestFeatureMatrix -v
```
Expected: FAIL with import error

- [ ] **Step 3: Write fit_model.py**

```python
"""Fit logistic regression for CardioOracle meta-regression component.

Usage: python curate/fit_model.py --input data/labeled_trials.json --output data/model_coefficients.json
"""
import argparse
import json
import math

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss


def _era_bucket(year):
    """Map start year to era bucket."""
    if year is None:
        return "unknown"
    if year < 2010:
        return "pre2010"
    if year < 2018:
        return "2010_2017"
    return "2018plus"


def prepare_feature_matrix(trials):
    """Convert labeled trials to feature matrix X and label vector y.

    Returns: (X: np.ndarray, y: np.ndarray, feature_names: list[str])
    """
    feature_names = [
        "log_enrollment", "duration_months", "placebo_controlled", "double_blind",
        "is_industry", "log_num_sites", "multi_regional", "num_arms", "has_dsmb",
        # One-hot: endpoint_type (reference: 'other')
        "ep_mace", "ep_hf_hosp", "ep_cv_death", "ep_acm", "ep_renal", "ep_surrogate",
        # One-hot: era (reference: 'pre2010')
        "era_2010_2017", "era_2018plus",
        # Continuous
        "historical_class_rate",
    ]

    rows = []
    labels = []
    for t in trials:
        enr = t.get("enrollment") if t.get("enrollment") is not None else 100
        nsites = t.get("num_sites") if t.get("num_sites") is not None else 1
        dur = t.get("duration_months") if t.get("duration_months") is not None else 24
        narms = t.get("num_arms") if t.get("num_arms") is not None else 2
        ep = t.get("endpoint_type", "other")
        era = _era_bucket(t.get("start_year"))
        hist_rate = t.get("historical_class_rate") if t.get("historical_class_rate") is not None else 0.45

        row = [
            math.log(max(enr, 1)),
            dur,
            1.0 if t.get("placebo_controlled") else 0.0,
            1.0 if t.get("double_blind") else 0.0,
            1.0 if t.get("is_industry") else 0.0,
            math.log(max(nsites, 1)),
            1.0 if t.get("multi_regional") else 0.0,
            float(narms),
            1.0 if t.get("has_dsmb") else 0.0,
            # endpoint one-hots
            1.0 if ep == "mace" else 0.0,
            1.0 if ep == "hf_hosp" else 0.0,
            1.0 if ep == "cv_death" else 0.0,
            1.0 if ep == "acm" else 0.0,
            1.0 if ep == "renal" else 0.0,
            1.0 if ep == "surrogate" else 0.0,
            # era one-hots
            1.0 if era == "2010_2017" else 0.0,
            1.0 if era == "2018plus" else 0.0,
            # continuous
            hist_rate,
        ]
        rows.append(row)
        labels.append(1 if t["label"] == "success" else 0)

    return np.array(rows), np.array(labels), feature_names


def fit_logistic_model(X, y, feature_names):
    """Fit L2-regularized logistic regression and return coefficients + metrics."""
    model = LogisticRegression(
        penalty="l2", C=1.0, solver="lbfgs", max_iter=1000, random_state=42
    )
    model.fit(X, y)

    coeffs = {"intercept": float(model.intercept_[0])}
    for name, coef in zip(feature_names, model.coef_[0]):
        coeffs[name] = float(coef)

    # In-sample metrics (full metrics computed on temporal split externally)
    y_prob = model.predict_proba(X)[:, 1]
    try:
        auc = float(roc_auc_score(y, y_prob))
    except ValueError:
        auc = None
    brier = float(brier_score_loss(y, y_prob))

    return {
        "coefficients": coeffs,
        "insample_metrics": {"auc": auc, "brier": brier, "n": int(len(y))},
    }


def compute_temporal_split_metrics(trials, coefficients, feature_names, split_date="2020-01-01"):
    """Evaluate model on temporal hold-out set."""
    train_trials = [t for t in trials
                    if (t.get("primary_completion_date") or "2000") < split_date]
    test_trials = [t for t in trials
                   if (t.get("primary_completion_date") or "2000") >= split_date]

    if len(test_trials) < 10:
        return {"warning": f"Only {len(test_trials)} test trials, metrics unreliable",
                "n_train": len(train_trials), "n_test": len(test_trials)}

    X_test, y_test, _ = prepare_feature_matrix(test_trials)

    # Reconstruct predictions from coefficients
    intercept = coefficients["intercept"]
    coef_vec = np.array([coefficients.get(name, 0.0) for name in feature_names])
    logits = X_test @ coef_vec + intercept
    probs = 1.0 / (1.0 + np.exp(-logits))

    try:
        auc = float(roc_auc_score(y_test, probs))
    except ValueError:
        auc = None

    brier = float(brier_score_loss(y_test, probs))

    # Calibration slope (logistic regression of y on logit(p))
    try:
        from sklearn.linear_model import LogisticRegression as LR
        cal_model = LR(penalty=None, solver="lbfgs", max_iter=1000)
        cal_model.fit(logits.reshape(-1, 1), y_test)
        cal_slope = float(cal_model.coef_[0][0])
    except Exception:
        cal_slope = None

    # Per-trial predictions for Calibration tab
    trial_predictions = []
    for i, t in enumerate(test_trials):
        trial_predictions.append({
            "nct_id": t["nct_id"],
            "title": t.get("title", ""),
            "predicted": float(probs[i]),
            "actual": int(y_test[i]),
            "label": t["label"],
        })

    return {
        "n_train": len(train_trials),
        "n_test": len(test_trials),
        "auc": auc,
        "brier": brier,
        "calibration_slope": cal_slope,
        "trial_predictions": trial_predictions,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/labeled_trials.json")
    parser.add_argument("--output", default="data/model_coefficients.json")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        trials = json.load(f)

    X, y, names = prepare_feature_matrix(trials)
    model_info = fit_logistic_model(X, y, names)

    # Temporal split evaluation
    temporal = compute_temporal_split_metrics(trials, model_info["coefficients"], names)
    model_info["temporal_validation"] = temporal

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(model_info, f, indent=2)

    print(f"Model fitted on {len(y)} trials")
    print(f"  In-sample AUC: {model_info['insample_metrics']['auc']:.3f}")
    print(f"  In-sample Brier: {model_info['insample_metrics']['brier']:.3f}")
    if temporal.get("auc"):
        print(f"  Temporal AUC:   {temporal['auc']:.3f}")
        print(f"  Temporal Brier: {temporal['brier']:.3f}")
        print(f"  Cal. slope:     {temporal.get('calibration_slope', 'N/A')}")
```

- [ ] **Step 4: Write export_training.py**

```python
"""Export curated training data and model coefficients for embedding in HTML.

Usage: python curate/export_training.py
       --labeled data/labeled_trials.json
       --model data/model_coefficients.json
       --config data/configs/cardiorenal.json
       --output-data data/training_data.json
       --output-model data/model_coefficients.json
"""
import argparse
import hashlib
import json
from datetime import datetime


def compute_class_base_rates(trials):
    """Compute historical success rate per drug class."""
    class_counts = {}
    for t in trials:
        dc = t.get("drug_class", "other")
        is_success = 1 if t["label"] == "success" else 0
        entry = class_counts.setdefault(dc, {"success": 0, "total": 0})
        entry["success"] += is_success
        entry["total"] += 1

    rates = {}
    for dc, counts in class_counts.items():
        rate = counts["success"] / counts["total"] if counts["total"] > 0 else 0.45
        rates[dc] = round(rate, 3)
    return rates


def export_training_data(labeled_trials, config):
    """Produce the final training_data.json for embedding."""
    records = []
    for t in labeled_trials:
        records.append({
            "nct_id": t["nct_id"],
            "title": t.get("title", ""),
            "label": t["label"],
            "label_tier": t.get("label_tier"),
            "features": {
                "enrollment": t.get("enrollment"),
                "duration_months": t.get("duration_months"),
                "placebo_controlled": t.get("placebo_controlled"),
                "double_blind": t.get("double_blind"),
                "is_industry": t.get("is_industry"),
                "num_sites": t.get("num_sites"),
                "multi_regional": t.get("multi_regional"),
                "endpoint_type": t.get("endpoint_type"),
                "drug_class": t.get("drug_class"),
                "comparator_type": t.get("comparator_type", "placebo" if t.get("placebo_controlled") else "active"),
                "num_arms": t.get("num_arms"),
                "has_dsmb": t.get("has_dsmb"),
                "start_year": t.get("start_year"),
                "population_tags": t.get("population_tags", []),
            },
            "outcome_summary": t.get("label_reason", ""),
        })

    class_rates = compute_class_base_rates(labeled_trials)

    # Inject historical_class_rate into each record
    for r in records:
        dc = r["features"].get("drug_class", "other")
        r["features"]["historical_class_rate"] = class_rates.get(dc, 0.45)

    # Compute content hash
    data_str = json.dumps(records, sort_keys=True)
    content_hash = hashlib.sha256(data_str.encode()).hexdigest()

    return {
        "version": "1.0.0",
        "generated": datetime.utcnow().isoformat() + "Z",
        "config": config.get("id", "cardiorenal"),
        "content_hash": content_hash,
        "n_trials": len(records),
        "class_base_rates": class_rates,
        "trials": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--labeled", default="data/labeled_trials.json")
    parser.add_argument("--config", default="data/configs/cardiorenal.json")
    parser.add_argument("--output", default="data/training_data.json")
    args = parser.parse_args()

    with open(args.labeled, encoding="utf-8") as f:
        labeled = json.load(f)
    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

    result = export_training_data(labeled, config)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Exported {result['n_trials']} trials")
    print(f"  Content hash: {result['content_hash'][:16]}...")
    print(f"  Class rates: {result['class_base_rates']}")
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/test_curation.py -v
```
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add curate/fit_model.py curate/export_training.py
git commit -m "feat: logistic regression model fitting + training data export with temporal validation"
```

---

## Task 5: Validate Labels Script

**Files:**
- Create: `curate/validate_labels.py`

- [ ] **Step 1: Write validate_labels.py**

```python
"""Cross-check labeled trials against landmark_trials.json gold standard.

Usage: python curate/validate_labels.py --labeled data/labeled_trials.json --landmarks data/landmark_trials.json
"""
import argparse
import json
import sys


def validate(labeled_trials, landmarks):
    """Compare pipeline labels against landmark ground truth."""
    labeled_map = {t["nct_id"]: t for t in labeled_trials}
    mismatches = []
    missing = []
    correct = 0

    for lm in landmarks:
        nct = lm["nct_id"]
        if nct not in labeled_map:
            missing.append(lm)
            continue

        pipeline_label = labeled_map[nct].get("label")
        expected_label = lm["label"]

        # Normalize: safety_failure counts as failure for validation
        if pipeline_label == "safety_failure":
            pipeline_label = "failure"

        if pipeline_label == expected_label:
            correct += 1
        else:
            mismatches.append({
                "nct_id": nct,
                "name": lm.get("name", ""),
                "expected": expected_label,
                "got": labeled_map[nct].get("label"),
                "tier": labeled_map[nct].get("label_tier"),
                "reason": labeled_map[nct].get("label_reason"),
            })

    total = correct + len(mismatches)
    accuracy = correct / total * 100 if total > 0 else 0

    print(f"\n=== Label Validation Report ===")
    print(f"Landmarks checked: {len(landmarks)}")
    print(f"Found in pipeline: {total}")
    print(f"Missing from pipeline: {len(missing)}")
    print(f"Correct: {correct}/{total} ({accuracy:.1f}%)")

    if mismatches:
        print(f"\nMISMATCHES ({len(mismatches)}):")
        for m in mismatches:
            print(f"  {m['nct_id']} ({m['name']}): expected={m['expected']}, "
                  f"got={m['got']} (tier {m['tier']}): {m['reason']}")

    if missing:
        print(f"\nMISSING ({len(missing)}):")
        for m in missing:
            print(f"  {m['nct_id']} ({m.get('name', '')})")

    return len(mismatches) == 0 and len(missing) == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--labeled", default="data/labeled_trials.json")
    parser.add_argument("--landmarks", default="data/landmark_trials.json")
    args = parser.parse_args()

    with open(args.labeled, encoding="utf-8") as f:
        labeled = json.load(f)
    with open(args.landmarks, encoding="utf-8") as f:
        landmarks = json.load(f)

    ok = validate(labeled, landmarks)
    sys.exit(0 if ok else 1)
```

- [ ] **Step 2: Commit**

```bash
git add curate/validate_labels.py
git commit -m "feat: landmark validation script for label cross-checking"
```

---

## Task 6: HTML App Shell (Structure + CSS + Tabs)

**Files:**
- Create: `CardioOracle.html`

This task creates the HTML/CSS skeleton with tab navigation, dark mode, and placeholder content for all 5 tabs. No prediction logic yet.

- [ ] **Step 1: Write the HTML app shell**

Create `CardioOracle.html` — the complete HTML/CSS skeleton. This is a long file; key sections:

1. `<head>`: meta, Plotly CDN, CSS custom properties (light/dark), responsive layout
2. Tab bar: Predict | Design | Training Data | Calibration | WebR Validation
3. Tab panels: each with placeholder content
4. Footer: version, AACT snapshot date, content hash
5. JS: tab switching, dark mode toggle, localStorage schema migration

The HTML structure follows the established pattern from CRES: `data-theme` attribute on `<html>`, CSS custom properties for theming, `role="tablist"` / `role="tab"` / `role="tabpanel"` for accessibility.

```html
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CardioOracle — Cardiovascular Trial Outcome Predictor</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
/* === CSS Custom Properties === */
:root {
  --bg: #f8f9fa; --bg-card: #ffffff; --bg-input: #ffffff;
  --text: #212529; --text-muted: #6c757d; --text-accent: #0d6efd;
  --border: #dee2e6; --shadow: rgba(0,0,0,0.08);
  --success: #198754; --warning: #fd7e14; --danger: #dc3545;
  --green-bg: #d1e7dd; --amber-bg: #fff3cd; --red-bg: #f8d7da;
  --tab-active: #0d6efd; --tab-hover: #e9ecef;
  --radius: 8px; --transition: 0.2s ease;
}
[data-theme="dark"] {
  --bg: #1a1d21; --bg-card: #2b2f35; --bg-input: #343a40;
  --text: #e9ecef; --text-muted: #adb5bd; --text-accent: #6ea8fe;
  --border: #495057; --shadow: rgba(0,0,0,0.3);
  --success: #75b798; --warning: #ffda6a; --danger: #ea868f;
  --green-bg: #0f3d2c; --amber-bg: #3d3000; --red-bg: #3d0a0a;
  --tab-active: #6ea8fe; --tab-hover: #343a40;
}

/* === Base === */
*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0; padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg); color: var(--text);
  line-height: 1.6; transition: background var(--transition), color var(--transition);
}
.container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }

/* === Header === */
.app-header {
  background: var(--bg-card); border-bottom: 1px solid var(--border);
  padding: 16px 0; box-shadow: 0 1px 3px var(--shadow);
}
.app-header .container { display: flex; align-items: center; justify-content: space-between; }
.app-title { font-size: 1.5rem; font-weight: 700; margin: 0; }
.app-title span { color: var(--text-accent); }
.app-subtitle { font-size: 0.85rem; color: var(--text-muted); margin: 0; }
.header-controls { display: flex; gap: 12px; align-items: center; }
.theme-toggle {
  background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 6px 12px; cursor: pointer; color: var(--text); font-size: 0.85rem;
}
.theme-toggle:hover { background: var(--tab-hover); }
.config-select {
  background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 6px 12px; color: var(--text); font-size: 0.85rem;
}

/* === Tabs === */
.tab-bar {
  display: flex; background: var(--bg-card); border-bottom: 2px solid var(--border);
  padding: 0 20px; overflow-x: auto;
}
.tab-btn {
  padding: 12px 20px; border: none; background: none; cursor: pointer;
  font-size: 0.9rem; color: var(--text-muted); white-space: nowrap;
  border-bottom: 3px solid transparent; margin-bottom: -2px;
  transition: color var(--transition), border-color var(--transition);
}
.tab-btn:hover { color: var(--text); background: var(--tab-hover); }
.tab-btn:focus-visible { outline: 2px solid var(--tab-active); outline-offset: -2px; }
.tab-btn[aria-selected="true"] {
  color: var(--tab-active); border-bottom-color: var(--tab-active); font-weight: 600;
}
.tab-panel { display: none; padding: 24px 0; }
.tab-panel.active { display: block; }

/* === Cards === */
.card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 20px; margin-bottom: 16px;
  box-shadow: 0 1px 3px var(--shadow);
}
.card-title { font-size: 1.1rem; font-weight: 600; margin: 0 0 12px 0; }

/* === Traffic Light === */
.traffic-light {
  display: inline-flex; align-items: center; gap: 12px;
  padding: 16px 24px; border-radius: var(--radius); font-size: 1.8rem; font-weight: 700;
}
.traffic-light.high { background: var(--green-bg); color: var(--success); }
.traffic-light.moderate { background: var(--amber-bg); color: var(--warning); }
.traffic-light.low { background: var(--red-bg); color: var(--danger); }
.traffic-label { font-size: 0.9rem; font-weight: 600; }

/* === Search === */
.search-bar {
  display: flex; gap: 8px; margin-bottom: 20px;
}
.search-input {
  flex: 1; padding: 10px 16px; border: 1px solid var(--border);
  border-radius: var(--radius); font-size: 1rem; background: var(--bg-input);
  color: var(--text);
}
.search-input:focus { outline: 2px solid var(--tab-active); border-color: var(--tab-active); }
.search-btn {
  padding: 10px 24px; background: var(--tab-active); color: #fff; border: none;
  border-radius: var(--radius); font-size: 1rem; cursor: pointer; font-weight: 600;
}
.search-btn:hover { opacity: 0.9; }
.search-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* === Collapsible === */
.collapsible-header {
  display: flex; align-items: center; justify-content: space-between;
  cursor: pointer; padding: 12px 0; border-bottom: 1px solid var(--border);
  user-select: none;
}
.collapsible-header:focus-visible { outline: 2px solid var(--tab-active); }
.collapsible-body { display: none; padding: 16px 0; }
.collapsible-body.open { display: block; }
.chevron { transition: transform var(--transition); }
.chevron.open { transform: rotate(180deg); }

/* === Tables === */
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
th { font-weight: 600; color: var(--text-muted); background: var(--bg); }

/* === Spinner === */
.spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid var(--border);
  border-top-color: var(--tab-active); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* === Responsive === */
@media (max-width: 768px) {
  .tab-btn { padding: 10px 14px; font-size: 0.8rem; }
  .traffic-light { font-size: 1.4rem; padding: 12px 16px; }
}

/* === Alerts === */
.alert { padding: 12px 16px; border-radius: var(--radius); margin-bottom: 16px; font-size: 0.9rem; }
.alert-warning { background: var(--amber-bg); color: var(--warning); border: 1px solid var(--warning); }
.alert-danger { background: var(--red-bg); color: var(--danger); border: 1px solid var(--danger); }
.alert-info { background: #cff4fc; color: #055160; border: 1px solid #b6effb; }
[data-theme="dark"] .alert-info { background: #032830; color: #6edff6; border: 1px solid #055160; }
</style>
</head>
<body>

<!-- Header -->
<header class="app-header">
  <div class="container">
    <div>
      <h1 class="app-title">Cardio<span>Oracle</span></h1>
      <p class="app-subtitle">Cardiovascular Trial Outcome Predictor</p>
    </div>
    <div class="header-controls">
      <select class="config-select" id="configSelect" aria-label="Therapeutic area">
        <option value="cardiorenal" selected>Cardiorenal / HF</option>
      </select>
      <button class="theme-toggle" id="themeToggle" aria-label="Toggle dark mode">Dark</button>
    </div>
  </div>
</header>

<!-- Tab Bar -->
<nav class="tab-bar" role="tablist" aria-label="Main navigation">
  <button class="tab-btn" role="tab" aria-selected="true" aria-controls="panel-predict" id="tab-predict" tabindex="0">Predict</button>
  <button class="tab-btn" role="tab" aria-selected="false" aria-controls="panel-design" id="tab-design" tabindex="-1">Design</button>
  <button class="tab-btn" role="tab" aria-selected="false" aria-controls="panel-data" id="tab-data" tabindex="-1">Training Data</button>
  <button class="tab-btn" role="tab" aria-selected="false" aria-controls="panel-calibration" id="tab-calibration" tabindex="-1">Calibration</button>
  <button class="tab-btn" role="tab" aria-selected="false" aria-controls="panel-webr" id="tab-webr" tabindex="-1">WebR Validation</button>
</nav>

<!-- Tab Panels -->
<main class="container">

  <!-- Predict Tab -->
  <div class="tab-panel active" role="tabpanel" id="panel-predict" aria-labelledby="tab-predict">
    <div class="search-bar">
      <input class="search-input" id="nctInput" type="text" placeholder="Enter NCT ID (e.g., NCT03036124)" aria-label="NCT ID">
      <button class="search-btn" id="predictBtn" onclick="runPrediction()">Predict</button>
    </div>
    <div id="predictionResult"></div>
    <div id="predictionError" style="display:none"></div>
  </div>

  <!-- Design Tab (Phase 2 placeholder) -->
  <div class="tab-panel" role="tabpanel" id="panel-design" aria-labelledby="tab-design">
    <div class="card">
      <h2 class="card-title">Trial Designer</h2>
      <p style="color:var(--text-muted)">Interactive trial design mode coming in Phase 2. Use the Predict tab to look up existing trials.</p>
    </div>
  </div>

  <!-- Training Data Tab (Phase 3 placeholder) -->
  <div class="tab-panel" role="tabpanel" id="panel-data" aria-labelledby="tab-data">
    <div class="card">
      <h2 class="card-title">Training Data Explorer</h2>
      <p style="color:var(--text-muted)">Full training data table coming in Phase 3.</p>
      <p>Training set: <strong id="trainingCount">0</strong> labeled trials | Content hash: <code id="trainingHash">—</code></p>
    </div>
  </div>

  <!-- Calibration Tab (Phase 3 placeholder) -->
  <div class="tab-panel" role="tabpanel" id="panel-calibration" aria-labelledby="tab-calibration">
    <div class="card">
      <h2 class="card-title">Model Calibration</h2>
      <p style="color:var(--text-muted)">Calibration plots and metrics coming in Phase 3.</p>
    </div>
  </div>

  <!-- WebR Tab (Phase 3 placeholder) -->
  <div class="tab-panel" role="tabpanel" id="panel-webr" aria-labelledby="tab-webr">
    <div class="card">
      <h2 class="card-title">WebR Validation</h2>
      <p style="color:var(--text-muted)">In-browser R validation coming in Phase 3.</p>
    </div>
  </div>

</main>

<footer style="text-align:center; padding:20px; color:var(--text-muted); font-size:0.8rem; border-top:1px solid var(--border); margin-top:40px;">
  CardioOracle v1.0.0 | Training data: <span id="footerHash">—</span> | <a href="https://clinicaltrials.gov" target="_blank" rel="noopener" style="color:var(--text-accent)">ClinicalTrials.gov</a>
</footer>

<script>
"use strict";

/* ============================================================
   SECTION 1: CONFIGURATION + DATA
   ============================================================ */

// --- Placeholder training data (replaced by pipeline output) ---
const TRAINING_DATA = { version: "1.0.0-placeholder", trials: [], content_hash: "placeholder", class_base_rates: {} };
const MODEL = { coefficients: {}, insample_metrics: {}, temporal_validation: {} };

// --- Config ---
const CONFIG = {
  id: "cardiorenal",
  priors: { alpha: 4.5, beta: 5.5 },
  similarity_weights: { drug_class: 0.30, endpoint_type: 0.25, comparator_type: 0.15, population: 0.15, era: 0.15 },
  ensemble_weights: { bayesian: 0.40, conditional_power: 0.35, meta_regression: 0.25 },
};

/* ============================================================
   SECTION 2: TAB NAVIGATION
   ============================================================ */

(function initTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');

  function switchTab(target) {
    tabs.forEach(t => { t.setAttribute('aria-selected', 'false'); t.tabIndex = -1; });
    panels.forEach(p => p.classList.remove('active'));
    target.setAttribute('aria-selected', 'true');
    target.tabIndex = 0;
    target.focus();
    const panelId = target.getAttribute('aria-controls');
    document.getElementById(panelId).classList.add('active');
  }

  tabs.forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab));
    tab.addEventListener('keydown', (e) => {
      const idx = Array.from(tabs).indexOf(tab);
      if (e.key === 'ArrowRight' && idx < tabs.length - 1) { e.preventDefault(); switchTab(tabs[idx + 1]); }
      if (e.key === 'ArrowLeft' && idx > 0) { e.preventDefault(); switchTab(tabs[idx - 1]); }
      if (e.key === 'Home') { e.preventDefault(); switchTab(tabs[0]); }
      if (e.key === 'End') { e.preventDefault(); switchTab(tabs[tabs.length - 1]); }
    });
  });
})();

/* ============================================================
   SECTION 3: DARK MODE
   ============================================================ */

(function initTheme() {
  const btn = document.getElementById('themeToggle');
  const saved = localStorage.getItem('cardiooracle_theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
  btn.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? 'Light' : 'Dark';

  btn.addEventListener('click', () => {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    btn.textContent = next === 'dark' ? 'Light' : 'Dark';
    try { localStorage.setItem('cardiooracle_theme', next); } catch(e) {}
  });
})();

/* ============================================================
   SECTION 4: UTILITY FUNCTIONS
   ============================================================ */

function escapeHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function normalCDF(x) {
  // Abramowitz & Stegun approximation
  const a1=0.254829592, a2=-0.284496736, a3=1.421413741, a4=-1.453152027, a5=1.061405429;
  const p=0.3275911;
  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x) / Math.SQRT2;
  const t = 1.0 / (1.0 + p * x);
  const y = 1.0 - (((((a5*t + a4)*t) + a3)*t + a2)*t + a1)*t * Math.exp(-x*x);
  return 0.5 * (1.0 + sign * y);
}

/* ============================================================
   SECTION 5: PREDICTION ENGINE (placeholder — filled in Task 7)
   ============================================================ */

function runPrediction() {
  const nctId = document.getElementById('nctInput').value.trim().toUpperCase();
  if (!nctId.match(/^NCT\d{8}$/)) {
    document.getElementById('predictionResult').innerHTML =
      '<div class="alert alert-warning">Please enter a valid NCT ID (e.g., NCT03036124)</div>';
    return;
  }
  document.getElementById('predictionResult').innerHTML =
    '<div style="text-align:center;padding:40px"><div class="spinner"></div><p style="margin-top:12px;color:var(--text-muted)">Fetching trial data from ClinicalTrials.gov...</p></div>';

  // Will be implemented in Task 7
  fetchAndPredict(nctId);
}

function fetchAndPredict(nctId) {
  // Placeholder — implemented in Task 7
  document.getElementById('predictionResult').innerHTML =
    '<div class="alert alert-info">Prediction engine will be implemented in Task 7. App shell is working.</div>';
}

/* ============================================================
   SECTION 6: INITIALIZATION
   ============================================================ */

(function init() {
  // localStorage schema migration
  const CURRENT_SCHEMA = 1;
  try {
    const stored = parseInt(localStorage.getItem('cardiooracle_schema_version') ?? '0', 10);
    if (stored < CURRENT_SCHEMA) {
      // v0 -> v1: initial schema, clear any stale keys from development
      const keysToPreserve = ['cardiooracle_theme'];
      const allKeys = Object.keys(localStorage).filter(k => k.startsWith('cardiooracle_'));
      for (const k of allKeys) {
        if (!keysToPreserve.includes(k)) localStorage.removeItem(k);
      }
      localStorage.setItem('cardiooracle_schema_version', String(CURRENT_SCHEMA));
    }
  } catch(e) { /* private browsing — no localStorage */ }

  document.getElementById('trainingCount').textContent = TRAINING_DATA.trials.length;
  document.getElementById('trainingHash').textContent = TRAINING_DATA.content_hash.substring(0, 16) + '...';
  document.getElementById('footerHash').textContent = TRAINING_DATA.content_hash.substring(0, 16) + '...';

  // Enter key triggers predict
  document.getElementById('nctInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') runPrediction();
  });
})();
</script>
</body>
</html>
```

- [ ] **Step 2: Open in browser and verify**

Open `CardioOracle.html` in a browser. Verify:
- Tab switching works (keyboard arrows + click)
- Dark mode toggle works and persists on reload
- Search bar accepts input, Enter triggers prediction
- Placeholder messages show in Phase 2/3/4 tabs
- No console errors

- [ ] **Step 3: Commit**

```bash
git add CardioOracle.html
git commit -m "feat: HTML app shell with 5-tab layout, dark mode, ARIA accessibility, Plotly CDN"
```

---

## Task 7: Prediction Engine (JS Core)

**Files:**
- Modify: `CardioOracle.html` (Section 5)

This is the heart of the app. Implement all three prediction components in JS:
1. CT.gov API fetch + feature extraction
2. BayesianBorrower
3. ConditionalPower
4. MetaRegressor (using embedded coefficients)
5. FeatureDecomposer
6. Ensemble combiner + result rendering

- [ ] **Step 1: Replace Section 5 (PREDICTION ENGINE) in CardioOracle.html**

Replace the placeholder `fetchAndPredict` and add the full prediction engine. The code goes between `SECTION 5` and `SECTION 6` comments. Key functions:

```javascript
/* ============================================================
   SECTION 5: PREDICTION ENGINE
   ============================================================ */

// --- 5A: CT.gov API Fetch ---

async function fetchTrialFromCTGov(nctId) {
  const cacheKey = 'cardiooracle_cache_' + nctId;
  try {
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) return JSON.parse(cached);
  } catch(e) {}

  const url = `https://clinicaltrials.gov/api/v2/studies/${nctId}`;
  const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!resp.ok) throw new Error(`CT.gov returned ${resp.status}`);
  const data = await resp.json();

  try { sessionStorage.setItem(cacheKey, JSON.stringify(data)); } catch(e) {}
  return data;
}

function extractFeatures(ctgovData) {
  const ps = ctgovData.protocolSection ?? {};
  const dm = ps.designModule ?? {};
  const em = ps.eligibilityModule ?? {};
  const cm = ps.conditionsModule ?? {};
  const ai = ps.armsInterventionsModule ?? {};
  const om = ps.outcomesModule ?? {};
  const sc = ps.sponsorCollaboratorsModule ?? {};
  const cl = ps.contactsLocationsModule ?? {};
  const sm = ps.statusModule ?? {};
  const id = ps.identificationModule ?? {};

  const enrollment = dm.enrollmentInfo?.count ?? null;
  const startDate = sm.startDateStruct?.date ?? null;
  const completionDate = sm.primaryCompletionDateStruct?.date ?? sm.completionDateStruct?.date ?? null;
  let durationMonths = null;
  if (startDate && completionDate) {
    const s = new Date(startDate), e = new Date(completionDate);
    durationMonths = Math.round((e - s) / (1000 * 60 * 60 * 24 * 30.44) * 10) / 10;
  }

  const arms = ai.armGroups ?? [];
  const interventions = ai.interventions ?? [];
  const placeboControlled = arms.some(a => a.type === 'PLACEBO_COMPARATOR');
  const maskingInfo = dm.maskingInfo ?? {};
  const doubleBlind = (maskingInfo.masking ?? '').toUpperCase().includes('DOUBLE');

  const sponsor = sc.leadSponsor ?? {};
  const isIndustry = sponsor.class === 'INDUSTRY';

  const locations = cl.locations ?? [];
  const numSites = locations.length;
  const countries = new Set(locations.map(l => l.country).filter(Boolean));
  const multiRegional = countries.size > 1;

  const drugNames = interventions
    .filter(i => i.type === 'DRUG' || i.type === 'BIOLOGICAL')
    .map(i => i.name ?? '');
  const drugClass = classifyDrugJS(drugNames);

  const primaryOutcomes = om.primaryOutcomes ?? [];
  const endpointText = primaryOutcomes.length > 0 ? (primaryOutcomes[0].measure ?? '') : '';
  const endpointType = classifyEndpointJS(endpointText);

  const numArms = dm.designInfo?.numberOfArms ?? arms.length ?? 2;
  const om2 = ps.oversightModule ?? {};
  const hasDsmb = om2.oversightHasDmc ?? null;

  const startYear = startDate ? new Date(startDate).getFullYear() : null;

  // Parse population tags from eligibility
  const eligText = em.eligibilityCriteria ?? '';
  const populationTags = extractPopulationTagsJS(eligText);

  const comparatorType = placeboControlled ? 'placebo' : 'active';

  return {
    title: id.briefTitle ?? id.officialTitle ?? nctId,
    enrollment, duration_months: durationMonths,
    placebo_controlled: placeboControlled, double_blind: doubleBlind,
    is_industry: isIndustry, num_sites: numSites, multi_regional: multiRegional,
    drug_class: drugClass, endpoint_type: endpointType, endpoint_text: endpointText,
    num_arms: numArms, has_dsmb: hasDsmb, start_year: startYear,
    population_tags: populationTags, comparator_type: comparatorType,
  };
}

// --- 5B: Drug/Endpoint Classification (JS mirrors of Python shared.py) ---

const DRUG_CLASS_MAP_JS = {
  sglt2i: ["empagliflozin","dapagliflozin","canagliflozin","ertugliflozin",
           "sotagliflozin","ipragliflozin","tofogliflozin","luseogliflozin"],
  mra: ["spironolactone","eplerenone"],
  ns_mra: ["finerenone","esaxerenone","apararenone","ocedurenone"],
  arni: ["sacubitril","entresto","sacubitril/valsartan"],
  arb: ["valsartan","losartan","candesartan","irbesartan","telmisartan","olmesartan","azilsartan"],
  acei: ["enalapril","ramipril","lisinopril","perindopril","captopril",
         "quinapril","benazepril","fosinopril"],
  bb: ["carvedilol","bisoprolol","metoprolol","nebivolol","atenolol"],
  glp1ra: ["semaglutide","liraglutide","dulaglutide","exenatide",
           "albiglutide","lixisenatide","tirzepatide"],
  pcsk9i: ["evolocumab","alirocumab","inclisiran"],
  statin: ["atorvastatin","rosuvastatin","simvastatin","pravastatin",
           "lovastatin","fluvastatin","pitavastatin"],
  anticoag: ["apixaban","rivaroxaban","edoxaban","dabigatran","warfarin"],
  antiplat: ["ticagrelor","prasugrel","clopidogrel","aspirin","cangrelor"],
};

function classifyDrugJS(drugNames) {
  for (const name of drugNames) {
    const lower = name.toLowerCase().replace(/\d+\s*(mg|mcg|ml)\b/g, '').trim();
    for (const [classId, drugs] of Object.entries(DRUG_CLASS_MAP_JS)) {
      if (drugs.some(d => lower.includes(d))) return classId;
    }
  }
  return 'other';
}

const ENDPOINT_TYPE_MAP_JS = [
  ['mace', ['mace','major adverse cardiovascular','composite cardiovascular']],
  ['hf_hosp', ['heart failure hospitalization','hf hospitalization','worsening heart failure']],
  ['cv_death', ['cardiovascular death','cardiac death','cv death','cardiovascular mortality']],
  ['acm', ['all-cause mortality','all cause mortality','overall survival','death from any cause']],
  ['renal', ['egfr','kidney','renal','dialysis','eskd','doubling of creatinine']],
  ['surrogate', ['blood pressure','ldl','hba1c','nt-probnp','ejection fraction','6-minute walk']],
];

function classifyEndpointJS(text) {
  const lower = text.toLowerCase();
  for (const [etype, keywords] of ENDPOINT_TYPE_MAP_JS) {
    if (keywords.some(kw => lower.includes(kw))) return etype;
  }
  return 'other';
}

function extractPopulationTagsJS(text) {
  if (!text) return [];
  const lower = text.toLowerCase();
  const tags = [];
  if (lower.includes('reduced ejection fraction') || lower.includes('hfref')) tags.push('HFrEF');
  if (lower.includes('preserved ejection fraction') || lower.includes('hfpef')) tags.push('HFpEF');
  if (lower.includes('diabetes') || lower.includes('diabetic') || lower.includes('type 2')) tags.push('diabetic');
  if (lower.includes('chronic kidney') || lower.includes('ckd')) tags.push('CKD');
  if (/\b(65|70|75)\s*years/.test(lower) || lower.includes('elderly')) tags.push('elderly');
  return tags;
}

// --- 5C: Bayesian Historical Borrowing ---

function computeSimilarity(target, candidate) {
  const w = CONFIG.similarity_weights;
  let score = 0;

  // Drug class
  if (target.drug_class === candidate.features.drug_class) score += w.drug_class * 1.0;
  else {
    const broadMech = { sglt2i:'sodium_glucose', mra:'mra', ns_mra:'mra', arni:'raas', arb:'raas', acei:'raas' };
    if (broadMech[target.drug_class] && broadMech[target.drug_class] === broadMech[candidate.features.drug_class])
      score += w.drug_class * 0.5;
  }

  // Endpoint type
  const hardEndpoints = new Set(['mace','hf_hosp','cv_death','acm']);
  if (target.endpoint_type === candidate.features.endpoint_type) score += w.endpoint_type * 1.0;
  else if (hardEndpoints.has(target.endpoint_type) && hardEndpoints.has(candidate.features.endpoint_type))
    score += w.endpoint_type * 0.3;

  // Comparator type
  if (target.comparator_type === (candidate.features.placebo_controlled ? 'placebo' : 'active'))
    score += w.comparator_type * 1.0;

  // Population (Jaccard)
  const tTags = new Set(target.population_tags ?? []);
  const cTags = new Set(candidate.features.population_tags ?? []);
  if (tTags.size > 0 || cTags.size > 0) {
    const inter = [...tTags].filter(t => cTags.has(t)).length;
    const union = new Set([...tTags, ...cTags]).size;
    score += w.population * (union > 0 ? inter / union : 0);
  }

  // Era (exponential decay, 10-year half-life)
  const tYear = target.start_year ?? 2020;
  const cYear = candidate.features.start_year ?? 2015;
  score += w.era * Math.exp(-Math.abs(tYear - cYear) * Math.LN2 / 10);

  return score;
}

function bayesianBorrowing(target, trainingTrials) {
  const scored = trainingTrials.map(t => ({
    trial: t, similarity: computeSimilarity(target, t)
  })).sort((a, b) => b.similarity - a.similarity);

  // K selection: similarity > 0.3, clamp [5, 30]
  let selected = scored.filter(s => s.similarity > 0.3);
  let confidence = 'NORMAL';

  if (selected.length < 5) {
    selected = scored.filter(s => s.similarity > 0.1);
    if (selected.length < 3) {
      return { p: null, ci: null, twins: [], confidence: 'INSUFFICIENT', reason: 'Fewer than 3 similar trials' };
    }
    confidence = 'LOW';
  }
  if (selected.length > 30) selected = selected.slice(0, 30);
  if (selected.length < 5 && scored.length >= 5) selected = scored.slice(0, 5);

  // Posterior computation (raw similarity weights, NOT normalized)
  const a0 = CONFIG.priors.alpha;
  const b0 = CONFIG.priors.beta;
  let effSucc = 0, effFail = 0;
  for (const s of selected) {
    const isSuccess = s.trial.label === 'success' ? 1 : 0;
    effSucc += s.similarity * isSuccess;
    effFail += s.similarity * (1 - isSuccess);
  }

  const aPost = a0 + effSucc;
  const bPost = b0 + effFail;
  const pBayesian = aPost / (aPost + bPost);

  // 80% credible interval from Beta distribution (approximation via normal)
  const variance = (aPost * bPost) / ((aPost + bPost) ** 2 * (aPost + bPost + 1));
  const sd = Math.sqrt(variance);
  const z80 = 1.2816;
  const ciLo = Math.max(0, pBayesian - z80 * sd);
  const ciHi = Math.min(1, pBayesian + z80 * sd);

  return {
    p: pBayesian, ci: [ciLo, ciHi],
    twins: selected.slice(0, 10).map(s => ({
      nct_id: s.trial.nct_id, title: s.trial.title,
      similarity: Math.round(s.similarity * 1000) / 1000,
      label: s.trial.label,
    })),
    confidence, a_post: aPost, b_post: bPost,
    eff_successes: effSucc, eff_failures: effFail, k: selected.length,
  };
}

// --- 5D: Conditional Power ---

function conditionalPower(target, similarTrials) {
  const enrollment = target.enrollment;
  if (!enrollment || enrollment < 10) return { power: null, reason: 'No enrollment data' };

  const ep = target.endpoint_type ?? 'other';
  const isTimeToEvent = ['mace', 'hf_hosp', 'cv_death', 'acm'].includes(ep);

  // Estimate historical effect size from similar trials' labels
  // Simplified: use base rate to derive approximate HR/OR
  const successes = similarTrials.filter(t => t.label === 'success').length;
  const total = similarTrials.length;
  if (total < 3) return { power: null, reason: 'Too few similar trials for effect estimation' };

  // Rough historical effect size estimation
  // If ~50% of similar trials succeeded, the typical effect is modest (HR ~0.85)
  // If ~80% succeeded, effects are larger (HR ~0.75)
  const successRate = successes / total;
  const estimatedLogHR = -0.05 - 0.25 * successRate; // maps 0->-0.05, 1->-0.30
  const estimatedHR = Math.exp(estimatedLogHR);

  let power, events;
  const zAlpha = 1.96; // two-sided 0.05

  if (isTimeToEvent) {
    // Schoenfeld formula
    events = Math.round(enrollment * 0.7); // 70% info fraction if no event rate data
    const logHR = Math.abs(estimatedLogHR);
    if (logHR < 0.001) {
      power = 0.025;
    } else {
      power = normalCDF(Math.sqrt(events) * logHR - zAlpha);
    }
  } else if (ep === 'surrogate') {
    // Continuous endpoint: SMD-based power
    // Convert success rate to approximate SMD (calibrated: 50% success ~ SMD 0.3)
    const estimatedSMD = 0.1 + 0.4 * successRate;
    power = normalCDF(estimatedSMD * Math.sqrt(enrollment / 4) - zAlpha);
  } else {
    // Binary endpoint: arcsine-transformed proportions
    // Approximate: use success rate to estimate treatment vs control proportions
    const p0 = 0.15; // typical control event rate
    const rr = estimatedHR; // use HR as proxy for RR
    const p1 = p0 * rr;
    const arcsineDiff = Math.abs(Math.asin(Math.sqrt(p1)) - Math.asin(Math.sqrt(p0)));
    power = normalCDF(arcsineDiff * Math.sqrt(2 * enrollment) - zAlpha);
  }

  // Power curve: compute power at multiple effect sizes
  const curve = [];
  const curveLabel = isTimeToEvent ? 'HR' : (ep === 'surrogate' ? 'SMD' : 'RR');
  if (isTimeToEvent) {
    for (let hr = 0.60; hr <= 1.05; hr += 0.05) {
      const lhr = Math.abs(Math.log(hr));
      const ev = Math.round(enrollment * 0.7);
      const pw = lhr < 0.001 ? 0.025 : normalCDF(Math.sqrt(ev) * lhr - zAlpha);
      curve.push({ x: Math.round(hr * 100) / 100, power: Math.round(pw * 1000) / 1000 });
    }
  } else if (ep === 'surrogate') {
    for (let smd = 0.05; smd <= 0.80; smd += 0.05) {
      const pw = normalCDF(smd * Math.sqrt(enrollment / 4) - zAlpha);
      curve.push({ x: Math.round(smd * 100) / 100, power: Math.round(pw * 1000) / 1000 });
    }
  } else {
    for (let rr = 0.60; rr <= 1.05; rr += 0.05) {
      const p0 = 0.15, p1 = p0 * rr;
      const ad = Math.abs(Math.asin(Math.sqrt(p1)) - Math.asin(Math.sqrt(p0)));
      const pw = normalCDF(ad * Math.sqrt(2 * enrollment) - zAlpha);
      curve.push({ x: Math.round(rr * 100) / 100, power: Math.round(pw * 1000) / 1000 });
    }
  }

  return {
    power: Math.round(power * 1000) / 1000,
    estimated_hr: Math.round(estimatedHR * 100) / 100,
    events: events ?? null,
    curve, curveLabel,
    reason: `Based on ${total} similar trials (${successes} successful), estimated effect=${estimatedHR.toFixed(2)}`,
  };
}

// --- 5E: Meta-Regression ---

function metaRegressionPredict(features) {
  const C = MODEL.coefficients;
  if (!C || !C.intercept) return { p: null, contributions: {}, reason: 'No model coefficients loaded' };

  const enr = features.enrollment ?? 100;
  const nsites = features.num_sites ?? 1;
  const ep = features.endpoint_type ?? 'other';
  const year = features.start_year ?? 2020;
  const era = year < 2010 ? 'pre2010' : year < 2018 ? '2010_2017' : '2018plus';

  const featureVec = {
    log_enrollment: Math.log(Math.max(enr, 1)),
    duration_months: features.duration_months ?? 24,
    placebo_controlled: features.placebo_controlled ? 1 : 0,
    double_blind: features.double_blind ? 1 : 0,
    is_industry: features.is_industry ? 1 : 0,
    log_num_sites: Math.log(Math.max(nsites, 1)),
    multi_regional: features.multi_regional ? 1 : 0,
    num_arms: features.num_arms ?? 2,
    has_dsmb: features.has_dsmb ? 1 : 0,
    ep_mace: ep === 'mace' ? 1 : 0,
    ep_hf_hosp: ep === 'hf_hosp' ? 1 : 0,
    ep_cv_death: ep === 'cv_death' ? 1 : 0,
    ep_acm: ep === 'acm' ? 1 : 0,
    ep_renal: ep === 'renal' ? 1 : 0,
    ep_surrogate: ep === 'surrogate' ? 1 : 0,
    era_2010_2017: era === '2010_2017' ? 1 : 0,
    era_2018plus: era === '2018plus' ? 1 : 0,
  };

  let logit = C.intercept ?? 0;
  const contributions = {};
  for (const [name, val] of Object.entries(featureVec)) {
    const coef = C[name] ?? 0;
    const contrib = coef * val;
    logit += contrib;
    if (Math.abs(contrib) > 0.001) {
      contributions[name] = Math.round(contrib * 1000) / 1000;
    }
  }

  const p = 1 / (1 + Math.exp(-logit));
  return { p: Math.round(p * 1000) / 1000, contributions, logit };
}

// --- 5F: Ensemble + Rendering ---

function ensemblePredict(bayesian, power, regression) {
  const w = CONFIG.ensemble_weights;
  let totalWeight = 0, weightedSum = 0;

  if (bayesian.p !== null) {
    weightedSum += w.bayesian * bayesian.p;
    totalWeight += w.bayesian;
  }
  if (power.power !== null) {
    weightedSum += w.conditional_power * power.power;
    totalWeight += w.conditional_power;
  }
  if (regression.p !== null) {
    weightedSum += w.meta_regression * regression.p;
    totalWeight += w.meta_regression;
  }

  if (totalWeight === 0) return { p: null, level: null };

  const pFinal = weightedSum / totalWeight;
  const level = pFinal > 0.6 ? 'high' : pFinal > 0.3 ? 'moderate' : 'low';
  const levelLabel = pFinal > 0.6 ? 'HIGH' : pFinal > 0.3 ? 'MODERATE' : 'LOW';

  return { p: Math.round(pFinal * 1000) / 1000, level, levelLabel, totalWeight };
}

function renderPrediction(nctId, features, bayesian, power, regression, ensemble) {
  const pct = ensemble.p !== null ? Math.round(ensemble.p * 100) : '—';
  const ciText = bayesian.ci ? `${Math.round(bayesian.ci[0]*100)}% – ${Math.round(bayesian.ci[1]*100)}%` : 'N/A';

  let confidenceAlert = '';
  if (bayesian.confidence === 'LOW') {
    confidenceAlert = '<div class="alert alert-warning">LOW CONFIDENCE — few closely similar trials. Prediction relies more on prior and design features.</div>';
  } else if (bayesian.confidence === 'INSUFFICIENT') {
    confidenceAlert = '<div class="alert alert-warning">Limited historical comparators — prediction based on design features only.</div>';
  }

  let html = `
    ${confidenceAlert}
    <div class="card">
      <h2 class="card-title">${escapeHtml(features.title)}</h2>
      <p style="color:var(--text-muted)">${escapeHtml(nctId)} | ${escapeHtml(features.drug_class)} | ${escapeHtml(features.endpoint_text || features.endpoint_type)}</p>
      <div style="margin:20px 0">
        <div class="traffic-light ${ensemble.level}" aria-live="polite">
          ${pct}%
          <span class="traffic-label">${ensemble.levelLabel}</span>
        </div>
        <p style="margin-top:8px;color:var(--text-muted)">80% Credible Interval: ${ciText}</p>
      </div>
      <p>This trial has a <strong>${pct}%</strong> probability of meeting its primary endpoint, based on ${bayesian.k ?? 0} similar completed trials.</p>
    </div>
  `;

  // Historical Twins panel
  if (bayesian.twins && bayesian.twins.length > 0) {
    html += `<div class="card">
      <div class="collapsible-header" tabindex="0" role="button" aria-expanded="true" onclick="toggleCollapsible(this)" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleCollapsible(this)}">
        <span class="card-title" style="margin:0">Historical Twins (${bayesian.k} similar trials)</span>
        <span class="chevron open">&#9660;</span>
      </div>
      <div class="collapsible-body open">
        <table><thead><tr><th>NCT ID</th><th>Title</th><th>Similarity</th><th>Outcome</th></tr></thead><tbody>`;
    for (const tw of bayesian.twins) {
      const outcomeColor = tw.label === 'success' ? 'var(--success)' : 'var(--danger)';
      html += `<tr>
        <td><a href="https://clinicaltrials.gov/study/${escapeHtml(tw.nct_id)}" target="_blank" rel="noopener" style="color:var(--text-accent)">${escapeHtml(tw.nct_id)}</a></td>
        <td>${escapeHtml(tw.title)}</td>
        <td>${tw.similarity.toFixed(3)}</td>
        <td style="color:${outcomeColor};font-weight:600">${escapeHtml(tw.label)}</td>
      </tr>`;
    }
    html += '</tbody></table></div></div>';
  }

  // Power Assessment panel
  if (power.power !== null) {
    html += `<div class="card">
      <div class="collapsible-header" tabindex="0" role="button" aria-expanded="false" onclick="toggleCollapsible(this)" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleCollapsible(this)}">
        <span class="card-title" style="margin:0">Power Assessment (${Math.round(power.power*100)}%)</span>
        <span class="chevron">&#9660;</span>
      </div>
      <div class="collapsible-body">
        <p>${escapeHtml(power.reason)}</p>
        <p>Conditional power: <strong>${Math.round(power.power*100)}%</strong> | Estimated HR: ${power.estimated_hr}</p>
        <div id="powerCurveChart" style="height:300px"></div>
      </div>
    </div>`;
  }

  // Design Risk Factors panel
  if (regression.contributions && Object.keys(regression.contributions).length > 0) {
    html += `<div class="card">
      <div class="collapsible-header" tabindex="0" role="button" aria-expanded="false" onclick="toggleCollapsible(this)" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleCollapsible(this)}">
        <span class="card-title" style="margin:0">Design Risk Factors</span>
        <span class="chevron">&#9660;</span>
      </div>
      <div class="collapsible-body">
        <div id="riskFactorsChart" style="height:300px"></div>
      </div>
    </div>`;
  }

  document.getElementById('predictionResult').innerHTML = html;

  // Render charts after DOM update
  setTimeout(() => {
    if (power.curve && document.getElementById('powerCurveChart')) renderPowerCurve(power);
    if (regression.contributions && document.getElementById('riskFactorsChart')) renderRiskFactors(regression);
  }, 100);
}

function toggleCollapsible(header) {
  const body = header.nextElementSibling;
  const chevron = header.querySelector('.chevron');
  const isOpen = body.classList.contains('open');
  body.classList.toggle('open');
  chevron.classList.toggle('open');
  header.setAttribute('aria-expanded', !isOpen);
}

// --- 5G: Charts ---

function renderPowerCurve(power) {
  const el = document.getElementById('powerCurveChart');
  if (!el) return;
  const xVals = power.curve.map(c => c.x);
  const pows = power.curve.map(c => c.power * 100);
  const axisLabel = power.curveLabel ?? 'HR';
  const xRange = axisLabel === 'SMD' ? [0, 0.85] : [0.55, 1.1];

  const trace = { x: xVals, y: pows, type: 'scatter', mode: 'lines+markers',
    line: { color: '#0d6efd', width: 2 }, marker: { size: 5 }, name: 'Power' };

  const histLine = {
    x: [power.estimated_hr, power.estimated_hr], y: [0, 100],
    type: 'scatter', mode: 'lines', line: { color: '#dc3545', dash: 'dash', width: 2 },
    name: `Historical ${axisLabel} (${power.estimated_hr})`,
  };

  const eightyLine = {
    x: xRange, y: [80, 80], type: 'scatter', mode: 'lines',
    line: { color: '#6c757d', dash: 'dot', width: 1 }, name: '80% power',
  };

  Plotly.newPlot(el, [trace, histLine, eightyLine], {
    xaxis: { title: axisLabel, range: xRange },
    yaxis: { title: 'Power (%)', range: [0, 105] },
    margin: { t: 20, r: 20 }, showlegend: true, legend: { x: 0.02, y: 0.98 },
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: getComputedStyle(document.body).getPropertyValue('--text').trim() },
  }, { responsive: true, displayModeBar: false });
}

function renderRiskFactors(regression) {
  const el = document.getElementById('riskFactorsChart');
  if (!el) return;

  const entries = Object.entries(regression.contributions)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 10);

  const labels = entries.map(e => e[0].replace(/_/g, ' '));
  const values = entries.map(e => Math.round(e[1] * 100) / 100);
  const colors = values.map(v => v > 0 ? '#198754' : '#dc3545');

  Plotly.newPlot(el, [{
    y: labels.reverse(), x: values.reverse(), type: 'bar', orientation: 'h',
    marker: { color: colors.reverse() },
  }], {
    xaxis: { title: 'Log-odds contribution', zeroline: true },
    margin: { l: 140, t: 20, r: 20, b: 40 },
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: getComputedStyle(document.body).getPropertyValue('--text').trim() },
  }, { responsive: true, displayModeBar: false });
}

// --- 5H: Main Prediction Flow ---

async function fetchAndPredict(nctId) {
  const resultDiv = document.getElementById('predictionResult');
  try {
    const ctgovData = await fetchTrialFromCTGov(nctId);
    const features = extractFeatures(ctgovData);

    // Get similar trials for Bayesian component
    const bayesian = bayesianBorrowing(features, TRAINING_DATA.trials);

    // Conditional power
    const similarForPower = bayesian.twins ?? [];
    const power = conditionalPower(features, TRAINING_DATA.trials.filter(t =>
      computeSimilarity(features, t) > 0.1
    ).slice(0, 30));

    // Meta-regression
    const regression = metaRegressionPredict(features);

    // Ensemble
    const ensemble = ensemblePredict(bayesian, power, regression);

    if (ensemble.p === null) {
      resultDiv.innerHTML = '<div class="alert alert-danger">INSUFFICIENT DATA — cannot generate a reliable prediction for this trial. Try the Design tab instead.</div>';
      return;
    }

    renderPrediction(nctId, features, bayesian, power, regression, ensemble);

    // Save to recent lookups
    try {
      const recent = JSON.parse(localStorage.getItem('cardiooracle_recent_lookups') ?? '[]');
      if (!recent.includes(nctId)) { recent.unshift(nctId); if (recent.length > 10) recent.pop(); }
      localStorage.setItem('cardiooracle_recent_lookups', JSON.stringify(recent));
    } catch(e) {}

  } catch (err) {
    if (err.name === 'AbortError' || err.message?.includes('timeout')) {
      // Automatic retry once per spec
      if (!fetchAndPredict._retried) {
        fetchAndPredict._retried = true;
        resultDiv.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div><p style="margin-top:12px;color:var(--text-muted)">Retrying...</p></div>';
        return fetchAndPredict(nctId);
      }
      fetchAndPredict._retried = false;
      resultDiv.innerHTML = '<div class="alert alert-danger">CT.gov is currently unavailable (timeout after retry). Try again later or enter trial details manually in the Design tab.<br><button class="search-btn" style="margin-top:8px" onclick="runPrediction()">Retry</button></div>';
    } else {
      resultDiv.innerHTML = `<div class="alert alert-danger">Could not fetch or parse trial data: ${escapeHtml(err.message)}<br>NCT ID may be invalid or trial record is incomplete.</div>`;
    }
    console.error('Prediction error:', err);
  }
}
```

- [ ] **Step 2: Open in browser and test with a known NCT ID**

Open `CardioOracle.html`, enter `NCT03036124` (DAPA-HF). Verify:
- Spinner shows during API fetch
- Traffic light renders with a probability
- Historical twins table populates
- Power curve chart renders
- Risk factors chart renders (will show zeros with placeholder model — expected)
- Error handling works: try `NCT99999999` (should show error message)

- [ ] **Step 3: Commit**

```bash
git add CardioOracle.html
git commit -m "feat: complete prediction engine — Bayesian borrowing, conditional power, meta-regression, Plotly charts"
```

---

## Task 8: Selenium Tests for Predict Tab

**Files:**
- Create: `tests/test_prediction.py`

- [ ] **Step 1: Write Selenium test suite**

```python
"""Selenium tests for CardioOracle Predict tab."""
import os
import sys
import time
import unittest

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', buffering=1)

HTML_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CardioOracle.html'))


class TestCardioOracleShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--incognito')
        options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        cls.driver = webdriver.Chrome(options=options)
        cls.driver.set_page_load_timeout(30)
        cls.driver.get(f'file:///{HTML_PATH}')
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def test_01_title(self):
        self.assertIn('CardioOracle', self.driver.title)

    def test_02_tabs_present(self):
        tabs = self.driver.find_elements(By.CSS_SELECTOR, '.tab-btn')
        self.assertEqual(len(tabs), 5)

    def test_03_tab_switching(self):
        design_tab = self.driver.find_element(By.ID, 'tab-design')
        design_tab.click()
        time.sleep(0.5)
        panel = self.driver.find_element(By.ID, 'panel-design')
        self.assertIn('active', panel.get_attribute('class'))

        predict_tab = self.driver.find_element(By.ID, 'tab-predict')
        predict_tab.click()
        time.sleep(0.5)

    def test_04_dark_mode_toggle(self):
        btn = self.driver.find_element(By.ID, 'themeToggle')
        btn.click()
        time.sleep(0.3)
        theme = self.driver.find_element(By.TAG_NAME, 'html').get_attribute('data-theme')
        self.assertEqual(theme, 'dark')
        btn.click()  # toggle back
        time.sleep(0.3)

    def test_05_invalid_nct_shows_warning(self):
        inp = self.driver.find_element(By.ID, 'nctInput')
        inp.clear()
        inp.send_keys('INVALID')
        self.driver.find_element(By.ID, 'predictBtn').click()
        time.sleep(1)
        result = self.driver.find_element(By.ID, 'predictionResult')
        self.assertIn('valid NCT ID', result.text)

    def test_06_search_bar_enter_key(self):
        inp = self.driver.find_element(By.ID, 'nctInput')
        inp.clear()
        inp.send_keys('NCT03036124')
        inp.send_keys(Keys.ENTER)
        time.sleep(1)
        result = self.driver.find_element(By.ID, 'predictionResult')
        # Should show spinner or result (API call may fail in CI, but no crash)
        self.assertTrue(len(result.text) > 0 or len(result.get_attribute('innerHTML')) > 10)

    def test_07_no_console_errors(self):
        logs = self.driver.get_log('browser')
        errors = [l for l in logs if l['level'] == 'SEVERE' and 'favicon' not in l['message']]
        self.assertEqual(len(errors), 0, f"Console errors: {errors}")

    def test_08_aria_roles_present(self):
        tablist = self.driver.find_element(By.CSS_SELECTOR, '[role="tablist"]')
        self.assertIsNotNone(tablist)
        tabs = self.driver.find_elements(By.CSS_SELECTOR, '[role="tab"]')
        self.assertEqual(len(tabs), 5)
        panels = self.driver.find_elements(By.CSS_SELECTOR, '[role="tabpanel"]')
        self.assertEqual(len(panels), 5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run Selenium tests**

```bash
python -m pytest tests/test_prediction.py -v --timeout=60
```
Expected: ALL PASS (8 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_prediction.py
git commit -m "test: 8 Selenium tests for app shell, tab navigation, dark mode, ARIA, search bar"
```

---

## Task 9: Run AACT Pipeline End-to-End

**Files:**
- Modify: `.env` (user creates with AACT credentials)

This task requires AACT credentials. If credentials are unavailable, skip to Task 10 and use placeholder data.

- [ ] **Step 1: Create .env file (user action)**

The user must create `C:\Models\CardioOracle\.env`:
```
AACT_USER=your_username
AACT_PASSWORD=your_password
```

Verify `.gitignore` (created in Task 1) includes `.env`:
```bash
grep ".env" .gitignore
```
Expected: `.env` is listed

- [ ] **Step 2: Install Python dependencies**

```bash
cd /c/Models/CardioOracle
pip install -r curate/requirements.txt
```

- [ ] **Step 3: Run extraction (limit 50 for initial test)**

```bash
cd /c/Models/CardioOracle
python curate/extract_aact.py --output data/raw_trials.json --limit 50
```
Expected: "Extracted 50 trials to data/raw_trials.json"

- [ ] **Step 4: Run labeling**

```bash
python curate/label_outcomes.py --input data/raw_trials.json --output data/labeled_trials.json
```
Expected: Tier distribution printed, labeled_trials.json created

- [ ] **Step 5: Run model fitting**

```bash
python curate/fit_model.py --input data/labeled_trials.json --output data/model_coefficients.json
```
Expected: AUC and Brier scores printed

- [ ] **Step 6: Run export**

```bash
python curate/export_training.py --labeled data/labeled_trials.json --output data/training_data.json
```
Expected: "Exported N trials" with content hash

- [ ] **Step 7: Validate labels**

```bash
python curate/validate_labels.py --labeled data/labeled_trials.json
```
Expected: Validation report (some landmarks may be missing from the 50-trial subset — expected)

- [ ] **Step 8: Run full extraction (no limit) once pipeline verified**

```bash
python curate/extract_aact.py --output data/raw_trials.json
python curate/label_outcomes.py --input data/raw_trials.json --output data/labeled_trials.json
python curate/fit_model.py --input data/labeled_trials.json --output data/model_coefficients.json
python curate/export_training.py --labeled data/labeled_trials.json --output data/training_data.json
python curate/validate_labels.py --labeled data/labeled_trials.json
```

- [ ] **Step 9: Commit pipeline outputs (not raw_trials.json)**

```bash
git add data/training_data.json data/model_coefficients.json
git commit -m "data: curated training set from AACT — N trials labeled, temporal validation"
```

---

## Task 10: Embed Training Data in HTML

**Files:**
- Modify: `CardioOracle.html` (replace placeholder TRAINING_DATA and MODEL)

- [ ] **Step 1: Generate JS embedding from JSON files**

```bash
cd /c/Models/CardioOracle
python -c "
import json
with open('data/training_data.json') as f: td = json.load(f)
with open('data/model_coefficients.json') as f: mc = json.load(f)
print(f'Training data: {td[\"n_trials\"]} trials, hash: {td[\"content_hash\"][:16]}')
print(f'Model AUC: {mc[\"insample_metrics\"][\"auc\"]:.3f}')
"
```

- [ ] **Step 2: Replace placeholder constants in CardioOracle.html**

Replace the placeholder `const TRAINING_DATA = { ... }` and `const MODEL = { ... }` with the actual contents of `data/training_data.json` and `data/model_coefficients.json`. The replacement is:

```javascript
const TRAINING_DATA = /* paste contents of data/training_data.json */;
const MODEL = /* paste contents of data/model_coefficients.json */;
```

- [ ] **Step 3: Verify in browser**

Open `CardioOracle.html`. Verify:
- Footer shows real content hash (not "placeholder")
- Training Data tab shows correct trial count
- Enter `NCT03036124` → prediction now uses real training data → should show meaningful P(success) with populated twins table

- [ ] **Step 4: Run Selenium tests**

```bash
python -m pytest tests/test_prediction.py -v --timeout=60
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add CardioOracle.html
git commit -m "feat: embed curated training data and model coefficients — Phase 1 MVP complete"
```

---

## Task 11: Final Integration Test + Cleanup

- [ ] **Step 1: Run all tests**

```bash
cd /c/Models/CardioOracle
python -m pytest tests/ -v --timeout=60
```
Expected: ALL PASS (curation unit tests + Selenium tests)

- [ ] **Step 2: Verify div balance**

```bash
cd /c/Models/CardioOracle
python -c "
import re
with open('CardioOracle.html', encoding='utf-8') as f:
    content = f.read()
# Count divs outside script blocks
script_sections = re.findall(r'<script[^>]*>.*?<\/script>', content, re.DOTALL)
non_script = content
for s in script_sections:
    non_script = non_script.replace(s, '')
opens = len(re.findall(r'<div[\s>]', non_script))
closes = len(re.findall(r'</div>', non_script))
print(f'Div balance: {opens} opens, {closes} closes — {\"BALANCED\" if opens == closes else \"IMBALANCED\"} ')
"
```
Expected: BALANCED

- [ ] **Step 3: Check for `</script>` in template literals**

```bash
cd /c/Models/CardioOracle
python -c "
import re
with open('CardioOracle.html', encoding='utf-8') as f:
    content = f.read()
scripts = re.findall(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
for i, s in enumerate(scripts):
    if '</script>' in s:
        print(f'WARNING: Literal </script> found inside script block {i+1}')
    else:
        print(f'Script block {i+1}: CLEAN')
"
```
Expected: All CLEAN

- [ ] **Step 4: Final commit with line count**

```bash
wc -l CardioOracle.html
git log --oneline
```

Report: Phase 1 MVP complete with line count and commit history.

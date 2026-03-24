"""
extract_aact.py — CardioOracle curation pipeline.

Queries the AACT PostgreSQL database for Phase 3 cardiovascular RCTs with
results, assembles each trial into a structured record, and writes JSON output.

Usage:
    python curate/extract_aact.py [--output data/raw_trials.json] [--limit N]
"""

import argparse
import json
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from shared import (
    DRUG_CLASS_MAP,
    classify_drug,
    classify_endpoint,
    get_aact_connection,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------

def parse_date(d) -> Optional[str]:
    """Convert a date/datetime object (or None) to an ISO-8601 string."""
    if d is None:
        return None
    if isinstance(d, (date, datetime)):
        return d.isoformat()
    # Fallback: stringify whatever we received
    return str(d)


def months_between(start, end) -> Optional[float]:
    """Return approximate months between two dates.

    Returns None if either argument is None.  Returns 0.0 if start == end.
    """
    if start is None or end is None:
        return None
    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()
    delta_days = (end - start).days
    return round(delta_days / 30.4375, 2)


# ---------------------------------------------------------------------------
# Population tag parser
# ---------------------------------------------------------------------------

def extract_population_tags(criteria_text: Optional[str]) -> list:
    """Parse an eligibility criteria block and return a list of population tags.

    Recognised tags: HFrEF, HFpEF, diabetic, CKD, elderly, AF.

    Operator precedence is made explicit with parentheses throughout to avoid
    any `and`/`or` precedence surprises.
    """
    if not criteria_text:
        return []

    text = criteria_text.lower()
    tags = []

    # HFrEF — reduced ejection fraction, explicit LVEF cut-offs
    if (
        ("reduced ejection fraction" in text)
        or ("hfref" in text)
        or (("lvef" in text) and (("40" in text) or ("35" in text)))
    ):
        tags.append("HFrEF")

    # HFpEF — preserved ejection fraction
    if (
        ("preserved ejection fraction" in text)
        or ("hfpef" in text)
        or (("lvef" in text) and ("50" in text))
    ):
        tags.append("HFpEF")

    # Diabetic — type 2 or general diabetes mention
    if (
        ("type 2 diabetes" in text)
        or ("t2dm" in text)
        or ("type 2 dm" in text)
        or ("diabetes mellitus" in text)
    ):
        tags.append("diabetic")

    # CKD — chronic kidney disease and related terms
    if (
        ("chronic kidney disease" in text)
        or ("ckd" in text)
        or ("egfr" in text)
        or ("renal impairment" in text)
    ):
        tags.append("CKD")

    # Elderly — age-based population criteria
    if (
        ("elderly" in text)
        or ("older adults" in text)
        or ("age \u2265 65" in text)
        or ("age >= 65" in text)
        or ("aged 65" in text)
    ):
        tags.append("elderly")

    # AF — atrial fibrillation
    if (
        ("atrial fibrillation" in text)
        or (" af " in text)
        or (text.startswith("af "))
        or (text.endswith(" af"))
    ):
        tags.append("AF")

    return tags


# ---------------------------------------------------------------------------
# Main SQL query builders
# ---------------------------------------------------------------------------

_CV_CONDITION_PATTERN = (
    "%(heart failure)s|%(coronary artery disease)s|%(myocardial infarction)s"
    "|%(atrial fibrillation)s|%(stroke)s|%(hypertension)s"
    "|%(cardiovascular)s|%(cardiac arrest)s|%(angina)s|%(atherosclerosis)s"
    "|%(peripheral artery disease)s|%(heart attack)s|%(cardiomyopathy)s"
    "|%(aortic stenosis)s|%(pulmonary hypertension)s|%(chronic kidney disease)s"
    "|%(diabetic nephropathy)s"
)

# SQL uses SIMILAR TO which requires the pattern without leading '%'
_CV_SIMILAR_TO = (
    "%(heart failure"
    "|coronary artery disease"
    "|myocardial infarction"
    "|atrial fibrillation"
    "|stroke"
    "|hypertension"
    "|cardiovascular"
    "|cardiac arrest"
    "|angina"
    "|atherosclerosis"
    "|peripheral artery disease"
    "|heart attack"
    "|cardiomyopathy"
    "|aortic stenosis"
    "|pulmonary hypertension"
    "|chronic kidney disease"
    "|diabetic nephropathy)%"
)


def _fetch_core_trials(cur, limit: Optional[int]) -> list:
    """Fetch the main trial roster from AACT with all study-level fields."""
    limit_clause = "" if limit is None else f"LIMIT {int(limit)}"

    sql = f"""
        SELECT
            s.nct_id,
            s.brief_title                   AS title,
            s.overall_status                AS status,
            s.why_stopped,
            s.enrollment,
            s.start_date,
            s.primary_completion_date,
            s.source                        AS sponsor_name,
            s.source_class                  AS sponsor_class,
            s.has_dmc                       AS has_dsmb,
            s.number_of_arms                AS num_arms,
            d.allocation,
            d.masking
        FROM ctgov.studies s
        LEFT JOIN ctgov.designs d
            ON d.nct_id = s.nct_id
        WHERE s.study_type        = 'INTERVENTIONAL'
          AND d.allocation        = 'RANDOMIZED'
          AND s.phase             = 'PHASE3'
          AND s.enrollment        >= 50
          AND s.overall_status    IN ('COMPLETED', 'TERMINATED')
          AND s.results_first_posted_date IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM ctgov.conditions c
              WHERE c.nct_id   = s.nct_id
                AND LOWER(c.name) SIMILAR TO %(cv_pattern)s
          )
        ORDER BY s.nct_id
        {limit_clause}
    """
    cur.execute(sql, {"cv_pattern": _CV_SIMILAR_TO})
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fetch_primary_outcomes(cur, nct_ids: list) -> dict:
    """Return primary outcome data keyed by nct_id.

    Each value is a list of dicts with analysis statistics where available.
    """
    if not nct_ids:
        return {}

    sql = """
        SELECT
            o.nct_id,
            o.title,
            oa.p_value,
            oa.ci_lower_limit   AS ci_lower,
            oa.ci_upper_limit   AS ci_upper,
            oa.param_type,
            oa.param_value,
            oa.method
        FROM ctgov.outcomes o
        LEFT JOIN ctgov.outcome_analyses oa
            ON oa.outcome_id = o.id
        WHERE o.nct_id        = ANY(%s)
          AND o.outcome_type  = 'PRIMARY'
        ORDER BY o.nct_id, o.id, oa.id
    """
    cur.execute(sql, (nct_ids,))
    cols = [desc[0] for desc in cur.description]
    result: dict = {}
    for row in cur.fetchall():
        rec = dict(zip(cols, row))
        nct = rec["nct_id"]
        if nct not in result:
            result[nct] = []
        result[nct].append(
            {
                "title": rec["title"],
                "p_value": rec["p_value"],
                "ci_lower": float(rec["ci_lower"]) if rec["ci_lower"] is not None else None,
                "ci_upper": float(rec["ci_upper"]) if rec["ci_upper"] is not None else None,
                "param_type": rec["param_type"],
                "param_value": float(rec["param_value"]) if rec["param_value"] is not None else None,
                "method": rec["method"],
            }
        )
    return result


def _fetch_interventions(cur, nct_ids: list) -> dict:
    """Return the first drug-class intervention name keyed by nct_id.

    Also flags whether a placebo arm was found and sets comparator_type.
    """
    if not nct_ids:
        return {}

    sql = """
        SELECT
            nct_id,
            name            AS intervention_name,
            intervention_type
        FROM ctgov.interventions
        WHERE nct_id = ANY(%s)
        ORDER BY nct_id, id
    """
    cur.execute(sql, (nct_ids,))
    cols = [desc[0] for desc in cur.description]
    by_nct: dict = {}
    for row in cur.fetchall():
        rec = dict(zip(cols, row))
        nct = rec["nct_id"]
        if nct not in by_nct:
            by_nct[nct] = {"interventions": [], "has_placebo": False}
        by_nct[nct]["interventions"].append(rec)
        if "placebo" in (rec["intervention_name"] or "").lower():
            by_nct[nct]["has_placebo"] = True
    return by_nct


def _fetch_facilities(cur, nct_ids: list) -> dict:
    """Return site count and unique country count keyed by nct_id."""
    if not nct_ids:
        return {}

    sql = """
        SELECT
            nct_id,
            COUNT(*)                        AS num_sites,
            COUNT(DISTINCT country)         AS num_countries
        FROM ctgov.facilities
        WHERE nct_id = ANY(%s)
        GROUP BY nct_id
    """
    cur.execute(sql, (nct_ids,))
    return {row[0]: {"num_sites": row[1], "num_countries": row[2]} for row in cur.fetchall()}


def _fetch_eligibilities(cur, nct_ids: list) -> dict:
    """Return eligibility criteria text keyed by nct_id."""
    if not nct_ids:
        return {}

    sql = """
        SELECT nct_id, criteria
        FROM ctgov.eligibilities
        WHERE nct_id = ANY(%s)
    """
    cur.execute(sql, (nct_ids,))
    return {row[0]: row[1] for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------

def _assemble_record(
    core: dict,
    outcomes: list,
    interv_data: dict,
    facility: dict,
    criteria: Optional[str],
) -> dict:
    """Assemble a single trial record from the raw query results."""
    nct = core["nct_id"]

    # Dates
    start = core.get("start_date")
    completion = core.get("primary_completion_date")
    start_year = start.year if isinstance(start, (date, datetime)) else None

    # Sponsor
    sponsor_class = (core.get("sponsor_class") or "").lower()
    is_industry = "industry" in sponsor_class

    # Arms / blinding
    masking = (core.get("masking") or "").lower()
    double_blind = ("double" in masking) or ("participant" in masking and "investigator" in masking)

    # Placebo / comparator
    has_placebo = interv_data.get("has_placebo", False)
    comparator_type = "placebo" if has_placebo else "active"

    # Drug classification — pick first non-placebo Drug intervention
    drug_class = "other"
    endpoint_type = "other"
    endpoint_text = None
    for iv in interv_data.get("interventions", []):
        if (iv.get("intervention_type") or "").lower() == "drug":
            name = iv.get("intervention_name") or ""
            if "placebo" not in name.lower():
                drug_class = classify_drug(name)
                break

    # Endpoint classification — use the first primary outcome title
    if outcomes:
        endpoint_text = outcomes[0].get("title")
        endpoint_type = classify_endpoint(endpoint_text or "")

    # Facilities
    num_sites = facility.get("num_sites", 0)
    num_countries = facility.get("num_countries", 0)

    return {
        "nct_id": nct,
        "title": core.get("title"),
        "status": core.get("status"),
        "why_stopped": core.get("why_stopped"),
        "enrollment": core.get("enrollment"),
        "start_date": parse_date(start),
        "primary_completion_date": parse_date(completion),
        "start_year": start_year,
        "duration_months": months_between(start, completion),
        "sponsor_name": core.get("sponsor_name"),
        "sponsor_class": core.get("sponsor_class"),
        "is_industry": is_industry,
        "has_dsmb": bool(core.get("has_dsmb")),
        "num_arms": core.get("num_arms"),
        "placebo_controlled": has_placebo,
        "comparator_type": comparator_type,
        "double_blind": double_blind,
        "drug_class": drug_class,
        "endpoint_type": endpoint_type,
        "endpoint_text": endpoint_text,
        "num_sites": num_sites,
        "num_countries": num_countries,
        "multi_regional": num_countries > 1,
        "population_tags": extract_population_tags(criteria),
        "primary_outcomes": outcomes,
    }


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_trials(output_path: str, limit: Optional[int] = None) -> None:
    """Run the full extraction pipeline and write JSON to output_path."""
    log.info("Connecting to AACT ...")
    conn = get_aact_connection()
    try:
        with conn.cursor() as cur:
            log.info("Fetching core trial roster ...")
            cores = _fetch_core_trials(cur, limit)
            log.info("Found %d trials matching Phase 3 CV criteria.", len(cores))

            if not cores:
                log.warning("No trials found. Writing empty output.")
                _write_json([], output_path)
                return

            nct_ids = [r["nct_id"] for r in cores]

            log.info("Fetching primary outcomes ...")
            all_outcomes = _fetch_primary_outcomes(cur, nct_ids)

            log.info("Fetching interventions ...")
            all_interventions = _fetch_interventions(cur, nct_ids)

            log.info("Fetching facilities ...")
            all_facilities = _fetch_facilities(cur, nct_ids)

            log.info("Fetching eligibility criteria ...")
            all_eligibilities = _fetch_eligibilities(cur, nct_ids)

        records = []
        for core in cores:
            nct = core["nct_id"]
            rec = _assemble_record(
                core=core,
                outcomes=all_outcomes.get(nct, []),
                interv_data=all_interventions.get(nct, {"interventions": [], "has_placebo": False}),
                facility=all_facilities.get(nct, {"num_sites": 0, "num_countries": 0}),
                criteria=all_eligibilities.get(nct),
            )
            records.append(rec)

        log.info("Assembled %d records. Writing to %s ...", len(records), output_path)
        _write_json(records, output_path)
        log.info("Done.")

    finally:
        conn.close()


def _write_json(records: list, path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Extract Phase 3 CV trial data from AACT PostgreSQL."
    )
    parser.add_argument(
        "--output",
        default="data/raw_trials.json",
        help="Output JSON file path (default: data/raw_trials.json)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of trials (for testing; default: no limit)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    extract_trials(output_path=args.output, limit=args.limit)

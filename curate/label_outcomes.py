"""
label_outcomes.py — CardioOracle 3-tier outcome labeling module.

Assigns success/failure/safety_failure labels to extracted trials using a
priority-ordered tier system:

  Tier 1 (highest priority)
    a) Terminated trials: why_stopped text → futility → FAILURE,
       safety keywords → SAFETY_FAIL
    b) Primary outcome p-value < 0.05 AND effect favors intervention → SUCCESS
       p-value >= 0.05 → FAILURE

  Tier 2 (used when Tier 1 cannot label)
    a) CI-based: for ratio params, CI upper < 1.0 → SUCCESS;
       CI lower > 1.0 → FAILURE (harm direction); else → FAILURE
    b) Multiple primaries: if any primary has p < 0.05 → SUCCESS (partial)

  Tier 3 (overrides all automated logic)
    Manually curated landmark_trials.json entries take priority over everything.

Usage:
    python curate/label_outcomes.py --input data/raw_trials.json \\
                                    --landmarks data/landmark_trials.json \\
                                    --output data/labeled_trials.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LABEL_SUCCESS = "success"
LABEL_FAILURE = "failure"
LABEL_SAFETY_FAIL = "safety_failure"

FUTILITY_KEYWORDS = [
    "futility",
    "lack of efficacy",
    "unlikely to demonstrate",
    "no benefit",
    "insufficient efficacy",
]

SAFETY_KEYWORDS = [
    "safety",
    "adverse",
    "harm",
    "toxicity",
    "increased mortality",
    "increased risk",
]

# Lowercase set of ratio-type parameter names
RATIO_PARAMS = {
    "hazard ratio",
    "odds ratio",
    "relative risk",
    "risk ratio",
    "rate ratio",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _effect_favors_intervention(outcome: dict) -> bool:
    """Return True if the effect direction favors the intervention arm.

    For ratio parameters (HR, OR, RR, etc.) a value < 1.0 means the
    intervention arm had fewer events — i.e. it favors the intervention.
    For non-ratio parameters (absolute differences, mean differences, etc.)
    we cannot determine direction reliably, so we return True conservatively
    (caller still requires p < 0.05 to call SUCCESS).
    """
    param_type = (outcome.get("param_type") or "").lower().strip()
    param_value = outcome.get("param_value")

    if param_type in RATIO_PARAMS:
        if param_value is None:
            return False
        return float(param_value) < 1.0

    # Non-ratio params: assume favors intervention (p-value gate is the
    # primary guard for Tier 1b; direction is ambiguous without sign convention)
    return True


def _parse_p_value(raw) -> Optional[float]:
    """Parse a p-value field that may be a float, string, or None.

    Handles common prefixes such as '<0.001', '=0.04', '0.05', etc.
    Returns None if the value cannot be parsed.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    # String handling
    s = str(raw).strip().lstrip("<>=").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _is_ratio_param(outcome: dict) -> bool:
    """Return True if outcome uses a ratio-scale parameter type."""
    param_type = (outcome.get("param_type") or "").lower().strip()
    return param_type in RATIO_PARAMS


# ---------------------------------------------------------------------------
# Core labeling logic
# ---------------------------------------------------------------------------

def label_trial(trial: dict) -> tuple:
    """Assign a label to a single trial record.

    Parameters
    ----------
    trial : dict
        A trial record as produced by extract_aact.py.  Relevant fields:
          - why_stopped      : str | None
          - status           : str | None  (e.g. 'Terminated', 'Completed')
          - primary_outcomes : list of outcome dicts, each with
              title, p_value, ci_lower, ci_upper, param_type, param_value

    Returns
    -------
    (label, tier, reason) : tuple
        label  — one of LABEL_SUCCESS, LABEL_FAILURE, LABEL_SAFETY_FAIL, or None
        tier   — 1, 2, or None
        reason — human-readable string explaining the decision
    """
    status = (trial.get("status") or "").strip()
    why_stopped = (trial.get("why_stopped") or "").strip()
    outcomes = trial.get("primary_outcomes") or []

    # ------------------------------------------------------------------
    # Tier 1a: Terminated trials — inspect why_stopped
    # ------------------------------------------------------------------
    if status.lower() == "terminated" and why_stopped:
        why_lower = why_stopped.lower()

        # Safety check first (higher severity)
        for kw in SAFETY_KEYWORDS:
            if kw in why_lower:
                return (
                    LABEL_SAFETY_FAIL,
                    1,
                    f"Terminated: safety keyword '{kw}' in why_stopped: {why_stopped!r}",
                )

        # Futility / lack of efficacy
        for kw in FUTILITY_KEYWORDS:
            if kw in why_lower:
                return (
                    LABEL_FAILURE,
                    1,
                    f"Terminated: futility keyword '{kw}' in why_stopped: {why_stopped!r}",
                )

    # ------------------------------------------------------------------
    # Tier 1b: p-value labeling
    # ------------------------------------------------------------------
    # Collect outcomes that have a usable p-value
    outcomes_with_p = []
    for oc in outcomes:
        p = _parse_p_value(oc.get("p_value"))
        if p is not None:
            outcomes_with_p.append((oc, p))

    if outcomes_with_p:
        # Single primary or use the first primary with a p-value
        oc, p = outcomes_with_p[0]
        if p < 0.05:
            if _effect_favors_intervention(oc):
                return (
                    LABEL_SUCCESS,
                    1,
                    f"Primary outcome p={p:.4g} < 0.05 with effect favoring intervention "
                    f"(param_type={oc.get('param_type')!r}, "
                    f"param_value={oc.get('param_value')!r})",
                )
            else:
                # p < 0.05 but effect goes against intervention (harm signal)
                return (
                    LABEL_FAILURE,
                    1,
                    f"Primary outcome p={p:.4g} < 0.05 but effect does NOT favor intervention "
                    f"(param_type={oc.get('param_type')!r}, "
                    f"param_value={oc.get('param_value')!r})",
                )
        else:
            return (
                LABEL_FAILURE,
                1,
                f"Primary outcome p={p:.4g} >= 0.05 (not statistically significant)",
            )

    # ------------------------------------------------------------------
    # Tier 2a: CI-based labeling (for ratio params)
    # ------------------------------------------------------------------
    ratio_outcomes = [oc for oc in outcomes if _is_ratio_param(oc)]
    for oc in ratio_outcomes:
        ci_lower = oc.get("ci_lower")
        ci_upper = oc.get("ci_upper")
        if ci_lower is None or ci_upper is None:
            continue
        ci_lower = float(ci_lower)
        ci_upper = float(ci_upper)
        if ci_upper < 1.0:
            return (
                LABEL_SUCCESS,
                2,
                f"CI entirely below 1.0: [{ci_lower:.3g}, {ci_upper:.3g}] "
                f"(param_type={oc.get('param_type')!r})",
            )
        # CI includes or is entirely above 1.0 → no significant benefit
        return (
            LABEL_FAILURE,
            2,
            f"CI includes or exceeds 1.0: [{ci_lower:.3g}, {ci_upper:.3g}] "
            f"(param_type={oc.get('param_type')!r})",
        )

    # ------------------------------------------------------------------
    # Tier 2b: Multiple primaries — any p < 0.05 → partial success
    # ------------------------------------------------------------------
    if len(outcomes) > 1 and outcomes_with_p:
        # outcomes_with_p already filtered; check if any is significant
        sig = [(oc, p) for oc, p in outcomes_with_p if p < 0.05]
        if sig:
            oc, p = sig[0]
            return (
                LABEL_SUCCESS,
                2,
                f"Multiple primaries: at least one significant (p={p:.4g} < 0.05) — "
                f"partial success",
            )

    # ------------------------------------------------------------------
    # Unlabelable — insufficient data
    # ------------------------------------------------------------------
    return (
        None,
        None,
        "Insufficient data: no usable p-value, CI, or termination reason found",
    )


# ---------------------------------------------------------------------------
# Batch labeling
# ---------------------------------------------------------------------------

def label_all(
    raw_trials: list,
    landmark_overrides: Optional[dict] = None,
) -> tuple:
    """Label all trials and return (labeled_list, stats_dict).

    Parameters
    ----------
    raw_trials : list
        Trial records from extract_aact.py.
    landmark_overrides : dict | None
        Mapping of nct_id → {"label": ..., "name": ..., "source": ...}.
        Tier 3 overrides: entries here always take priority.

    Returns
    -------
    labeled_list : list
        Only trials where a label was assigned (not None).  Each record is
        the original trial dict augmented with:
          - label         : str
          - label_tier    : int
          - label_reason  : str
    stats_dict : dict
        {"tier1": int, "tier2": int, "tier3": int, "unlabeled": int, "total": int}
    """
    if landmark_overrides is None:
        landmark_overrides = {}

    labeled = []
    stats = {"tier1": 0, "tier2": 0, "tier3": 0, "unlabeled": 0, "total": len(raw_trials)}

    for trial in raw_trials:
        nct_id = trial.get("nct_id", "")

        # Tier 3: landmark override takes priority
        if nct_id in landmark_overrides:
            override = landmark_overrides[nct_id]
            rec = dict(trial)
            rec["label"] = override["label"]
            rec["label_tier"] = 3
            rec["label_reason"] = (
                f"Landmark override: {override.get('name', nct_id)} — "
                f"{override.get('source', 'manual curation')}"
            )
            labeled.append(rec)
            stats["tier3"] += 1
            continue

        # Automated labeling (Tier 1 / Tier 2)
        label, tier, reason = label_trial(trial)

        if label is None:
            stats["unlabeled"] += 1
            continue

        rec = dict(trial)
        rec["label"] = label
        rec["label_tier"] = tier
        rec["label_reason"] = reason
        labeled.append(rec)

        if tier == 1:
            stats["tier1"] += 1
        elif tier == 2:
            stats["tier2"] += 1

    return labeled, stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_landmarks(path: str) -> dict:
    """Load landmark_trials.json and return a dict keyed by nct_id."""
    p = Path(path)
    if not p.exists():
        log.warning("Landmark file not found: %s — no overrides applied.", path)
        return {}
    with p.open(encoding="utf-8") as fh:
        entries = json.load(fh)
    return {e["nct_id"]: e for e in entries}


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Assign success/failure labels to extracted CardioOracle trials."
    )
    parser.add_argument(
        "--input",
        default="data/raw_trials.json",
        help="Input JSON file produced by extract_aact.py (default: data/raw_trials.json)",
    )
    parser.add_argument(
        "--landmarks",
        default="data/landmark_trials.json",
        help="Landmark override file (default: data/landmark_trials.json)",
    )
    parser.add_argument(
        "--output",
        default="data/labeled_trials.json",
        help="Output JSON file path (default: data/labeled_trials.json)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        log.error("Input file not found: %s", args.input)
        sys.exit(1)

    with input_path.open(encoding="utf-8") as fh:
        raw_trials = json.load(fh)
    log.info("Loaded %d trials from %s", len(raw_trials), args.input)

    landmark_overrides = _load_landmarks(args.landmarks)
    log.info("Loaded %d landmark overrides from %s", len(landmark_overrides), args.landmarks)

    labeled, stats = label_all(raw_trials, landmark_overrides)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(labeled, fh, indent=2, ensure_ascii=False)

    log.info(
        "Labeled %d / %d trials  "
        "(tier1=%d, tier2=%d, tier3=%d, unlabeled=%d)",
        len(labeled),
        stats["total"],
        stats["tier1"],
        stats["tier2"],
        stats["tier3"],
        stats["unlabeled"],
    )
    log.info("Output written to %s", args.output)


if __name__ == "__main__":
    main()

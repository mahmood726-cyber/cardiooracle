"""
validate_labels.py — CardioOracle label validation script.

Cross-checks pipeline-generated labels against gold-standard landmark_trials.json.
Compares nct_id, label type, and provides detailed mismatch reporting.

Usage:
    python curate/validate_labels.py --labeled data/labeled_trials.json \\
                                     --landmarks data/landmark_trials.json

Exit code: 0 if validation passes (0 mismatches, 0 missing), 1 otherwise.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Tuple, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LABEL_SAFETY_FAIL = "safety_failure"


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------

def validate(labeled_trials: List[dict], landmarks: List[dict]) -> Tuple[bool, Dict]:
    """Cross-check labeled trials against landmark gold standard.

    Parameters
    ----------
    labeled_trials : list of dict
        Trials labeled by the pipeline, each with at minimum:
          - nct_id : str
          - label  : str (one of "success", "failure", "safety_failure")
    landmarks : list of dict
        Gold-standard landmark trials, each with:
          - nct_id  : str
          - label   : str
          - name    : str (trial name)
          - source  : str (publication reference)

    Returns
    -------
    (success : bool, report : dict)
        success : bool
            True if 0 mismatches and 0 missing; False otherwise.
        report : dict
            Detailed validation report with keys:
              - landmarks_checked    : int
              - landmarks_found      : int
              - landmarks_missing    : int
              - correct_labels       : int
              - mismatched_labels    : int
              - accuracy             : float (0.0-1.0)
              - missing_details      : list of dicts
              - mismatch_details     : list of dicts
    """
    # Build a map of labeled trials by nct_id
    labeled_map = {trial.get("nct_id"): trial for trial in labeled_trials if trial.get("nct_id")}

    # Initialize counters
    landmarks_checked = len(landmarks)
    landmarks_found = 0
    landmarks_missing = 0
    correct_labels = 0
    mismatched_labels = 0
    missing_details = []
    mismatch_details = []

    # Check each landmark
    for landmark in landmarks:
        nct_id = landmark.get("nct_id")
        expected_label = landmark.get("label")
        name = landmark.get("name", nct_id)
        source = landmark.get("source", "unknown source")

        if nct_id not in labeled_map:
            # Missing from labeled results
            landmarks_missing += 1
            missing_details.append({
                "nct_id": nct_id,
                "name": name,
                "expected_label": expected_label,
                "source": source,
            })
            continue

        # Found in labeled results
        landmarks_found += 1
        labeled_trial = labeled_map[nct_id]
        actual_label = labeled_trial.get("label")

        # Compare labels (treat safety_failure as failure for comparison purposes)
        expected_normalized = expected_label
        actual_normalized = actual_label if actual_label != LABEL_SAFETY_FAIL else "failure"

        if expected_normalized == actual_normalized:
            correct_labels += 1
        else:
            mismatched_labels += 1
            mismatch_details.append({
                "nct_id": nct_id,
                "name": name,
                "expected_label": expected_label,
                "actual_label": actual_label,
                "label_tier": labeled_trial.get("label_tier"),
                "label_reason": labeled_trial.get("label_reason", ""),
                "source": source,
            })

    # Calculate accuracy
    accuracy = correct_labels / landmarks_found if landmarks_found > 0 else 0.0

    # Build report
    report = {
        "landmarks_checked": landmarks_checked,
        "landmarks_found": landmarks_found,
        "landmarks_missing": landmarks_missing,
        "correct_labels": correct_labels,
        "mismatched_labels": mismatched_labels,
        "accuracy": accuracy,
        "missing_details": missing_details,
        "mismatch_details": mismatch_details,
    }

    # Success if no mismatches and no missing
    success = (landmarks_missing == 0) and (mismatched_labels == 0)

    return success, report


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(report: Dict) -> None:
    """Print a formatted validation report to stdout."""
    print("\n" + "=" * 80)
    print("LANDMARK VALIDATION REPORT")
    print("=" * 80)

    print(f"\nLandmarks checked:    {report['landmarks_checked']}")
    print(f"Landmarks found:      {report['landmarks_found']}")
    print(f"Landmarks missing:    {report['landmarks_missing']}")
    print(f"Correct labels:       {report['correct_labels']}")
    print(f"Mismatched labels:    {report['mismatched_labels']}")
    print(f"Accuracy:             {report['accuracy']:.1%}")

    if report["missing_details"]:
        print(f"\n{'-' * 80}")
        print("MISSING LANDMARKS (not in labeled_trials.json):")
        print(f"{'-' * 80}")
        for detail in report["missing_details"]:
            print(f"  {detail['nct_id']:20s} {detail['name']:30s} "
                  f"expected={detail['expected_label']:15s} "
                  f"source={detail['source'][:50]}")

    if report["mismatch_details"]:
        print(f"\n{'-' * 80}")
        print("MISMATCHED LABELS:")
        print(f"{'-' * 80}")
        for detail in report["mismatch_details"]:
            print(f"\n  {detail['nct_id']:20s} {detail['name']}")
            print(f"    Expected:  {detail['expected_label']}")
            print(f"    Actual:    {detail['actual_label']} (tier {detail['label_tier']})")
            print(f"    Reason:    {detail['label_reason'][:70]}")
            print(f"    Source:    {detail['source'][:70]}")

    print("\n" + "=" * 80)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _load_json(path: str) -> list:
    """Load and return JSON array from file."""
    p = Path(path)
    if not p.exists():
        log.error("File not found: %s", path)
        sys.exit(1)
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate pipeline-generated labels against landmark gold standard."
    )
    parser.add_argument(
        "--labeled",
        default="data/labeled_trials.json",
        help="Path to labeled_trials.json from pipeline (default: data/labeled_trials.json)",
    )
    parser.add_argument(
        "--landmarks",
        default="data/landmark_trials.json",
        help="Path to landmark_trials.json gold standard (default: data/landmark_trials.json)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(argv)

    log.info("Loading labeled trials from %s", args.labeled)
    labeled = _load_json(args.labeled)
    log.info("Loaded %d labeled trials", len(labeled))

    log.info("Loading landmarks from %s", args.landmarks)
    landmarks = _load_json(args.landmarks)
    log.info("Loaded %d landmarks", len(landmarks))

    success, report = validate(labeled, landmarks)

    print_report(report)

    if success:
        log.info("✓ Validation passed: all landmarks match correctly")
        sys.exit(0)
    else:
        log.error("✗ Validation failed: %d mismatches, %d missing",
                  report["mismatched_labels"], report["landmarks_missing"])
        sys.exit(1)


if __name__ == "__main__":
    main()

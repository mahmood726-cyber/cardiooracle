"""
export_training.py — CardioOracle training data export for HTML embedding.

Exports a curated, versioned JSON bundle of labeled trial features suitable for
embedding in the CardioOracle HTML app.  The bundle includes a SHA-256 content
hash for TruthCert provenance tracking.

Usage:
    python curate/export_training.py --labeled data/labeled_trials.json \\
                                     --config data/export_config.json \\
                                     --output data/training_export.json
"""

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default export config (used when --config is not supplied)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "id": "cardiooracle_v1",
    "description": "CardioOracle training export v1.0",
}


# ---------------------------------------------------------------------------
# Base rate computation
# ---------------------------------------------------------------------------


def compute_class_base_rates(trials: list) -> dict:
    """Compute per-drug-class success rates from labeled trial records.

    Parameters
    ----------
    trials : list
        Labeled trial records. Each record is expected to have:
          - drug_class (str | None)
          - label (str | None) — one of "success", "failure", "safety_failure"

    Returns
    -------
    dict mapping drug_class → float (success rate, 0.0–1.0).
    Classes with zero trials are omitted.
    """
    counts: dict = {}   # drug_class → {"success": int, "total": int}

    for t in trials:
        drug_class = t.get("drug_class") or "other"
        label = t.get("label") or ""

        if drug_class not in counts:
            counts[drug_class] = {"success": 0, "total": 0}

        counts[drug_class]["total"] += 1
        if label == "success":
            counts[drug_class]["success"] += 1

    result = {}
    for cls, c in counts.items():
        if c["total"] > 0:
            result[cls] = round(c["success"] / c["total"], 6)

    return result


# ---------------------------------------------------------------------------
# Export function
# ---------------------------------------------------------------------------


def export_training_data(labeled_trials: list, config: Optional[dict] = None) -> dict:
    """Build the training data export bundle.

    Parameters
    ----------
    labeled_trials : list
        Output from label_all (records with label, label_tier, label_reason).
    config : dict | None
        Export configuration with at least {"id": str}. Defaults to DEFAULT_CONFIG.

    Returns
    -------
    dict with keys:
        version           : str
        generated         : str (ISO 8601 UTC)
        config_id         : str
        content_hash      : str (SHA-256 hex of the trials array JSON)
        n_trials          : int
        class_base_rates  : dict
        trials            : list of per-trial feature dicts
    """
    if config is None:
        config = DEFAULT_CONFIG

    # Compute per-class base rates first (used to inject into each trial record)
    class_base_rates = compute_class_base_rates(labeled_trials)

    # Build per-trial feature records
    trial_records = []
    for t in labeled_trials:
        drug_class = t.get("drug_class") or "other"

        # Inject historical_class_rate from class_base_rates
        # Use `if ... is not None` pattern — never `x or default` (drops valid 0)
        hist_rate = (
            t.get("historical_class_rate")
            if t.get("historical_class_rate") is not None
            else class_base_rates.get(drug_class, 0.45)
        )

        features = {
            "enrollment": t.get("enrollment"),
            "duration_months": t.get("duration_months"),
            "placebo_controlled": t.get("placebo_controlled"),
            "double_blind": t.get("double_blind"),
            "is_industry": t.get("is_industry"),
            "num_sites": t.get("num_sites"),
            "multi_regional": t.get("multi_regional"),
            "endpoint_type": t.get("endpoint_type"),
            "drug_class": drug_class,
            "comparator_type": t.get("comparator_type"),
            "num_arms": t.get("num_arms"),
            "has_dsmb": t.get("has_dsmb"),
            "start_year": t.get("start_year"),
            "population_tags": t.get("population_tags") or [],
            "historical_class_rate": hist_rate,
        }

        record = {
            "nct_id": t.get("nct_id", ""),
            "title": t.get("title") or t.get("brief_title") or "",
            "label": t.get("label"),
            "label_tier": t.get("label_tier"),
            "features": features,
        }
        trial_records.append(record)

    # SHA-256 of the serialized trials array (deterministic sort for reproducibility)
    trials_json = json.dumps(trial_records, sort_keys=True, ensure_ascii=False)
    content_hash = hashlib.sha256(trials_json.encode("utf-8")).hexdigest()

    bundle = {
        "version": "1.0.0",
        "generated": datetime.now(timezone.utc).isoformat(),
        "config_id": config.get("id", "unknown"),
        "content_hash": content_hash,
        "n_trials": len(trial_records),
        "class_base_rates": class_base_rates,
        "trials": trial_records,
    }

    return bundle


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Export CardioOracle labeled training data for HTML embedding."
    )
    parser.add_argument(
        "--labeled",
        default="data/labeled_trials.json",
        help="Labeled trials JSON (default: data/labeled_trials.json)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Export config JSON file (optional; uses built-in defaults if omitted)",
    )
    parser.add_argument(
        "--output",
        default="data/training_export.json",
        help="Output path for training bundle (default: data/training_export.json)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(argv)

    labeled_path = Path(args.labeled)
    if not labeled_path.exists():
        log.error("Labeled trials file not found: %s", args.labeled)
        sys.exit(1)

    with labeled_path.open(encoding="utf-8") as fh:
        labeled_trials = json.load(fh)
    log.info("Loaded %d labeled trials from %s", len(labeled_trials), args.labeled)

    config = DEFAULT_CONFIG
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            log.error("Config file not found: %s", args.config)
            sys.exit(1)
        with config_path.open(encoding="utf-8") as fh:
            config = json.load(fh)
        log.info("Loaded export config from %s  (id=%s)", args.config, config.get("id"))

    bundle = export_training_data(labeled_trials, config)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2, ensure_ascii=False)

    log.info(
        "Training export written to %s  "
        "(n=%d, hash=%s...)",
        args.output,
        bundle["n_trials"],
        bundle["content_hash"][:16],
    )


if __name__ == "__main__":
    main()

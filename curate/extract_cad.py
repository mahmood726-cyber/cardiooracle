"""
extract_cad.py — CAD-specific trial extraction from AACT for CardioOracle.

Thin wrapper around extract_aact.py that uses a CAD-specific PostgreSQL
SIMILAR TO condition pattern (coronary, MI, ACS, angina, atherosclerosis,
PCI, CABG, stent).

Usage:
    python curate/extract_cad.py [--output data/raw_cad_trials.json] [--limit N]
"""

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from .extract_aact import extract_trials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# CAD-specific SIMILAR TO pattern for the ctgov.conditions.name column.
# PostgreSQL SIMILAR TO uses SQL-style regex: | for alternation, % for wildcard.
# The leading and trailing % ensure substring matching anywhere in the name.
CAD_SIMILAR_TO = (
    "%(coronary"
    "|myocardial infarction"
    "|acute coronary"
    "|angina"
    "|ischemic heart"
    "|atheroscler"
    "|percutaneous coronary"
    "|stent"
    "|bypass graft"
    "|cabg)%"
)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Extract Phase 3 CAD trial data from AACT PostgreSQL."
    )
    parser.add_argument(
        "--output",
        default="data/raw_cad_trials.json",
        help="Output JSON file path (default: data/raw_cad_trials.json)",
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
    log.info("Starting CAD extraction with pattern: %s", CAD_SIMILAR_TO)
    extract_trials(
        output_path=args.output,
        limit=args.limit,
        condition_pattern=CAD_SIMILAR_TO,
    )
    log.info("CAD extraction complete -> %s", args.output)

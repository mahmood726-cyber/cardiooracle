"""
fit_model.py — CardioOracle logistic regression model fitting with temporal validation.

Fits a logistic regression model on labeled trial features and exports:
  - model coefficients
  - in-sample metrics (AUC, Brier score)
  - temporal split metrics (train/test by primary_completion_date)

Usage:
    python curate/fit_model.py --input data/labeled_trials.json \\
                               --output data/model_coefficients.json
"""

import argparse
import json
import logging
import math
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FEATURE_NAMES = [
    "log_enrollment",
    "duration_months",
    "placebo_controlled",
    "double_blind",
    "is_industry",
    "log_num_sites",
    "multi_regional",
    "num_arms",
    "has_dsmb",
    "ep_mace",
    "ep_hf_hosp",
    "ep_cv_death",
    "ep_acm",
    "ep_renal",
    "ep_surrogate",
    "era_2010_2017",
    "era_2018plus",
    "historical_class_rate",
]


# ---------------------------------------------------------------------------
# Era bucketing
# ---------------------------------------------------------------------------


def _era_bucket(year) -> str:
    """Return era bucket string for a given year.

    Parameters
    ----------
    year : int | None

    Returns
    -------
    "pre2010" | "2010_2017" | "2018plus" | "unknown"
    """
    if year is None:
        return "unknown"
    try:
        y = int(year)
    except (ValueError, TypeError):
        return "unknown"

    if y < 2010:
        return "pre2010"
    if y <= 2017:
        return "2010_2017"
    return "2018plus"


# ---------------------------------------------------------------------------
# Feature matrix construction
# ---------------------------------------------------------------------------


def prepare_feature_matrix(trials: list) -> tuple:
    """Build the 18-feature matrix from a list of labeled trial dicts.

    Parameters
    ----------
    trials : list
        Labeled trial records (from label_all or labeled_trials.json).
        Expected to have 'label' field and feature fields.

    Returns
    -------
    X : np.ndarray, shape (n_trials, 18)
    y : np.ndarray, shape (n_trials,)  — 1 for "success", 0 otherwise
    feature_names : list[str]
    """
    rows = []
    labels = []

    for t in trials:
        # --- Safe feature extraction (never use `x or default` — drops valid 0) ---
        enr = t.get("enrollment") if t.get("enrollment") is not None else 100
        nsites = t.get("num_sites") if t.get("num_sites") is not None else 1
        dur = t.get("duration_months") if t.get("duration_months") is not None else 24
        narms = t.get("num_arms") if t.get("num_arms") is not None else 2
        hist_rate = (
            t.get("historical_class_rate")
            if t.get("historical_class_rate") is not None
            else 0.45
        )

        # Guard against non-positive values before log
        enr_safe = max(float(enr), 1.0)
        nsites_safe = max(float(nsites), 1.0)

        log_enrollment = math.log(enr_safe)
        log_num_sites = math.log(nsites_safe)

        # Boolean / indicator features
        placebo_controlled = 1 if t.get("placebo_controlled") else 0
        double_blind = 1 if t.get("double_blind") else 0
        is_industry = 1 if t.get("is_industry") else 0
        multi_regional = 1 if t.get("multi_regional") else 0
        has_dsmb = 1 if t.get("has_dsmb") else 0

        # Endpoint type one-hot
        ep_type = (t.get("endpoint_type") or "").lower()
        ep_mace = 1 if ep_type == "mace" else 0
        ep_hf_hosp = 1 if ep_type == "hf_hosp" else 0
        ep_cv_death = 1 if ep_type == "cv_death" else 0
        ep_acm = 1 if ep_type == "acm" else 0
        ep_renal = 1 if ep_type == "renal" else 0
        ep_surrogate = 1 if ep_type == "surrogate" else 0

        # Era one-hot (pre2010 is the reference category)
        start_year = t.get("start_year")
        era = _era_bucket(start_year)
        era_2010_2017 = 1 if era == "2010_2017" else 0
        era_2018plus = 1 if era == "2018plus" else 0

        row = [
            log_enrollment,
            float(dur),
            placebo_controlled,
            double_blind,
            is_industry,
            log_num_sites,
            multi_regional,
            float(narms),
            has_dsmb,
            ep_mace,
            ep_hf_hosp,
            ep_cv_death,
            ep_acm,
            ep_renal,
            ep_surrogate,
            era_2010_2017,
            era_2018plus,
            float(hist_rate),
        ]
        rows.append(row)

        # y: 1 for success, 0 for everything else (failure, safety_failure)
        label_val = 1 if (t.get("label") or "") == "success" else 0
        labels.append(label_val)

    X = np.array(rows, dtype=float)
    y = np.array(labels, dtype=float)
    return X, y, list(FEATURE_NAMES)


# ---------------------------------------------------------------------------
# Model fitting
# ---------------------------------------------------------------------------


def _compute_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Compute AUC via trapezoidal rule (no sklearn required)."""
    # Sort by descending predicted probability
    order = np.argsort(-y_prob)
    y_true_sorted = y_true[order]

    n_pos = float(y_true.sum())
    n_neg = float(len(y_true) - n_pos)

    if n_pos == 0 or n_neg == 0:
        return float("nan")

    tp = 0.0
    fp = 0.0
    auc = 0.0
    prev_fp = 0.0

    for yt in y_true_sorted:
        if yt == 1:
            tp += 1
        else:
            fp += 1
            auc += tp  # trapezoidal increment

    # Normalise
    auc = auc / (n_pos * n_neg)
    return float(auc)


def _brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Mean squared error between predicted probabilities and outcomes."""
    return float(np.mean((y_true - y_prob) ** 2))


def fit_logistic_model(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list,
) -> dict:
    """Fit an L2-regularised logistic regression and return coefficients + metrics.

    Parameters
    ----------
    X : np.ndarray, shape (n, p)
    y : np.ndarray, shape (n,)
    feature_names : list[str]

    Returns
    -------
    dict with keys:
        coefficients : {intercept, feature_name: float, ...}
        insample_metrics : {auc, brier, n}
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    # Standardise features for numerical stability
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    clf = LogisticRegression(
        penalty="l2",
        C=1.0,
        solver="lbfgs",
        max_iter=1000,
        random_state=42,
    )
    clf.fit(X_scaled, y)

    # Build coefficients dict (intercept + named features)
    coef_dict = {"intercept": float(clf.intercept_[0])}
    for name, coef in zip(feature_names, clf.coef_[0]):
        coef_dict[name] = float(coef)

    # In-sample predictions
    y_prob = clf.predict_proba(X_scaled)[:, 1]
    auc = _compute_auc(y, y_prob)
    brier = _brier_score(y, y_prob)

    return {
        "coefficients": coef_dict,
        "insample_metrics": {
            "auc": auc,
            "brier": brier,
            "n": int(len(y)),
        },
        # Store scaler parameters so predictions can be reproduced
        "_scaler_mean": scaler.mean_.tolist(),
        "_scaler_scale": scaler.scale_.tolist(),
    }


# ---------------------------------------------------------------------------
# Temporal split metrics
# ---------------------------------------------------------------------------


def _parse_date(raw) -> Optional[date]:
    """Parse a date string 'YYYY-MM-DD' → date, or return None."""
    if raw is None:
        return None
    try:
        parts = str(raw).split("-")
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, AttributeError):
        pass
    return None


def _calibration_slope(y_true: np.ndarray, y_prob: np.ndarray) -> Optional[float]:
    """Ordinary least squares calibration slope (regress y_true on logit(y_prob)).

    Returns None if fewer than 2 observations or all predictions are 0/1.
    """
    if len(y_true) < 2:
        return None

    eps = 1e-7
    logit_prob = np.log(np.clip(y_prob, eps, 1 - eps) / (1 - np.clip(y_prob, eps, 1 - eps)))

    # OLS: slope = cov(x, y) / var(x)
    var_x = np.var(logit_prob)
    if var_x < 1e-12:
        return None

    cov_xy = np.mean((logit_prob - logit_prob.mean()) * (y_true - y_true.mean()))
    return float(cov_xy / var_x)


def compute_temporal_split_metrics(
    trials: list,
    coefficients: dict,
    feature_names: list,
    split_date: str = "2020-01-01",
) -> dict:
    """Evaluate model on temporal train/test split.

    Parameters
    ----------
    trials : list
        Labeled trial records.
    coefficients : dict
        Coefficient dict from fit_logistic_model (keyed by feature name + "intercept").
    feature_names : list[str]
        Ordered list matching coefficient keys (excluding intercept).
    split_date : str
        ISO date string 'YYYY-MM-DD'. Trials before → train; on/after → test.

    Returns
    -------
    dict with keys:
        split_date, n_train, n_test,
        test_metrics: {auc, brier, calibration_slope},
        trial_predictions: list of {nct_id, y_true, y_prob, split}
    """
    cutoff = _parse_date(split_date)
    if cutoff is None:
        raise ValueError(f"Cannot parse split_date: {split_date!r}")

    train_trials = []
    test_trials = []

    for t in trials:
        pc_date = _parse_date(t.get("primary_completion_date"))
        if pc_date is not None and pc_date < cutoff:
            train_trials.append(t)
        else:
            test_trials.append(t)

    # Build weight vector from coefficients
    intercept = coefficients.get("intercept", 0.0)
    coef_vec = np.array([coefficients.get(fn, 0.0) for fn in feature_names], dtype=float)

    def _predict(trial_list):
        if not trial_list:
            return np.array([]), np.array([])
        X, y, _ = prepare_feature_matrix(trial_list)
        # Apply raw (unscaled) prediction — coefficients already absorb scaling
        # from fit_logistic_model; here we replicate using stored coefficients
        logit = X @ coef_vec + intercept
        prob = 1.0 / (1.0 + np.exp(-logit))
        return y, prob

    y_test, p_test = _predict(test_trials)

    # Per-trial predictions for Calibration tab
    trial_predictions = []
    for split_label, trial_list in [("train", train_trials), ("test", test_trials)]:
        for i, t in enumerate(trial_list):
            X_single, y_single, _ = prepare_feature_matrix([t])
            logit_val = float(X_single[0] @ coef_vec + intercept)
            prob_val = 1.0 / (1.0 + math.exp(-logit_val))
            trial_predictions.append(
                {
                    "nct_id": t.get("nct_id", ""),
                    "y_true": int(y_single[0]),
                    "y_prob": prob_val,
                    "split": split_label,
                }
            )

    test_metrics = {}
    if len(y_test) > 0:
        test_metrics["auc"] = _compute_auc(y_test, p_test)
        test_metrics["brier"] = _brier_score(y_test, p_test)
        test_metrics["calibration_slope"] = _calibration_slope(y_test, p_test)
    else:
        test_metrics = {"auc": None, "brier": None, "calibration_slope": None}

    return {
        "split_date": split_date,
        "n_train": len(train_trials),
        "n_test": len(test_trials),
        "test_metrics": test_metrics,
        "trial_predictions": trial_predictions,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Fit CardioOracle logistic regression model on labeled trials."
    )
    parser.add_argument(
        "--input",
        default="data/labeled_trials.json",
        help="Labeled trials JSON (default: data/labeled_trials.json)",
    )
    parser.add_argument(
        "--output",
        default="data/model_coefficients.json",
        help="Output path for coefficients + metrics (default: data/model_coefficients.json)",
    )
    parser.add_argument(
        "--split-date",
        default="2020-01-01",
        dest="split_date",
        help="ISO date for temporal train/test split (default: 2020-01-01)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        log.error("Input file not found: %s", args.input)
        sys.exit(1)

    with input_path.open(encoding="utf-8") as fh:
        trials = json.load(fh)
    log.info("Loaded %d labeled trials from %s", len(trials), args.input)

    X, y, feature_names = prepare_feature_matrix(trials)
    log.info("Feature matrix: X=%s  y=%s (%.1f%% success)", X.shape, y.shape, 100 * y.mean())

    model = fit_logistic_model(X, y, feature_names)
    log.info(
        "Model fit: in-sample AUC=%.3f  Brier=%.3f  n=%d",
        model["insample_metrics"]["auc"],
        model["insample_metrics"]["brier"],
        model["insample_metrics"]["n"],
    )

    temporal = compute_temporal_split_metrics(
        trials,
        model["coefficients"],
        feature_names,
        split_date=args.split_date,
    )
    log.info(
        "Temporal split (%s): n_train=%d n_test=%d  test_AUC=%s  test_Brier=%s",
        args.split_date,
        temporal["n_train"],
        temporal["n_test"],
        temporal["test_metrics"]["auc"],
        temporal["test_metrics"]["brier"],
    )

    output = {
        "model": model,
        "temporal_validation": temporal,
        "feature_names": feature_names,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    log.info("Model output written to %s", args.output)


if __name__ == "__main__":
    main()

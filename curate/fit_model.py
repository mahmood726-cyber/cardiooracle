"""
fit_model.py — CardioOracle logistic regression model fitting with temporal validation.

Fits a logistic regression model on labeled trial features and exports:
  - model coefficients
  - in-sample metrics (AUC, Brier score)
  - independent retrospective temporal holdout metrics (training-only refit)

Usage:
    python curate/fit_model.py --input data/labeled_trials.json \\
                               --output data/model_coefficients.json
"""

import argparse
import json
import logging
import math
import platform
import sys
from datetime import date
from pathlib import Path

# Python 3.13 + Windows WMI deadlock workaround: monkey-patch _wmi_query
# before any scipy/sklearn import triggers platform.machine()
if sys.platform == "win32" and hasattr(platform, "_wmi_query"):
    platform._wmi_query = lambda *a, **k: ("10.0.26100", "1", "Multiprocessor Free", "0", "0")
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
    """Area under the ROC curve with correct 0.5 credit for tied scores.

    AUC is the probability a randomly drawn positive has a higher score than
    a randomly drawn negative, plus half the probability of a tie. Iterating
    individual records after sorting incorrectly depends on row order for ties.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)
    if y_true.ndim != 1 or y_prob.ndim != 1 or len(y_true) != len(y_prob):
        raise ValueError("AUC inputs must be equally sized 1-D arrays")
    if not np.all(np.isin(y_true, [0, 1])) or not np.all(np.isfinite(y_prob)):
        raise ValueError("AUC requires binary labels and finite probabilities")

    n_pos = int(np.count_nonzero(y_true == 1))
    n_neg = len(y_true) - n_pos
    if not n_pos or not n_neg:
        return float("nan")

    order = np.argsort(-y_prob, kind="stable")
    scores = y_prob[order]
    labels = y_true[order]
    concordant_pairs = 0.0
    positives_above = 0
    i = 0
    while i < len(scores):
        j = i + 1
        while j < len(scores) and scores[j] == scores[i]:
            j += 1
        positives_tied = int(np.count_nonzero(labels[i:j] == 1))
        negatives_tied = (j - i) - positives_tied
        concordant_pairs += negatives_tied * (positives_above + 0.5 * positives_tied)
        positives_above += positives_tied
        i = j
    return float(concordant_pairs / (n_pos * n_neg))

def _brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Mean squared error between predicted probabilities and outcomes."""
    return float(np.mean((y_true - y_prob) ** 2))


def _fit_platt_sigmoid(logits: np.ndarray, y: np.ndarray, max_iter: int = 100) -> tuple:
    """Fit Platt sigmoid parameters a, b: p = 1/(1+exp(a*f+b)).

    Uses Newton's method (Platt 1999). Returns (a, b).
    """
    n = len(y)
    # Target: t_i = (y_i * (n_pos+1) + 0.5) / (n_pos + 2) for smoothing
    n_pos = float(np.sum(y))
    n_neg = n - n_pos
    t = np.where(y == 1, (n_pos + 1) / (n_pos + 2), 1.0 / (n_neg + 2))

    a, b = 0.0, np.log((n_neg + 1) / (n_pos + 1))

    for _ in range(max_iter):
        p = 1.0 / (1.0 + np.exp(a * logits + b))
        p = np.clip(p, 1e-10, 1 - 1e-10)
        d = p * (1 - p)
        # Gradient
        da = np.sum((t - p) * logits)
        db = np.sum(t - p)
        # Hessian (diagonal approximation)
        haa = -np.sum(d * logits * logits)
        hab = -np.sum(d * logits)
        hbb = -np.sum(d)
        det = haa * hbb - hab * hab
        if abs(det) < 1e-15:
            break
        a -= (hbb * da - hab * db) / det
        b -= (haa * db - hab * da) / det

    return a, b


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

    # Fit directly on raw features — no StandardScaler.
    clf = LogisticRegression(
        penalty="l2",
        C=1.0,
        solver="lbfgs",
        max_iter=1000,
        random_state=42,
    )
    clf.fit(X, y)

    # Build coefficients dict
    coef_dict = {"intercept": float(clf.intercept_[0])}
    for name, coef in zip(feature_names, clf.coef_[0]):
        coef_dict[name] = float(coef)

    # In-sample predictions
    y_prob = clf.predict_proba(X)[:, 1]
    auc = _compute_auc(y, y_prob)
    brier = _brier_score(y, y_prob)

    return {
        "coefficients": coef_dict,
        "insample_metrics": {
            "auc": auc,
            "brier": brier,
            "n": int(len(y)),
        },
    }


def _historical_rates_from_reference(
    reference_trials: list,
    prediction_trials: list,
    leave_one_out: bool = False,
) -> list:
    """Assign drug-class rates using *only* reference (training) outcomes.

    During model fitting each reference record gets a leave-one-out rate,
    avoiding direct target encoding of its own outcome. Holdout rows get the
    rate from the pre-cutoff training cohort only. Pre-existing
    historical_class_rate fields are not trusted because they may have been
    computed across a temporal split.
    """
    counts = {}
    successes = 0
    for trial in reference_trials:
        if trial.get("label") not in ("success", "failure", "safety_failure"):
            raise ValueError("Reference labels must be verified binary outcomes")
        cls = trial.get("drug_class") or "other"
        if cls not in counts:
            counts[cls] = [0, 0]
        outcome = int(trial["label"] == "success")
        counts[cls][0] += 1
        counts[cls][1] += outcome
        successes += outcome

    total = len(reference_trials)
    mapped = []
    for trial in prediction_trials:
        cls = trial.get("drug_class") or "other"
        cls_n, cls_success = counts.get(cls, [0, 0])
        global_n, global_success = total, successes
        if leave_one_out:
            if trial.get("label") not in ("success", "failure", "safety_failure"):
                raise ValueError("Leave-one-out rates require training labels")
            this_success = int(trial["label"] == "success")
            cls_n -= 1
            cls_success -= this_success
            global_n -= 1
            global_success -= this_success

        rate = (cls_success / cls_n if cls_n > 0 else
                global_success / global_n if global_n > 0 else 0.5)
        mapped.append({**trial, "historical_class_rate": rate})
    return mapped


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
    """Logistic calibration slope: coefficient of logit(prediction) in y ~ logit(p).

    Ordinary least-squares regression of a binary outcome on the logit is not
    a logistic calibration slope and must not be reported as one.
    """
    from sklearn.linear_model import LogisticRegression

    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if (len(y_true) < 3 or len(np.unique(y_true)) < 2
            or not np.all(np.isfinite(y_prob))):
        return None

    clipped = np.clip(y_prob, 1e-7, 1 - 1e-7)
    logits = np.log(clipped / (1 - clipped))
    if np.var(logits) < 1e-12:
        return None

    recal = LogisticRegression(penalty=None, solver="lbfgs", max_iter=2000,
                              tol=1e-9)
    recal.fit(logits.reshape(-1, 1), y_true)
    slope = float(recal.coef_[0, 0])
    return slope if math.isfinite(slope) else None

def compute_temporal_split_metrics(
    trials: list,
    coefficients: dict,
    feature_names: list,
    split_date: str = "2020-01-01",
) -> dict:
    """True held-out temporal evaluation, refitting only on pre-cutoff trials.

    The coefficients argument is accepted only for legacy caller compatibility.
    It is deliberately NOT used: coefficients fitted on the complete cohort
    would leak future test outcomes into the supposed temporal validation.

    Primary completion date is an imperfect availability proxy, not proof
    that the trial results were publicly known by the cutoff. Therefore this
    is a retrospective temporal holdout, not prospective validation.
    """
    cutoff = _parse_date(split_date)
    if cutoff is None:
        raise ValueError(f"Cannot parse split_date: {split_date!r}")

    train_trials, test_trials, missing_date = [], [], 0
    for trial in trials:
        completed = _parse_date(trial.get("primary_completion_date"))
        if completed is None:
            missing_date += 1
        elif completed < cutoff:
            train_trials.append(trial)
        else:
            test_trials.append(trial)

    empty_metrics = {"auc": None, "brier": None, "calibration_slope": None}
    result = {
        "split_date": split_date,
        "n_train": len(train_trials),
        "n_test": len(test_trials),
        "n_excluded_missing_date": missing_date,
        "method": "refit_pre_cutoff_only; class rates train-only; unknown dates excluded",
        "caveat": ("Primary completion date does not establish public result "
                   "availability; this is retrospective, not prospective validation."),
        "test_metrics": dict(empty_metrics),
        "trial_predictions": [],
    }
    if len(train_trials) < 3 or not test_trials:
        result["validation_status"] = "insufficient_split_data"
        return result

    safe_train = _historical_rates_from_reference(
        train_trials, train_trials, leave_one_out=True
    )
    safe_test = _historical_rates_from_reference(train_trials, test_trials)
    X_train, y_train, actual_names = prepare_feature_matrix(safe_train)
    if actual_names != feature_names:
        raise ValueError("Feature names do not match model training schema")
    if len(np.unique(y_train)) < 2:
        result["validation_status"] = "single_class_training_cohort"
        return result

    # Fit a separate model. Never evaluate the all-cohort deployed model here.
    heldout_model = fit_logistic_model(X_train, y_train, feature_names)
    fitted = heldout_model["coefficients"]
    weight_vec = np.array([fitted[name] for name in feature_names], dtype=float)
    intercept = fitted["intercept"]

    for group_name, rows in (("train", safe_train), ("test", safe_test)):
        X_group, y_group, _ = prepare_feature_matrix(rows)
        logits = np.clip(X_group @ weight_vec + intercept, -500, 500)
        probs = 1.0 / (1.0 + np.exp(-logits))
        for trial, outcome, probability in zip(rows, y_group, probs):
            result["trial_predictions"].append({
                "nct_id": trial.get("nct_id", ""),
                "y_true": int(outcome),
                "y_prob": float(probability),
                "split": group_name,
            })
        if group_name == "test":
            result["test_metrics"]["brier"] = _brier_score(y_group, probs)
            if len(np.unique(y_group)) >= 2:
                result["test_metrics"]["auc"] = _compute_auc(y_group, probs)
                result["test_metrics"]["calibration_slope"] = _calibration_slope(
                    y_group, probs
                )

    result["validation_status"] = (
        "ok" if result["test_metrics"]["auc"] is not None
        else "single_class_test_cohort"
    )
    result["test_metrics"]["calibration_slope_method"] = "logistic"
    return result

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

    # Fit the released model on the full corpus, but leave each trial's own
    # outcome out of its drug-class historical success rate.
    training_views = _historical_rates_from_reference(trials, trials, leave_one_out=True)
    X, y, feature_names = prepare_feature_matrix(training_views)
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

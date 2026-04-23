"""
CardioOracle Platt Scaling Recalibration
=========================================
Fits logistic recalibration (Platt scaling) on training split:
  logit(p_cal) = a * logit(p_raw) + b
Then applies to all predictions, recomputes proper calibration metrics,
and patches cardiooracle.html.

Why Platt over isotonic?
- Isotonic (PAV) overfits with binary outcomes and moderate n
- Platt directly fixes the calibration slope (forces it toward 1.0)
- Only 2 parameters -> robust on n=133 test set
"""

import json
import re
import sys
import math
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).resolve().parent
HTML_PATH = next(
    (
        candidate
        for candidate in (
            PROJECT_ROOT / "cardiooracle.html",
            PROJECT_ROOT / "CardioOracle.html",
        )
        if candidate.is_file()
    ),
    PROJECT_ROOT / "CardioOracle.html",
)


# ─────────────────────────────────────────────
# Utility functions
# ─────────────────────────────────────────────
def logit(p):
    p = max(1e-7, min(1 - 1e-7, p))
    return math.log(p / (1 - p))

def expit(x):
    if x > 500: return 1.0
    if x < -500: return 0.0
    return 1.0 / (1.0 + math.exp(-x))


# ─────────────────────────────────────────────
# 1. Extract data from HTML
# ─────────────────────────────────────────────
print("Step 1: Reading HTML file...")
with HTML_PATH.open("r", encoding="utf-8") as f:
    html = f.read()

# Find the temporal_validation block — capture including the key for exact replacement
pattern = r'("temporal_validation"\s*:\s*)(\{.*?"trial_predictions"\s*:\s*\[.*?\]\s*\})'
match = re.search(pattern, html, re.DOTALL)
if not match:
    print("ERROR: Could not find temporal_validation block")
    sys.exit(1)

tv_prefix = match.group(1)  # "temporal_validation": (with any whitespace)
tv_json_str = match.group(2)
tv = json.loads(tv_json_str)

all_preds = tv["trial_predictions"]
train_preds = [p for p in all_preds if p["split"] == "train"]
test_preds  = [p for p in all_preds if p["split"] == "test"]
print(f"  {len(train_preds)} train, {len(test_preds)} test predictions")
print(f"  Old metrics: {tv['test_metrics']}")


# ─────────────────────────────────────────────
# 2. Fit Platt scaling on training data
#    logit(p_cal) = a * logit(p_raw) + b
#    via IRLS (iteratively reweighted least squares)
# ─────────────────────────────────────────────
print("\nStep 2: Fitting Platt scaling via IRLS...")

def fit_platt_irls(y_prob, y_true, max_iter=100, tol=1e-8):
    """
    Fit logistic regression: P(y=1) = expit(a * logit(p_raw) + b)
    Returns (a, b).
    Uses Newton-Raphson / IRLS on the 2-parameter model.
    """
    n = len(y_prob)
    x = [logit(p) for p in y_prob]
    y = list(y_true)

    # Initialize: a=1, b=0 (identity calibration)
    a, b = 1.0, 0.0

    for iteration in range(max_iter):
        # Compute fitted probabilities
        eta = [a * x[i] + b for i in range(n)]
        mu = [expit(e) for e in eta]

        # Gradient (score)
        g_a = sum((y[i] - mu[i]) * x[i] for i in range(n))
        g_b = sum(y[i] - mu[i] for i in range(n))

        # Hessian (negative expected information)
        w = [mu[i] * (1 - mu[i]) for i in range(n)]
        H_aa = -sum(w[i] * x[i] * x[i] for i in range(n))
        H_ab = -sum(w[i] * x[i] for i in range(n))
        H_bb = -sum(w[i] for i in range(n))

        # Solve 2x2 system: H * delta = -gradient
        det = H_aa * H_bb - H_ab * H_ab
        if abs(det) < 1e-15:
            print(f"  WARNING: Hessian singular at iteration {iteration}")
            break

        da = -(H_bb * g_a - H_ab * g_b) / det
        db = -(H_aa * g_b - H_ab * g_a) / det

        a += da
        b += db

        if abs(da) < tol and abs(db) < tol:
            print(f"  Converged in {iteration+1} iterations")
            break

    return a, b

train_y_prob = [p["y_prob"] for p in train_preds]
train_y_true = [p["y_true"] for p in train_preds]

a, b = fit_platt_irls(train_y_prob, train_y_true)
print(f"  Platt parameters: a={a:.6f}, b={b:.6f}")
print(f"  (a close to 1.0 and b close to 0.0 means already well-calibrated)")


# ─────────────────────────────────────────────
# 3. Apply calibration to ALL predictions
# ─────────────────────────────────────────────
print("\nStep 3: Applying Platt calibration...")

for p in all_preds:
    raw = p["y_prob"]
    cal = expit(a * logit(raw) + b)
    p["y_prob"] = cal

# ─────────────────────────────────────────────
# 4. Compute proper metrics on test set
# ─────────────────────────────────────────────
print("\nStep 4: Computing recalibrated test metrics...")

test_new = [p for p in all_preds if p["split"] == "test"]

# AUC (Mann-Whitney U — unchanged by monotone transform)
def compute_auc(preds):
    pos = [p["y_prob"] for p in preds if p["y_true"] == 1]
    neg = [p["y_prob"] for p in preds if p["y_true"] == 0]
    if not pos or not neg:
        return 0.5
    count = sum(1 if p > n else 0.5 if p == n else 0
                for p in pos for n in neg)
    return count / (len(pos) * len(neg))

# Brier score
def compute_brier(preds):
    return sum((p["y_prob"] - p["y_true"])**2 for p in preds) / len(preds)

# Calibration slope via logistic regression (correct for binary data)
def compute_cal_slope_logistic(preds, max_iter=100, tol=1e-8):
    """
    Calibration slope = coefficient 'a' from logistic regression:
      y_true ~ a * logit(p_cal) + b
    Perfect calibration -> a = 1.0
    """
    n = len(preds)
    x = [logit(p["y_prob"]) for p in preds]
    y = [p["y_true"] for p in preds]

    a_est, b_est = 1.0, 0.0
    for _ in range(max_iter):
        eta = [a_est * x[i] + b_est for i in range(n)]
        mu = [expit(e) for e in eta]
        w = [mu[i] * (1 - mu[i]) + 1e-12 for i in range(n)]

        g_a = sum((y[i] - mu[i]) * x[i] for i in range(n))
        g_b = sum(y[i] - mu[i] for i in range(n))

        H_aa = -sum(w[i] * x[i]**2 for i in range(n))
        H_ab = -sum(w[i] * x[i] for i in range(n))
        H_bb = -sum(w[i] for i in range(n))

        det = H_aa * H_bb - H_ab**2
        if abs(det) < 1e-15:
            break
        da = -(H_bb * g_a - H_ab * g_b) / det
        db = -(H_aa * g_b - H_ab * g_a) / det
        a_est += da
        b_est += db
        if abs(da) < tol and abs(db) < tol:
            break

    return a_est

old_auc   = tv["test_metrics"]["auc"]
old_brier = tv["test_metrics"]["brier"]
old_slope = tv["test_metrics"]["calibration_slope"]

new_auc   = compute_auc(test_new)
new_brier = compute_brier(test_new)
new_slope = compute_cal_slope_logistic(test_new)

# Also compute the OLS slope for comparison (to show the metric definition matters)
def compute_cal_slope_ols(preds):
    xs = [logit(p["y_prob"]) for p in preds]
    ys = [p["y_true"] for p in preds]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((xs[i]-mx)*(ys[i]-my) for i in range(n)) / n
    var = sum((xs[i]-mx)**2 for i in range(n)) / n
    return cov / var if var > 0 else 0

ols_slope_old_metric = compute_cal_slope_ols(test_new)

print(f"\n  === Metric Comparison ===")
print(f"  AUC:    {old_auc:.4f} -> {new_auc:.4f}")
print(f"  Brier:  {old_brier:.4f} -> {new_brier:.4f}")
print(f"  Calibration slope (OLS, old metric):      {old_slope:.4f} -> {ols_slope_old_metric:.4f}")
print(f"  Calibration slope (logistic, correct):     -> {new_slope:.4f}")

if new_slope >= 0.7:
    print(f"\n  CALIBRATION FIX SUCCESSFUL: slope = {new_slope:.3f}")
else:
    print(f"\n  WARNING: slope still low ({new_slope:.3f}) — model discrimination may be the bottleneck")


# ─────────────────────────────────────────────
# 5. Patch the HTML
# ─────────────────────────────────────────────
print("\nStep 5: Patching HTML...")

# Update metrics in the TV block
tv["test_metrics"]["auc"] = round(new_auc, 10)
tv["test_metrics"]["brier"] = round(new_brier, 10)
tv["test_metrics"]["calibration_slope"] = round(new_slope, 10)
tv["trial_predictions"] = all_preds

# Store calibration method metadata
tv["calibration"] = {
    "method": "platt_scaling",
    "a": round(a, 8),
    "b": round(b, 8),
    "fitted_on": "train",
}

new_tv_str = json.dumps(tv, separators=(",", ":"))

# Replace exactly what we found (including the prefix with any whitespace)
full_old = tv_prefix + tv_json_str
full_new = tv_prefix.rstrip() + new_tv_str  # normalize whitespace
new_html = html.replace(full_old, full_new, 1)

if new_html == html:
    # Fallback: try without prefix normalization
    new_html = html.replace(full_old, tv_prefix + new_tv_str, 1)

if new_html == html:
    print("ERROR: HTML replacement failed!")
    print(f"  Looking for prefix: {repr(tv_prefix[:50])}")
    print(f"  Looking for TV start: {repr(tv_json_str[:80])}")
    # Write metrics to a separate file so we don't lose them
    results_path = PROJECT_ROOT / "recalibration_results.json"
    with results_path.open("w", encoding="utf-8") as f:
        json.dump({
            "platt_a": a, "platt_b": b,
            "old_metrics": {"auc": old_auc, "brier": old_brier, "slope_ols": old_slope},
            "new_metrics": {"auc": new_auc, "brier": new_brier, "slope_logistic": new_slope, "slope_ols": ols_slope_old_metric},
        }, f, indent=2)
    print(f"  Saved metrics to {results_path} for manual patching")
    sys.exit(1)

# ─────────────────────────────────────────────
# 6. Verify and save
# ─────────────────────────────────────────────
print("\nStep 6: Verifying...")
open_divs  = len(re.findall(r'<div[\s>]', new_html))
close_divs = len(re.findall(r'</div>', new_html))
print(f"  Div balance: {open_divs}/{close_divs} {'OK' if open_divs == close_divs else 'MISMATCH'}")

with HTML_PATH.open("w", encoding="utf-8") as f:
    f.write(new_html)
print(f"  Saved to {HTML_PATH}")

print(f"\n{'='*50}")
print(f"  RECALIBRATION COMPLETE")
print(f"  Method: Platt scaling (a={a:.4f}, b={b:.4f})")
print(f"  AUC:    {old_auc:.4f} -> {new_auc:.4f}")
print(f"  Brier:  {old_brier:.4f} -> {new_brier:.4f}")
print(f"  Slope:  {old_slope:.4f} -> {new_slope:.4f} (logistic)")
print(f"{'='*50}")

"""CardioOracle Backtest: Sliding-window out-of-time validation.

For each year Y from 2010 to 2022:
  1. Training set: all trials with start_year < Y
  2. Test set: all trials with start_year == Y
  3. Re-fit meta-regression + compute Bayesian borrowing + conditional power
  4. Evaluate predictions on test set

This gives a genuine temporal validation — no future leakage.

Output:
  - backtest_results.csv: per-trial predictions with actual outcomes
  - backtest_summary.json: per-year and overall metrics
"""

import json
import math
import csv
from pathlib import Path
from collections import Counter

DATA_PATH = Path(r'C:\Models\CardioOracle\data\training_data.json')
OUTPUT_DIR = Path(r'C:\Models\CardioOracle\backtest')


def load_data():
    with open(DATA_PATH) as f:
        data = json.load(f)
    trials = []
    for t in data['trials']:
        feat = t['features']
        year = feat.get('start_year', 0)
        if year < 1999:
            continue
        label = 1 if t['label'] == 'success' else 0
        trials.append({
            'nct_id': t['nct_id'],
            'title': t['title'],
            'label': label,
            'label_text': t['label'],
            'year': int(year),
            'drug_class': feat.get('drug_class', 'other'),
            'endpoint_type': feat.get('endpoint_type', 'other'),
            'enrollment': feat.get('enrollment', 0),
            'duration_months': feat.get('duration_months', 0),
            'placebo_controlled': feat.get('placebo_controlled', 0),
            'double_blind': feat.get('double_blind', 0),
            'is_industry': feat.get('is_industry', 0),
            'num_sites': feat.get('num_sites', 0),
            'multi_regional': feat.get('multi_regional', 0),
            'num_arms': feat.get('num_arms', 2),
            'has_dsmb': feat.get('has_dsmb', 0),
            'historical_class_rate': feat.get('historical_class_rate', 0.5),
            'comparator_type': feat.get('comparator_type', 'placebo'),
        })
    return trials


# ═══════════════════════════════════════
# COMPONENT 1: Bayesian Historical Borrowing
# ═══════════════════════════════════════

def similarity(target, reference):
    """5-dimensional similarity score between two trials."""
    s = 0
    # Drug class (0.30)
    if target['drug_class'] == reference['drug_class']:
        s += 0.30
    elif target['drug_class'] != 'other' and reference['drug_class'] != 'other':
        s += 0.15  # partial match for non-other classes

    # Endpoint type (0.25)
    hard = {'mace', 'cv_death', 'acm', 'hf_hosp', 'renal'}
    if target['endpoint_type'] == reference['endpoint_type']:
        s += 0.25
    elif target['endpoint_type'] in hard and reference['endpoint_type'] in hard:
        s += 0.10

    # Comparator (0.15)
    if target['placebo_controlled'] == reference['placebo_controlled']:
        s += 0.15

    # Era (0.15) — exponential decay with 10-year half-life
    year_diff = abs(target['year'] - reference['year'])
    s += 0.15 * math.exp(-year_diff * math.log(2) / 10)

    # Industry (0.15)
    if target['is_industry'] == reference['is_industry']:
        s += 0.15

    return s


def bayesian_borrowing(target, training):
    """Beta-binomial posterior using similarity-weighted historical outcomes."""
    sims = [(t, similarity(target, t)) for t in training]
    similar = [(t, s) for t, s in sims if s > 0.3]

    if len(similar) < 3:
        similar = [(t, s) for t, s in sims if s > 0.1][:20]

    if len(similar) < 3:
        return 0.5, 'LOW'

    # Beta(4.5, 5.5) prior — slightly skeptical
    alpha_post = 4.5 + sum(s * t['label'] for t, s in similar)
    beta_post = 5.5 + sum(s * (1 - t['label']) for t, s in similar)

    p = alpha_post / (alpha_post + beta_post)
    conf = 'HIGH' if len(similar) >= 10 else 'MODERATE' if len(similar) >= 5 else 'LOW'
    return p, conf


# ═══════════════════════════════════════
# COMPONENT 2: Conditional Power
# ═══════════════════════════════════════

EVENT_RATES = {'mace': 0.10, 'cv_death': 0.08, 'acm': 0.08, 'hf_hosp': 0.15,
               'renal': 0.12, 'surrogate': 0.70, 'other': 0.15}


def conditional_power(target, success_rate):
    """Estimate power to detect plausible effect size."""
    n = max(target['enrollment'], 100)
    n_per_arm = n // max(target['num_arms'], 2)
    ep = target['endpoint_type']

    if ep in ('mace', 'cv_death', 'acm', 'hf_hosp', 'renal'):
        # Time-to-event: Schoenfeld
        er = EVENT_RATES.get(ep, 0.10)
        events = n * er
        hr = math.exp(-0.05 - 0.25 * success_rate)
        if events < 10 or hr >= 1:
            return 0.5
        z = abs(math.log(hr)) * math.sqrt(events) / 2
        power = normal_cdf(z - 1.96) + normal_cdf(-z - 1.96)
    elif ep == 'surrogate':
        # Continuous: SMD
        smd = 0.1 + 0.4 * success_rate
        lam = smd * math.sqrt(n_per_arm / 2)
        power = normal_cdf(lam - 1.96) + normal_cdf(-lam - 1.96)
    else:
        # Binary
        p0 = 0.15
        p1 = p0 * (1 - 0.3 * success_rate)
        h = 2 * (math.asin(math.sqrt(p0)) - math.asin(math.sqrt(max(0.01, p1))))
        z = h * math.sqrt(n_per_arm)
        power = normal_cdf(abs(z) - 1.96) + normal_cdf(-abs(z) - 1.96)

    return max(0.05, min(0.99, power))


def normal_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ═══════════════════════════════════════
# COMPONENT 3: Meta-Regression (simplified L2 logistic)
# ═══════════════════════════════════════

def fit_logistic(training):
    """Fit L2-regularized logistic regression on training data.
    Uses iteratively reweighted least squares (IRLS).
    Returns coefficients vector.
    """
    # Feature extraction
    features = []
    labels = []
    for t in training:
        x = [
            math.log(max(t['enrollment'], 1)),
            t['duration_months'] / 12,  # normalize to years
            float(t['placebo_controlled']),
            float(t['double_blind']),
            float(t['is_industry']),
            math.log(max(t['num_sites'], 1)),
            float(t['multi_regional']),
            float(t['endpoint_type'] == 'mace'),
            float(t['endpoint_type'] == 'hf_hosp'),
            float(t['endpoint_type'] == 'surrogate'),
            float(t['endpoint_type'] == 'acm'),
            t['historical_class_rate'],
        ]
        features.append(x)
        labels.append(t['label'])

    n = len(features)
    p = len(features[0]) + 1  # +1 for intercept
    lam = 1.0  # L2 penalty

    # IRLS
    beta = [0.0] * p
    for iteration in range(25):
        # Compute predictions
        preds = []
        for i in range(n):
            z = beta[0] + sum(beta[j+1] * features[i][j] for j in range(p-1))
            z = max(-20, min(20, z))
            preds.append(1 / (1 + math.exp(-z)))

        # Weighted least squares update
        # X^T W X + lambda*I
        # X^T W z
        xtx = [[0.0]*p for _ in range(p)]
        xtz = [0.0] * p

        for i in range(n):
            w = preds[i] * (1 - preds[i]) + 1e-8
            r = labels[i] - preds[i]
            z_wls = sum(beta[j+1] * features[i][j] for j in range(p-1)) + beta[0] + r / w

            # X_i = [1, features...]
            xi = [1.0] + features[i]
            for j1 in range(p):
                xtz[j1] += w * xi[j1] * z_wls
                for j2 in range(p):
                    xtx[j1][j2] += w * xi[j1] * xi[j2]

        # Add L2 penalty (not on intercept)
        for j in range(1, p):
            xtx[j][j] += lam

        # Solve via Gaussian elimination
        new_beta = solve_linear(xtx, xtz)
        if new_beta is None:
            break

        # Check convergence
        diff = max(abs(new_beta[j] - beta[j]) for j in range(p))
        beta = new_beta
        if diff < 1e-6:
            break

    return beta, p


def solve_linear(A, b):
    """Solve Ax = b via Gaussian elimination with partial pivoting."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]

    for col in range(n):
        # Pivot
        max_row = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[max_row] = M[max_row], M[col]

        if abs(M[col][col]) < 1e-12:
            return None

        for row in range(col + 1, n):
            factor = M[row][col] / M[col][col]
            for j in range(col, n + 1):
                M[row][j] -= factor * M[col][j]

    # Back substitution
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]

    return x


def predict_logistic(trial, beta, p):
    """Predict P(success) using fitted logistic model."""
    x = [
        math.log(max(trial['enrollment'], 1)),
        trial['duration_months'] / 12,
        float(trial['placebo_controlled']),
        float(trial['double_blind']),
        float(trial['is_industry']),
        math.log(max(trial['num_sites'], 1)),
        float(trial['multi_regional']),
        float(trial['endpoint_type'] == 'mace'),
        float(trial['endpoint_type'] == 'hf_hosp'),
        float(trial['endpoint_type'] == 'surrogate'),
        float(trial['endpoint_type'] == 'acm'),
        trial['historical_class_rate'],
    ]
    z = beta[0] + sum(beta[j+1] * x[j] for j in range(len(x)))
    z = max(-20, min(20, z))
    return 1 / (1 + math.exp(-z))


# ═══════════════════════════════════════
# ENSEMBLE
# ═══════════════════════════════════════

def ensemble_predict(p_bayes, p_power, p_reg):
    """Weighted ensemble: 40% Bayesian + 35% Power + 25% Regression."""
    return 0.40 * p_bayes + 0.35 * p_power + 0.25 * p_reg


# ═══════════════════════════════════════
# METRICS
# ═══════════════════════════════════════

def compute_metrics(predictions):
    """Compute AUC, Brier, calibration slope."""
    if len(predictions) < 5:
        return {}

    y = [p['actual'] for p in predictions]
    prob = [p['predicted'] for p in predictions]
    n = len(y)

    # Brier score
    brier = sum((prob[i] - y[i])**2 for i in range(n)) / n

    # AUC (Mann-Whitney)
    pos = [(prob[i], y[i]) for i in range(n) if y[i] == 1]
    neg = [(prob[i], y[i]) for i in range(n) if y[i] == 0]
    if len(pos) == 0 or len(neg) == 0:
        auc = 0.5
    else:
        concordant = sum(1 for p in pos for nn in neg if p[0] > nn[0])
        tied = sum(0.5 for p in pos for nn in neg if p[0] == nn[0])
        auc = (concordant + tied) / (len(pos) * len(neg))

    mean_y = sum(y) / n

    # Calibration slope (logistic regression of y on logit(p) — NOT OLS on binary)
    logits = []
    for p in prob:
        p_clamp = max(0.001, min(0.999, p))
        logits.append(math.log(p_clamp / (1 - p_clamp)))

    # Newton-Raphson for logistic calibration: y ~ Bernoulli(expit(a*logit(p) + b))
    a, b = 1.0, 0.0
    for _ in range(50):
        eta = [a * logits[i] + b for i in range(n)]
        mu = [1 / (1 + math.exp(-max(-20, min(20, e)))) for e in eta]
        w = [mu[i] * (1 - mu[i]) + 1e-12 for i in range(n)]
        g_a = sum((y[i] - mu[i]) * logits[i] for i in range(n))
        g_b = sum(y[i] - mu[i] for i in range(n))
        H_aa = -sum(w[i] * logits[i]**2 for i in range(n))
        H_ab = -sum(w[i] * logits[i] for i in range(n))
        H_bb = -sum(w[i] for i in range(n))
        det = H_aa * H_bb - H_ab**2
        if abs(det) < 1e-15:
            break
        da = -(H_bb * g_a - H_ab * g_b) / det
        db = -(H_aa * g_b - H_ab * g_a) / det
        a += da
        b += db
        if abs(da) < 1e-8 and abs(db) < 1e-8:
            break
    cal_slope = a

    # Accuracy at 0.5 threshold
    correct = sum(1 for i in range(n) if (prob[i] >= 0.5) == (y[i] == 1))
    accuracy = correct / n

    return {
        'n': n,
        'auc': round(auc, 3),
        'brier': round(brier, 3),
        'cal_slope': round(cal_slope, 3),
        'accuracy': round(accuracy, 3),
        'base_rate': round(mean_y, 3),
    }


# ═══════════════════════════════════════
# MAIN
# ═══════════════════════════════════════

def main():
    print("CardioOracle Backtest")
    print("=" * 40)

    trials = load_data()
    print(f"  Loaded {len(trials)} trials ({min(t['year'] for t in trials)}-{max(t['year'] for t in trials)})")

    all_predictions = []
    year_metrics = {}

    for test_year in range(2010, 2023):
        train = [t for t in trials if t['year'] < test_year]
        test = [t for t in trials if t['year'] == test_year]

        if len(test) < 3 or len(train) < 50:
            continue

        # Fit meta-regression on training data
        beta, p = fit_logistic(train)

        # Historical success rate per drug class (from training only)
        class_rates = {}
        for dc in set(t['drug_class'] for t in train):
            subset = [t for t in train if t['drug_class'] == dc]
            class_rates[dc] = sum(t['label'] for t in subset) / len(subset)

        # Predict each test trial
        year_preds = []
        for target in test:
            # Fix P0-2: overwrite historical_class_rate with train-only value to prevent leakage
            target_rate = class_rates.get(target['drug_class'], 0.5)
            target['historical_class_rate'] = target_rate

            p_bayes, conf = bayesian_borrowing(target, train)
            p_power = conditional_power(target, target_rate)
            p_reg = predict_logistic(target, beta, p)
            p_ensemble = ensemble_predict(p_bayes, p_power, p_reg)

            pred = {
                'nct_id': target['nct_id'],
                'year': test_year,
                'actual': target['label'],
                'predicted': round(p_ensemble, 3),
                'p_bayes': round(p_bayes, 3),
                'p_power': round(p_power, 3),
                'p_reg': round(p_reg, 3),
                'drug_class': target['drug_class'],
                'endpoint_type': target['endpoint_type'],
                'n_train': len(train),
            }
            year_preds.append(pred)
            all_predictions.append(pred)

        metrics = compute_metrics(year_preds)
        year_metrics[test_year] = metrics
        print(f"  {test_year}: n_test={len(test):>3}, n_train={len(train):>3}, AUC={metrics.get('auc','?'):>5}, Brier={metrics.get('brier','?'):>5}")

    # Overall metrics
    overall = compute_metrics(all_predictions)

    # P1-6: Per-component metrics
    bayes_m = compute_metrics([{'actual': p['actual'], 'predicted': p['p_bayes']} for p in all_predictions])
    power_m = compute_metrics([{'actual': p['actual'], 'predicted': p['p_power']} for p in all_predictions])
    reg_m = compute_metrics([{'actual': p['actual'], 'predicted': p['p_reg']} for p in all_predictions])

    print(f"\n{'='*50}")
    print("OVERALL BACKTEST RESULTS")
    print(f"{'='*50}")
    if overall:
        print(f"  Total predictions: {overall.get('n', 0)}")
        print(f"  AUC: {overall.get('auc', '?')}")
        print(f"  Brier Score: {overall.get('brier', '?')}")
        print(f"  Calibration Slope: {overall.get('cal_slope', '?')}")
        print(f"  Accuracy: {overall.get('accuracy', '?')}")
        print(f"  Base rate: {overall.get('base_rate', '?')}")
    else:
        print("  Insufficient predictions for overall metrics")

    print(f"\n  Per-component AUC: Bayesian={bayes_m.get('auc','?')}, Power={power_m.get('auc','?')}, Regression={reg_m.get('auc','?')}")

    # Export
    fields = list(all_predictions[0].keys())
    with open(OUTPUT_DIR / 'backtest_results.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_predictions)

    summary = {
        'overall': overall,
        'per_year': year_metrics,
        'n_total': len(all_predictions),
        'years_tested': list(year_metrics.keys()),
    }
    with open(OUTPUT_DIR / 'backtest_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Saved to {OUTPUT_DIR}/")


if __name__ == '__main__':
    main()

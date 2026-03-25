"""
CardioOracle — Publication-Quality Figure Generator
====================================================
Generates 4 figures for the manuscript:
  1. ROC Curve (test set, n=133)
  2. Calibration Plot (quintile, with reference line)
  3. Feature Importance (top 10 logistic regression coefficients)
  4. Prediction Distribution (histogram by actual outcome, test set)

Uses recalibrated predictions from the HTML file (Platt scaling applied).
Outputs 300 dpi PNG + PDF to C:\Models\CardioOracle\figures\
"""

import json
import sys
import io
import os
import re
import math
import numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch

# ── Configuration ──────────────────────────────────────────────────
OUT_DIR = r"C:\Models\CardioOracle\figures"
HTML_PATH = r"C:\Models\CardioOracle\CardioOracle.html"
JSON_PATH = r"C:\Models\CardioOracle\data\model_coefficients.json"
DPI = 300

# ── Publication style ──────────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 11,
    'axes.labelsize': 13,
    'axes.titlesize': 14,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.dpi': DPI,
    'savefig.dpi': DPI,
    'savefig.bbox': 'tight',
    'axes.linewidth': 1.0,
    'xtick.major.width': 0.8,
    'ytick.major.width': 0.8,
    'axes.spines.top': False,
    'axes.spines.right': False,
})

# Colour palette (colourblind-safe)
COL_PRIMARY   = '#2166AC'   # Blue
COL_SECONDARY = '#B2182B'   # Red
COL_ACCENT    = '#4DAF4A'   # Green
COL_GREY      = '#969696'
COL_LIGHT     = '#D1E5F0'
COL_SUCCESS   = '#2166AC'   # Blue for success
COL_FAILURE   = '#B2182B'   # Red for failure

# ── 1. Load data ──────────────────────────────────────────────────
print("Loading data from HTML file...")
with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

# Extract cardiorenal model's temporal_validation trial_predictions
cr_start = html.find('cardiorenal')
cad_start = html.find('"cad"', cr_start + 100)

section = html[cr_start:cad_start]

# Extract test_metrics
tm_match = re.search(r'"test_metrics"\s*:\s*\{([^}]+)\}', section)
test_metrics_str = '{' + tm_match.group(1) + '}'
test_metrics = json.loads(test_metrics_str)
print(f"  Test metrics: AUC={test_metrics['auc']:.4f}, "
      f"Brier={test_metrics['brier']:.4f}, "
      f"Cal. slope={test_metrics['calibration_slope']:.4f}")

# Extract insample_metrics
im_match = re.search(r'"insample_metrics"\s*:\s*\{([^}]+)\}', section)
insample_metrics_str = '{' + im_match.group(1) + '}'
insample_metrics = json.loads(insample_metrics_str)
print(f"  In-sample metrics: AUC={insample_metrics['auc']:.4f}, "
      f"Brier={insample_metrics['brier']:.4f}")

# Extract trial_predictions array
tp_start = section.find('"trial_predictions"')
arr_start = section.find('[', tp_start)
depth = 0
for i in range(arr_start, len(section)):
    if section[i] == '[':
        depth += 1
    elif section[i] == ']':
        depth -= 1
    if depth == 0:
        break
arr_end = i + 1
predictions = json.loads(section[arr_start:arr_end])

test_preds  = [p for p in predictions if p['split'] == 'test']
train_preds = [p for p in predictions if p['split'] == 'train']
print(f"  {len(train_preds)} train, {len(test_preds)} test predictions")

# Load coefficients from JSON
with open(JSON_PATH, 'r', encoding='utf-8') as f:
    coef_data = json.load(f)
coefficients = coef_data['model']['coefficients']
print(f"  {len(coefficients)} coefficients loaded")

# ── Helper: compute ROC ──────────────────────────────────────────
def compute_roc(y_true, y_prob):
    """Compute ROC curve and AUC using the trapezoidal rule."""
    paired = sorted(zip(y_prob, y_true), key=lambda x: -x[0])
    n_pos = sum(y_true)
    n_neg = len(y_true) - n_pos

    tpr_list = [0.0]
    fpr_list = [0.0]
    tp = 0
    fp = 0

    for prob, label in paired:
        if label == 1:
            tp += 1
        else:
            fp += 1
        tpr_list.append(tp / n_pos if n_pos > 0 else 0)
        fpr_list.append(fp / n_neg if n_neg > 0 else 0)

    # AUC via trapezoidal rule
    auc = 0.0
    for i in range(1, len(fpr_list)):
        auc += (fpr_list[i] - fpr_list[i-1]) * (tpr_list[i] + tpr_list[i-1]) / 2.0

    return np.array(fpr_list), np.array(tpr_list), auc


# ══════════════════════════════════════════════════════════════════
# FIGURE 1: ROC Curve
# ══════════════════════════════════════════════════════════════════
print("\nGenerating Figure 1: ROC Curve...")

y_true_test = [p['y_true'] for p in test_preds]
y_prob_test = [p['y_prob'] for p in test_preds]

fpr, tpr, auc_val = compute_roc(y_true_test, y_prob_test)

fig1, ax1 = plt.subplots(figsize=(5.5, 5.5))

# Diagonal reference
ax1.plot([0, 1], [0, 1], linestyle='--', color=COL_GREY, linewidth=1.0,
         label='Random classifier', zorder=1)

# ROC curve
ax1.plot(fpr, tpr, color=COL_PRIMARY, linewidth=2.2, zorder=2,
         label=f'CardioOracle (AUC = {auc_val:.3f})')

# Fill under curve
ax1.fill_between(fpr, tpr, alpha=0.12, color=COL_PRIMARY, zorder=1)

# Youden's J point (optimal threshold)
j_scores = tpr - fpr
best_idx = np.argmax(j_scores)
ax1.scatter(fpr[best_idx], tpr[best_idx], color=COL_SECONDARY, s=80,
            zorder=3, edgecolors='white', linewidths=1.5,
            label=f"Youden's J = {j_scores[best_idx]:.2f}")

ax1.set_xlabel('False Positive Rate (1 - Specificity)')
ax1.set_ylabel('True Positive Rate (Sensitivity)')
ax1.set_title('A. Receiver Operating Characteristic Curve', fontweight='bold',
              loc='left')
ax1.legend(loc='lower right', frameon=True, framealpha=0.9, edgecolor='#cccccc')
ax1.set_xlim(-0.02, 1.02)
ax1.set_ylim(-0.02, 1.02)
ax1.set_aspect('equal')

# Add n annotation
ax1.text(0.98, 0.02, f'Temporal test set (n = {len(test_preds)})',
         transform=ax1.transAxes, ha='right', va='bottom',
         fontsize=9, color=COL_GREY)

fig1.savefig(os.path.join(OUT_DIR, 'fig1_roc_curve.png'), dpi=DPI)
fig1.savefig(os.path.join(OUT_DIR, 'fig1_roc_curve.pdf'))
plt.close(fig1)
print(f"  Saved. AUC = {auc_val:.4f}")


# ══════════════════════════════════════════════════════════════════
# FIGURE 2: Calibration Plot
# ══════════════════════════════════════════════════════════════════
print("\nGenerating Figure 2: Calibration Plot...")

# Quintile calibration
n_bins = 5
sorted_test = sorted(test_preds, key=lambda p: p['y_prob'])
bin_size = len(sorted_test) // n_bins

predicted_means = []
observed_means  = []
bin_counts      = []
bin_ses         = []

for i in range(n_bins):
    start = i * bin_size
    end = start + bin_size if i < n_bins - 1 else len(sorted_test)
    bin_data = sorted_test[start:end]

    pred_mean = np.mean([p['y_prob'] for p in bin_data])
    obs_mean  = np.mean([p['y_true'] for p in bin_data])
    n_bin     = len(bin_data)

    # SE of observed proportion (binomial)
    se = np.sqrt(obs_mean * (1 - obs_mean) / n_bin) if n_bin > 0 else 0

    predicted_means.append(pred_mean)
    observed_means.append(obs_mean)
    bin_counts.append(n_bin)
    bin_ses.append(se)

predicted_means = np.array(predicted_means)
observed_means  = np.array(observed_means)
bin_ses         = np.array(bin_ses)

fig2, ax2 = plt.subplots(figsize=(5.5, 5.5))

# 45-degree reference (perfect calibration)
ax2.plot([0, 1], [0, 1], linestyle='--', color=COL_GREY, linewidth=1.0,
         label='Perfect calibration', zorder=1)

# Quintile points with error bars
ax2.errorbar(predicted_means, observed_means, yerr=1.96 * bin_ses,
             fmt='o', color=COL_PRIMARY, markersize=10, capsize=5,
             capthick=1.5, linewidth=1.5, elinewidth=1.5,
             markeredgecolor='white', markeredgewidth=1.5,
             label='Quintile groups', zorder=3)

# Connect points with line
ax2.plot(predicted_means, observed_means, color=COL_PRIMARY, linewidth=1.2,
         alpha=0.5, zorder=2)

# Add bin count annotations
for j in range(n_bins):
    ax2.annotate(f'n={bin_counts[j]}',
                 xy=(predicted_means[j], observed_means[j]),
                 xytext=(8, -12), textcoords='offset points',
                 fontsize=8, color=COL_GREY)

# Calibration slope annotation
cal_slope = test_metrics['calibration_slope']
ax2.text(0.05, 0.92,
         f'Calibration slope = {cal_slope:.3f}\n'
         f'Brier score = {test_metrics["brier"]:.3f}',
         transform=ax2.transAxes, fontsize=10,
         verticalalignment='top',
         bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                   edgecolor='#cccccc', alpha=0.9))

ax2.set_xlabel('Mean predicted probability')
ax2.set_ylabel('Observed proportion of successes')
ax2.set_title('B. Calibration Plot (Quintiles)', fontweight='bold', loc='left')
ax2.legend(loc='lower right', frameon=True, framealpha=0.9, edgecolor='#cccccc')
ax2.set_xlim(-0.02, 1.02)
ax2.set_ylim(-0.02, 1.02)
ax2.set_aspect('equal')

# n annotation
ax2.text(0.98, 0.02, f'Temporal test set (n = {len(test_preds)})',
         transform=ax2.transAxes, ha='right', va='bottom',
         fontsize=9, color=COL_GREY)

fig2.savefig(os.path.join(OUT_DIR, 'fig2_calibration.png'), dpi=DPI)
fig2.savefig(os.path.join(OUT_DIR, 'fig2_calibration.pdf'))
plt.close(fig2)
print(f"  Saved. Calibration slope = {cal_slope:.4f}")


# ══════════════════════════════════════════════════════════════════
# FIGURE 3: Feature Importance (Logistic Regression Coefficients)
# ══════════════════════════════════════════════════════════════════
print("\nGenerating Figure 3: Feature Importance...")

# Exclude intercept, sort by absolute magnitude
features = {k: v for k, v in coefficients.items() if k != 'intercept'}
sorted_feats = sorted(features.items(), key=lambda x: abs(x[1]), reverse=True)

# Top 10
top10 = sorted_feats[:10]

# Readable labels
label_map = {
    'is_industry':           'Industry sponsored',
    'ep_acm':                'All-cause mortality EP',
    'ep_surrogate':          'Surrogate endpoint',
    'has_dsmb':              'DSMB present',
    'ep_hf_hosp':            'HF hospitalisation EP',
    'ep_mace':               'MACE endpoint',
    'placebo_controlled':    'Placebo-controlled',
    'double_blind':          'Double-blind',
    'ep_cv_death':           'CV death endpoint',
    'multi_regional':        'Multi-regional',
    'log_enrollment':        'Log enrollment',
    'duration_months':       'Duration (months)',
    'era_2010_2017':         'Era 2010-2017',
    'era_2018plus':          'Era 2018+',
    'log_num_sites':         'Log number of sites',
    'num_arms':              'Number of arms',
    'ep_renal':              'Renal endpoint',
    'historical_class_rate': 'Historical class rate',
}

names  = [label_map.get(k, k) for k, v in top10]
values = [v for k, v in top10]
colors = [COL_SUCCESS if v > 0 else COL_FAILURE for v in values]

fig3, ax3 = plt.subplots(figsize=(7, 5))

y_pos = np.arange(len(names))
bars = ax3.barh(y_pos, values, color=colors, height=0.65, edgecolor='white',
                linewidth=0.5, zorder=2)

# Value labels
for bar_item, val in zip(bars, values):
    # Place label outside the bar end
    if val >= 0:
        x_pos = val + 0.03
        ha = 'left'
    else:
        x_pos = val - 0.03
        ha = 'right'
    ax3.text(x_pos, bar_item.get_y() + bar_item.get_height() / 2,
             f'{val:+.3f}', va='center', ha=ha, fontsize=9, fontweight='bold')

# Ensure x-axis has room for labels
x_min = min(values) - 0.25
x_max = max(values) + 0.25
ax3.set_xlim(x_min, x_max)

ax3.set_yticks(y_pos)
ax3.set_yticklabels(names)
ax3.invert_yaxis()
ax3.set_xlabel('Logistic regression coefficient')
ax3.set_title('C. Feature Importance (Top 10 by |coefficient|)',
              fontweight='bold', loc='left')

# Zero line
ax3.axvline(x=0, color='black', linewidth=0.8, zorder=1)

# Light grid
ax3.xaxis.grid(True, alpha=0.3, linestyle='-', zorder=0)

# Legend for direction
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=COL_SUCCESS, label='Increases P(success)'),
                   Patch(facecolor=COL_FAILURE, label='Decreases P(success)')]
ax3.legend(handles=legend_elements, loc='lower right', frameon=True,
           framealpha=0.9, edgecolor='#cccccc')

# Annotation
ax3.text(0.98, 0.02,
         f'Logistic regression on {insample_metrics["n"]} trials',
         transform=ax3.transAxes, ha='right', va='bottom',
         fontsize=9, color=COL_GREY)

fig3.tight_layout()
fig3.savefig(os.path.join(OUT_DIR, 'fig3_feature_importance.png'), dpi=DPI)
fig3.savefig(os.path.join(OUT_DIR, 'fig3_feature_importance.pdf'))
plt.close(fig3)
print(f"  Saved. Top feature: {top10[0][0]} ({top10[0][1]:+.3f})")


# ══════════════════════════════════════════════════════════════════
# FIGURE 4: Prediction Distribution (Histogram by outcome)
# ══════════════════════════════════════════════════════════════════
print("\nGenerating Figure 4: Prediction Distribution...")

probs_success = [p['y_prob'] for p in test_preds if p['y_true'] == 1]
probs_failure = [p['y_prob'] for p in test_preds if p['y_true'] == 0]

fig4, ax4 = plt.subplots(figsize=(7, 4.5))

bins = np.linspace(0, 1, 21)  # 20 bins

ax4.hist(probs_success, bins=bins, alpha=0.7, color=COL_SUCCESS,
         edgecolor='white', linewidth=0.5, label=f'Actual success (n={len(probs_success)})',
         zorder=2)
ax4.hist(probs_failure, bins=bins, alpha=0.7, color=COL_FAILURE,
         edgecolor='white', linewidth=0.5, label=f'Actual failure (n={len(probs_failure)})',
         zorder=2)

# Threshold line at 0.5
ax4.axvline(x=0.5, color='black', linestyle='--', linewidth=1.0, alpha=0.6, zorder=3)
ax4.text(0.51, ax4.get_ylim()[1] * 0.9 if ax4.get_ylim()[1] > 0 else 10,
         'Decision\nthreshold',
         fontsize=8, color='black', alpha=0.7, va='top')

# Tier boundaries
for thresh, label in [(0.3, 'Low'), (0.6, 'Moderate')]:
    ax4.axvline(x=thresh, color=COL_GREY, linestyle=':', linewidth=0.8,
                alpha=0.5, zorder=1)

ax4.set_xlabel('Predicted probability of trial success')
ax4.set_ylabel('Number of trials')
ax4.set_title('D. Distribution of Predicted Probabilities (Test Set)',
              fontweight='bold', loc='left')
ax4.legend(loc='upper left', frameon=True, framealpha=0.9, edgecolor='#cccccc')

# Add tier labels at top
ax4.text(0.15, 1.02, 'Low', transform=ax4.get_xaxis_transform(),
         ha='center', fontsize=8, color=COL_GREY, style='italic')
ax4.text(0.45, 1.02, 'Moderate', transform=ax4.get_xaxis_transform(),
         ha='center', fontsize=8, color=COL_GREY, style='italic')
ax4.text(0.80, 1.02, 'High', transform=ax4.get_xaxis_transform(),
         ha='center', fontsize=8, color=COL_GREY, style='italic')

# Summary statistics
median_s = np.median(probs_success)
median_f = np.median(probs_failure)
ax4.text(0.98, 0.95,
         f'Median P (success trials): {median_s:.3f}\n'
         f'Median P (failure trials): {median_f:.3f}',
         transform=ax4.transAxes, ha='right', va='top', fontsize=9,
         bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                   edgecolor='#cccccc', alpha=0.9))

# n annotation
ax4.text(0.98, 0.02, f'Temporal test set (n = {len(test_preds)})',
         transform=ax4.transAxes, ha='right', va='bottom',
         fontsize=9, color=COL_GREY)

fig4.tight_layout()
fig4.savefig(os.path.join(OUT_DIR, 'fig4_prediction_distribution.png'), dpi=DPI)
fig4.savefig(os.path.join(OUT_DIR, 'fig4_prediction_distribution.pdf'))
plt.close(fig4)
print(f"  Saved. Median P: success={median_s:.3f}, failure={median_f:.3f}")


# ══════════════════════════════════════════════════════════════════
# COMPOSITE FIGURE (all 4 panels)
# ══════════════════════════════════════════════════════════════════
print("\nGenerating composite figure (all 4 panels)...")

fig, axes = plt.subplots(2, 2, figsize=(12, 11))

# Panel A: ROC
ax = axes[0, 0]
ax.plot([0, 1], [0, 1], linestyle='--', color=COL_GREY, linewidth=1.0, zorder=1)
ax.plot(fpr, tpr, color=COL_PRIMARY, linewidth=2.0, zorder=2,
        label=f'AUC = {auc_val:.3f}')
ax.fill_between(fpr, tpr, alpha=0.10, color=COL_PRIMARY, zorder=1)
ax.scatter(fpr[best_idx], tpr[best_idx], color=COL_SECONDARY, s=60,
           zorder=3, edgecolors='white', linewidths=1.2)
ax.set_xlabel('False Positive Rate')
ax.set_ylabel('True Positive Rate')
ax.set_title('A. ROC Curve', fontweight='bold', loc='left')
ax.legend(loc='lower right', frameon=True, framealpha=0.9, edgecolor='#cccccc')
ax.set_xlim(-0.02, 1.02)
ax.set_ylim(-0.02, 1.02)
ax.set_aspect('equal')

# Panel B: Calibration
ax = axes[0, 1]
ax.plot([0, 1], [0, 1], linestyle='--', color=COL_GREY, linewidth=1.0, zorder=1)
ax.errorbar(predicted_means, observed_means, yerr=1.96 * bin_ses,
            fmt='o', color=COL_PRIMARY, markersize=9, capsize=4,
            capthick=1.2, linewidth=1.2, elinewidth=1.2,
            markeredgecolor='white', markeredgewidth=1.2, zorder=3)
ax.plot(predicted_means, observed_means, color=COL_PRIMARY, linewidth=1.0,
        alpha=0.5, zorder=2)
ax.text(0.05, 0.92,
        f'Slope = {cal_slope:.3f}\nBrier = {test_metrics["brier"]:.3f}',
        transform=ax.transAxes, fontsize=9, va='top',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                  edgecolor='#cccccc', alpha=0.9))
ax.set_xlabel('Mean predicted probability')
ax.set_ylabel('Observed proportion')
ax.set_title('B. Calibration Plot', fontweight='bold', loc='left')
ax.set_xlim(-0.02, 1.02)
ax.set_ylim(-0.02, 1.02)
ax.set_aspect('equal')

# Panel C: Feature Importance
ax = axes[1, 0]
bars = ax.barh(y_pos, values, color=colors, height=0.65, edgecolor='white',
               linewidth=0.5, zorder=2)
for bar_item, val in zip(bars, values):
    x_pos = val + 0.02 if val >= 0 else val - 0.02
    ha = 'left' if val >= 0 else 'right'
    ax.text(x_pos, bar_item.get_y() + bar_item.get_height() / 2,
            f'{val:+.2f}', va='center', ha=ha, fontsize=8, fontweight='bold')
ax.set_yticks(y_pos)
ax.set_yticklabels(names, fontsize=9)
ax.invert_yaxis()
ax.set_xlabel('Coefficient')
ax.set_title('C. Feature Importance', fontweight='bold', loc='left')
ax.axvline(x=0, color='black', linewidth=0.8, zorder=1)
ax.xaxis.grid(True, alpha=0.3, linestyle='-', zorder=0)

# Panel D: Prediction Distribution
ax = axes[1, 1]
ax.hist(probs_success, bins=bins, alpha=0.7, color=COL_SUCCESS,
        edgecolor='white', linewidth=0.5,
        label=f'Success (n={len(probs_success)})', zorder=2)
ax.hist(probs_failure, bins=bins, alpha=0.7, color=COL_FAILURE,
        edgecolor='white', linewidth=0.5,
        label=f'Failure (n={len(probs_failure)})', zorder=2)
ax.axvline(x=0.5, color='black', linestyle='--', linewidth=0.8, alpha=0.6, zorder=3)
for thresh in [0.3, 0.6]:
    ax.axvline(x=thresh, color=COL_GREY, linestyle=':', linewidth=0.7,
               alpha=0.4, zorder=1)
ax.set_xlabel('Predicted probability')
ax.set_ylabel('Count')
ax.set_title('D. Prediction Distribution', fontweight='bold', loc='left')
ax.legend(loc='upper left', frameon=True, framealpha=0.9, edgecolor='#cccccc',
          fontsize=9)

fig.suptitle('CardioOracle: Temporal Validation (n = 133 trials, 2020+)',
             fontsize=14, fontweight='bold', y=0.98)
fig.tight_layout(rect=[0, 0, 1, 0.96])

fig.savefig(os.path.join(OUT_DIR, 'fig_composite_all.png'), dpi=DPI)
fig.savefig(os.path.join(OUT_DIR, 'fig_composite_all.pdf'))
plt.close(fig)

# ── Cleanup temp file ─────────────────────────────────────────────
temp_path = r"C:\Models\CardioOracle\data\_temp_html_predictions.json"
if os.path.exists(temp_path):
    os.remove(temp_path)

# ── Summary ───────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("DONE - All figures generated")
print("=" * 60)
print(f"Output directory: {OUT_DIR}")
for fname in sorted(os.listdir(OUT_DIR)):
    fpath = os.path.join(OUT_DIR, fname)
    size_kb = os.path.getsize(fpath) / 1024
    print(f"  {fname:40s} {size_kb:7.1f} KB")
print(f"\nKey metrics (recalibrated, Platt scaling):")
print(f"  AUC:               {auc_val:.4f}")
print(f"  Brier score:       {test_metrics['brier']:.4f}")
print(f"  Calibration slope: {cal_slope:.4f}")
print(f"  Youden's J:        {j_scores[best_idx]:.4f}")
print(f"  Test n:            {len(test_preds)} (success={len(probs_success)}, failure={len(probs_failure)})")

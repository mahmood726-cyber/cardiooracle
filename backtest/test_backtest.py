"""Unit tests for CardioOracle backtest functions."""
import sys, math, pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from backtest import (similarity, bayesian_borrowing, conditional_power,
                       fit_logistic, predict_logistic, ensemble_predict,
                       compute_metrics, solve_linear, normal_cdf, load_data)


class TestSimilarity:
    def test_identical_trials_max_score(self):
        t = {'drug_class': 'sglt2i', 'endpoint_type': 'hf_hosp', 'placebo_controlled': 1,
             'year': 2020, 'is_industry': 1}
        assert similarity(t, t) > 0.9

    def test_different_trials_low_score(self):
        t1 = {'drug_class': 'sglt2i', 'endpoint_type': 'hf_hosp', 'placebo_controlled': 1,
              'year': 2020, 'is_industry': 1}
        t2 = {'drug_class': 'other', 'endpoint_type': 'surrogate', 'placebo_controlled': 0,
              'year': 2005, 'is_industry': 0}
        assert similarity(t1, t2) < 0.3

    def test_score_range(self):
        t1 = {'drug_class': 'glp1ra', 'endpoint_type': 'mace', 'placebo_controlled': 1,
              'year': 2018, 'is_industry': 1}
        t2 = {'drug_class': 'glp1ra', 'endpoint_type': 'cv_death', 'placebo_controlled': 1,
              'year': 2020, 'is_industry': 0}
        s = similarity(t1, t2)
        assert 0 <= s <= 1


class TestBayesianBorrowing:
    def test_all_successes_high_p(self):
        train = [{'label': 1, 'drug_class': 'sglt2i', 'endpoint_type': 'hf_hosp',
                  'placebo_controlled': 1, 'year': 2020, 'is_industry': 1} for _ in range(20)]
        target = train[0].copy()
        p, conf = bayesian_borrowing(target, train)
        assert p > 0.7

    def test_all_failures_low_p(self):
        train = [{'label': 0, 'drug_class': 'other', 'endpoint_type': 'other',
                  'placebo_controlled': 0, 'year': 2015, 'is_industry': 0} for _ in range(20)]
        target = train[0].copy()
        p, conf = bayesian_borrowing(target, train)
        assert p < 0.4

    def test_few_similar_low_confidence(self):
        train = [{'label': 1, 'drug_class': 'other', 'endpoint_type': 'other',
                  'placebo_controlled': 0, 'year': 2000, 'is_industry': 0} for _ in range(3)]
        target = {'drug_class': 'pcsk9i', 'endpoint_type': 'mace', 'placebo_controlled': 1,
                  'year': 2023, 'is_industry': 1}
        _, conf = bayesian_borrowing(target, train)
        assert conf in ('LOW', 'MODERATE')


class TestConditionalPower:
    def test_large_trial_high_power(self):
        t = {'enrollment': 10000, 'num_arms': 2, 'endpoint_type': 'mace'}
        p = conditional_power(t, success_rate=0.7)
        assert p > 0.5

    def test_tiny_trial_low_power(self):
        t = {'enrollment': 50, 'num_arms': 2, 'endpoint_type': 'mace'}
        p = conditional_power(t, success_rate=0.3)
        assert p < 0.5

    def test_surrogate_endpoint(self):
        t = {'enrollment': 500, 'num_arms': 2, 'endpoint_type': 'surrogate'}
        p = conditional_power(t, success_rate=0.6)
        assert 0.05 <= p <= 0.99


class TestLogistic:
    def test_fit_and_predict_consistent(self):
        train = [{'enrollment': 1000, 'duration_months': 36, 'placebo_controlled': 1,
                  'double_blind': 1, 'is_industry': 1, 'num_sites': 100, 'multi_regional': 1,
                  'endpoint_type': 'mace', 'historical_class_rate': 0.7, 'label': 1}
                 for _ in range(30)]
        train += [{'enrollment': 200, 'duration_months': 12, 'placebo_controlled': 0,
                   'double_blind': 0, 'is_industry': 0, 'num_sites': 5, 'multi_regional': 0,
                   'endpoint_type': 'other', 'historical_class_rate': 0.3, 'label': 0}
                  for _ in range(20)]
        beta, p = fit_logistic(train)
        assert len(beta) == p
        # Predict should give high prob for success-like trial
        pred = predict_logistic(train[0], beta, p)
        assert 0.5 < pred < 1.0


class TestEnsemble:
    def test_weights_sum_correctly(self):
        p = ensemble_predict(0.8, 0.6, 0.4)
        expected = 0.40 * 0.8 + 0.35 * 0.6 + 0.25 * 0.4
        assert abs(p - expected) < 1e-10

    def test_range(self):
        assert 0 <= ensemble_predict(0.0, 0.0, 0.0) <= 1
        assert 0 <= ensemble_predict(1.0, 1.0, 1.0) <= 1


class TestMetrics:
    def test_perfect_predictions(self):
        preds = [{'actual': 1, 'predicted': 0.99} for _ in range(10)]
        preds += [{'actual': 0, 'predicted': 0.01} for _ in range(10)]
        m = compute_metrics(preds)
        assert m['auc'] > 0.95
        assert m['brier'] < 0.05
        assert m['accuracy'] > 0.95

    def test_random_predictions(self):
        import random
        random.seed(42)
        preds = [{'actual': random.choice([0, 1]), 'predicted': random.random()} for _ in range(100)]
        m = compute_metrics(preds)
        assert 0.3 < m['auc'] < 0.7  # Near chance

    def test_too_few_returns_empty(self):
        preds = [{'actual': 1, 'predicted': 0.9} for _ in range(3)]
        assert compute_metrics(preds) == {}


class TestSolveLinear:
    def test_identity_system(self):
        A = [[1, 0], [0, 1]]
        b = [3, 5]
        x = solve_linear(A, b)
        assert abs(x[0] - 3) < 1e-10
        assert abs(x[1] - 5) < 1e-10

    def test_2x2_system(self):
        A = [[2, 1], [1, 3]]
        b = [5, 10]
        x = solve_linear(A, b)
        assert abs(2*x[0] + x[1] - 5) < 1e-10
        assert abs(x[0] + 3*x[1] - 10) < 1e-10


class TestNormalCDF:
    def test_symmetry(self):
        assert abs(normal_cdf(0) - 0.5) < 1e-10

    def test_known_values(self):
        assert abs(normal_cdf(1.96) - 0.975) < 0.001
        assert abs(normal_cdf(-1.96) - 0.025) < 0.001


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

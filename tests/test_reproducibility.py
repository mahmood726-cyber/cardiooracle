"""
test_reproducibility.py — guards against the "fresh-clone broken" failure mode.

Each assertion here protects a specific reproducibility contract that has
broken in the past or could break silently:
  - curate/ must import as a package (regression guard for missing __init__.py)
  - .env.example must exist and document AACT_USER and AACT_PASSWORD
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_curate_is_importable_as_package():
    from curate.shared import get_aact_connection, classify_drug, classify_endpoint
    from curate.extract_aact import extract_trials
    from curate.label_outcomes import label_trial
    from curate.fit_model import fit_logistic_model

    assert callable(get_aact_connection)
    assert callable(classify_drug)
    assert callable(classify_endpoint)
    assert callable(extract_trials)
    assert callable(label_trial)
    assert callable(fit_logistic_model)


def test_env_example_documents_aact_credentials():
    env_example = REPO_ROOT / ".env.example"
    assert env_example.exists(), ".env.example must exist for fresh-clone reproducibility"
    body = env_example.read_text(encoding="utf-8")
    assert "AACT_USER" in body
    assert "AACT_PASSWORD" in body


def test_curate_init_is_tracked():
    init_file = REPO_ROOT / "curate" / "__init__.py"
    assert init_file.exists(), "curate/__init__.py is required for package imports"

"""Public entry points must prominently disclose pending validation corrections."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_ENTRY_POINTS = (
    "CardioOracle.html",
    "e156-submission/assets/CardioOracle.html",
    "e156-submission/index.html",
    "e156-submission/assets/index.html",
    "index.html",
)


@pytest.mark.parametrize("path", PUBLIC_ENTRY_POINTS)
def test_visible_validation_correction_notice(path):
    html = (ROOT / path).read_text(encoding="utf-8")
    assert "Validation correction" in html
    assert "not independent held-out validation" in html or "not valid independent holdout estimates" in html
    assert "docs/validation-audit-2026-10-15.md" in html


@pytest.mark.parametrize("path", PUBLIC_ENTRY_POINTS[:4])
def test_disclosure_is_visible_before_app_or_manuscript(path):
    html = (ROOT / path).read_text(encoding="utf-8")
    body_start = html.index("<body>")
    notice = html.index('id="cardiooracle-validation-notice"')
    assert body_start < notice < body_start + 250
    assert 'role="alert"' in html[body_start:notice + 120]

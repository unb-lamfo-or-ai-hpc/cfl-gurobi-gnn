"""Regression checks for the evidence-only delivery auditor."""
import importlib.util
from pathlib import Path
import zipfile
import pytest

SPEC = importlib.util.spec_from_file_location('delivery', Path(__file__).resolve().parents[2] / 'scripts/audit_pr50_delivery.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

def test_classification_recomputes_confusion_counts():
    result = MOD.classification(dict(tp=2398, tn=3216964, fp=2063, fn=1375))
    assert result['f1_score'] == pytest.approx(0.5824629584649016)
    assert result['precision'] == pytest.approx(0.5375476350594037)

def test_unsafe_archive_is_rejected_before_reading(tmp_path):
    path = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('../escape', 'untrusted')
    with pytest.raises(ValueError, match='Unsafe'):
        MOD.audit(path)

def test_zero_positive_predictions():
    result = MOD.classification(dict(tp=0, tn=10, fp=0, fn=2))
    assert result['precision'] == result['recall'] == result['f1_score'] == 0

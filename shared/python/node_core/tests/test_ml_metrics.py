"""
Unit tests for ml_metrics module.
"""
import pytest
import numpy as np
from node_core import (
    compute_metrics,
    get_classification_report,
    compute_roc_curve,
    aggregate_metrics
)


def test_compute_metrics():
    """Test metrics computation."""
    y_true = [0, 1, 1, 0, 1, 0, 1, 0]
    y_pred = [0, 1, 0, 0, 1, 0, 1, 1]
    y_probs = [0.1, 0.9, 0.4, 0.2, 0.8, 0.3, 0.85, 0.6]
    
    metrics = compute_metrics(y_true, y_pred, y_probs)
    
    assert 'accuracy' in metrics
    assert 'f1' in metrics
    assert 'precision' in metrics
    assert 'recall' in metrics
    assert 'auc' in metrics
    assert 'confusion_matrix' in metrics
    
    # Check value ranges
    assert 0 <= metrics['accuracy'] <= 1
    assert 0 <= metrics['f1'] <= 1
    assert metrics['auc'] is not None


def test_classification_report():
    """Test classification report generation."""
    y_true = [0, 1, 1, 0, 1]
    y_pred = [0, 1, 0, 0, 1]
    
    report = get_classification_report(y_true, y_pred)
    
    assert isinstance(report, str)
    assert 'NORMAL' in report
    assert 'PNEUMONIA' in report
    assert 'precision' in report
    assert 'recall' in report


def test_compute_roc_curve():
    """Test ROC curve computation."""
    y_true = [0, 1, 1, 0, 1, 0]
    y_probs = [0.1, 0.9, 0.8, 0.2, 0.85, 0.3]
    
    fpr, tpr, auc_score = compute_roc_curve(y_true, y_probs)
    
    assert len(fpr) > 0
    assert len(tpr) > 0
    assert 0 <= auc_score <= 1


def test_aggregate_metrics():
    """Test metrics aggregation across folds."""
    metrics_list = [
        {'accuracy': 0.90, 'f1': 0.88, 'auc': 0.92},
        {'accuracy': 0.92, 'f1': 0.90, 'auc': 0.94},
        {'accuracy': 0.88, 'f1': 0.86, 'auc': 0.90},
    ]
    
    aggregated = aggregate_metrics(metrics_list)
    
    assert 'accuracy_mean' in aggregated
    assert 'accuracy_std' in aggregated
    assert 'f1_mean' in aggregated
    assert 'auc_mean' in aggregated
    
    # Check mean calculation
    assert abs(aggregated['accuracy_mean'] - 0.90) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

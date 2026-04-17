"""
ML Metrics Module - Evaluation metrics and performance analysis.
"""
import numpy as np
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    confusion_matrix, classification_report, roc_curve, auc,
    roc_auc_score
)
from typing import Dict, List, Tuple


def compute_metrics(
    y_true: List[int],
    y_pred: List[int],
    y_probs: List[float] = None
) -> Dict:
    """
    Compute comprehensive classification metrics.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        y_probs: Predicted probabilities for positive class (optional)
        
    Returns:
        Dict with accuracy, f1, precision, recall, auc, etc.
    """
    metrics = {
        'accuracy': accuracy_score(y_true, y_pred),
        'f1': f1_score(y_true, y_pred, average='binary'),
        'precision': precision_score(y_true, y_pred, average='binary'),
        'recall': recall_score(y_true, y_pred, average='binary'),
    }
    
    # Add per-class metrics
    precision_per_class = precision_score(y_true, y_pred, average=None)
    recall_per_class = recall_score(y_true, y_pred, average=None)
    
    metrics['precision_normal'] = float(precision_per_class[0])
    metrics['precision_pneumonia'] = float(precision_per_class[1])
    metrics['recall_normal'] = float(recall_per_class[0])
    metrics['recall_pneumonia'] = float(recall_per_class[1])
    
    # Compute AUC if probabilities provided
    if y_probs is not None:
        try:
            metrics['auc'] = roc_auc_score(y_true, y_probs)
        except ValueError:
            metrics['auc'] = None
    
    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    metrics['confusion_matrix'] = cm.tolist()
    
    # True negatives, false positives, false negatives, true positives
    if cm.shape == (2, 2):
        tn, fp, fn, tp = cm.ravel()
        metrics['true_negatives'] = int(tn)
        metrics['false_positives'] = int(fp)
        metrics['false_negatives'] = int(fn)
        metrics['true_positives'] = int(tp)
        
        # Specificity
        metrics['specificity'] = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        
        # Sensitivity (same as recall)
        metrics['sensitivity'] = metrics['recall']
    
    return metrics


def get_classification_report(
    y_true: List[int],
    y_pred: List[int],
    class_names: List[str] = None
) -> str:
    """
    Get detailed classification report as string.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        class_names: Optional class names for display
        
    Returns:
        Classification report string
    """
    if class_names is None:
        class_names = ['NORMAL', 'PNEUMONIA']
    
    return classification_report(y_true, y_pred, target_names=class_names)


def compute_roc_curve(
    y_true: List[int],
    y_probs: List[float]
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Compute ROC curve data.
    
    Args:
        y_true: True binary labels
        y_probs: Predicted probabilities for positive class
        
    Returns:
        Tuple of (fpr, tpr, auc_score)
    """
    fpr, tpr, _ = roc_curve(y_true, y_probs)
    auc_score = auc(fpr, tpr)
    
    return fpr, tpr, auc_score


def compute_confusion_matrix(
    y_true: List[int],
    y_pred: List[int]
) -> np.ndarray:
    """
    Compute confusion matrix.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        
    Returns:
        2D numpy array confusion matrix
    """
    return confusion_matrix(y_true, y_pred)


def aggregate_metrics(metrics_list: List[Dict]) -> Dict:
    """
    Aggregate metrics from multiple folds/runs.
    
    Args:
        metrics_list: List of metric dicts
        
    Returns:
        Dict with mean and std for each metric
    """
    if not metrics_list:
        return {}
    
    # Get all metric keys (excluding non-numeric ones)
    numeric_keys = [
        'accuracy', 'f1', 'precision', 'recall', 'auc',
        'precision_normal', 'precision_pneumonia',
        'recall_normal', 'recall_pneumonia',
        'specificity', 'sensitivity'
    ]
    
    aggregated = {}
    
    for key in numeric_keys:
        values = [m[key] for m in metrics_list if key in m and m[key] is not None]
        if values:
            aggregated[f'{key}_mean'] = float(np.mean(values))
            aggregated[f'{key}_std'] = float(np.std(values))
            aggregated[f'{key}_min'] = float(np.min(values))
            aggregated[f'{key}_max'] = float(np.max(values))
    
    return aggregated


def format_metrics_for_display(metrics: Dict) -> str:
    """
    Format metrics dict as readable string.
    
    Args:
        metrics: Metrics dictionary
        
    Returns:
        Formatted string
    """
    lines = []
    lines.append("=" * 50)
    lines.append("PERFORMANCE METRICS")
    lines.append("=" * 50)
    
    # Main metrics
    if 'accuracy' in metrics:
        lines.append(f"Accuracy:  {metrics['accuracy']:.4f}")
    if 'f1' in metrics:
        lines.append(f"F1-Score:  {metrics['f1']:.4f}")
    if 'auc' in metrics and metrics['auc'] is not None:
        lines.append(f"AUC:       {metrics['auc']:.4f}")
    
    lines.append("-" * 50)
    
    # Per-class metrics
    if 'precision_normal' in metrics:
        lines.append(f"Precision (NORMAL):     {metrics['precision_normal']:.4f}")
    if 'precision_pneumonia' in metrics:
        lines.append(f"Precision (PNEUMONIA):  {metrics['precision_pneumonia']:.4f}")
    if 'recall_normal' in metrics:
        lines.append(f"Recall (NORMAL):        {metrics['recall_normal']:.4f}")
    if 'recall_pneumonia' in metrics:
        lines.append(f"Recall (PNEUMONIA):     {metrics['recall_pneumonia']:.4f}")
    
    lines.append("=" * 50)
    
    return "\n".join(lines)

"""
Node Core - Shared ML and FL utilities for federated medical imaging.
"""

__version__ = "0.1.0"

# ML modules
from .ml_models import (
    get_model,
    get_final_conv_layer,
    save_model,
    load_model,
    count_parameters
)

from .ml_training import (
    EarlyStopping,
    train_epoch,
    validate,
    train_model,
    get_optimizer,
    get_scheduler
)

from .ml_inference import (
    predict_single_image,
    predict_batch,
    GradCAM,
    apply_colormap_on_image,
    save_gradcam_overlay,
    batch_inference_with_gradcam
)

from .ml_metrics import (
    compute_metrics,
    get_classification_report,
    compute_roc_curve,
    compute_confusion_matrix,
    aggregate_metrics,
    format_metrics_for_display
)

from .data_utils import (
    get_train_transforms,
    get_val_transforms,
    load_dataset,
    create_stratified_folds,
    create_dataloaders,
    get_class_distribution,
    denormalize_image,
    IMAGENET_MEAN,
    IMAGENET_STD
)

from .utils_hash import compute_model_hash

# Federated Learning
from .fl_client import FederatedClient
from .fl_aggregator import FedAvgAggregator
from .fl_utils import (
    compute_delta_statistics,
    compare_models,
    scale_delta,
    clip_delta,
    add_noise_to_delta,
    compute_cosine_similarity,
    check_model_compatibility,
    compute_update_quality_score,
    simulate_fl_round
)

__all__ = [
    # ML Models
    'get_model',
    'get_final_conv_layer',
    'save_model',
    'load_model',
    'count_parameters',
    
    # Training
    'EarlyStopping',
    'train_epoch',
    'validate',
    'train_model',
    'get_optimizer',
    'get_scheduler',
    
    # Inference
    'predict_single_image',
    'predict_batch',
    'GradCAM',
    'apply_colormap_on_image',
    'save_gradcam_overlay',
    'batch_inference_with_gradcam',
    
    # Metrics
    'compute_metrics',
    'get_classification_report',
    'compute_roc_curve',
    'compute_confusion_matrix',
    'aggregate_metrics',
    'format_metrics_for_display',
    
    # Data
    'get_train_transforms',
    'get_val_transforms',
    'load_dataset',
    'create_stratified_folds',
    'create_dataloaders',
    'get_class_distribution',
    'denormalize_image',
    'IMAGENET_MEAN',
    'IMAGENET_STD',
    
    # Utils
    'compute_model_hash',
    
    # Federated Learning
    'FederatedClient',
    'FedAvgAggregator',
    'compute_delta_statistics',
    'compare_models',
    'scale_delta',
    'clip_delta',
    'add_noise_to_delta',
    'compute_cosine_similarity',
    'check_model_compatibility',
    'compute_update_quality_score',
    'simulate_fl_round',
]

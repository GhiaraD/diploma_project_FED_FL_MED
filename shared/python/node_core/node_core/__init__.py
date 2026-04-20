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

# Federated Learning - Flower Integration
from .flower_strategy import FedMedStrategy, create_fedmed_strategy

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
    
    # Federated Learning - Flower
    'FedMedStrategy',
    'create_fedmed_strategy',
]

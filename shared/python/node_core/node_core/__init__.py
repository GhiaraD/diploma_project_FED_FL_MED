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

# Cryptographic utilities
from .crypto_utils import (
    PayloadSigner,
    SignatureCache,
    create_payload_signer,
    sign_model_parameters,
    verify_model_parameters
)

# FastAPI SSL/HTTPS utilities (optional - only for API services)
try:
    from .fastapi_ssl import (
        SSLConfig,
        ClientCertificateMiddleware,
        configure_fastapi_ssl,
        get_uvicorn_config
    )
    _FASTAPI_SSL_AVAILABLE = True
except ImportError:
    # FastAPI not available (e.g., in worker containers)
    _FASTAPI_SSL_AVAILABLE = False
    SSLConfig = None
    ClientCertificateMiddleware = None
    configure_fastapi_ssl = None
    get_uvicorn_config = None

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
    
    # Cryptographic utilities
    'PayloadSigner',
    'SignatureCache',
    'create_payload_signer',
    'sign_model_parameters',
    'verify_model_parameters',
    
    # FastAPI SSL/HTTPS utilities
    'SSLConfig',
    'ClientCertificateMiddleware',
    'configure_fastapi_ssl',
    'get_uvicorn_config',
    
    # Federated Learning - Flower
    'FedMedStrategy',
    'create_fedmed_strategy',
]

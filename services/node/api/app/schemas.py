"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================================================
# Health & Status
# ============================================================================

class HealthResponse(BaseModel):
    ok: bool
    node_id: str
    timestamp: str


class NodeStatusResponse(BaseModel):
    node_id: str
    storage_root: str
    central_url: str
    device: str
    models: Dict[str, int]
    jobs: Dict[str, int]
    datasets: int


# ============================================================================
# Models
# ============================================================================

class ModelInfo(BaseModel):
    model_id: str
    model_name: str
    version: str
    type: str
    round_id: Optional[str]
    metrics: Optional[Dict[str, float]]
    created_at: str


class ModelListResponse(BaseModel):
    models: List[ModelInfo]


class ModelPromoteRequest(BaseModel):
    model_id: str


# ============================================================================
# Jobs
# ============================================================================

class JobInfo(BaseModel):
    job_id: str
    job_type: str
    status: str
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: str
    completed_at: Optional[str]


class JobCreateResponse(BaseModel):
    job_id: str
    task_id: str
    status: str


# ============================================================================
# Training
# ============================================================================

class TrainRequest(BaseModel):
    dataset_id: str
    model_name: str = "resnet18"
    num_epochs: int = 10
    batch_size: int = 32
    learning_rate: float = 0.001
    optimizer: str = "adam"
    scheduler: Optional[str] = "cosine"


# ============================================================================
# Inference
# ============================================================================

class InferRequest(BaseModel):
    image_paths: List[str]
    model_id: Optional[str] = None  # If None, uses deployed model
    generate_gradcam: bool = True


class InferResponse(BaseModel):
    job_id: str
    task_id: str
    status: str


class InferenceResultItem(BaseModel):
    result_id: str
    image_path: str
    predicted_class: int
    confidence: float
    probabilities: List[float]
    gradcam_path: Optional[str]


# ============================================================================
# Federated Learning
# ============================================================================

class FederatedJoinRequest(BaseModel):
    pass  # No additional params needed


class FederatedStatusResponse(BaseModel):
    round_id: str
    node_id: str
    local_status: str
    central_status: Dict[str, Any]


# ============================================================================
# Datasets
# ============================================================================

class DatasetInfo(BaseModel):
    dataset_id: str
    name: str
    split: str
    num_samples: int
    num_normal: int
    num_pneumonia: int
    created_at: str


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    path: str
    num_samples: int
    num_normal: int
    num_pneumonia: int

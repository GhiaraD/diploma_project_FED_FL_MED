"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================================================
# Authentication & Authorization
# ============================================================================

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12, description="Password must be at least 12 characters")
    role: str = Field(..., pattern="^(admin|doctor|researcher|viewer)$")
    node_id: str = Field(..., pattern="^(node1|node2|node3|central)$")


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    node_id: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes in seconds
    user: Optional[UserResponse] = None


class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    node_id: Optional[str] = None
    permissions: List[str] = []


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=12)


class ApiKeyCreate(BaseModel):
    node_id: str = Field(..., pattern="^(node1|node2|node3|central)$")
    permissions: List[str]
    expires_days: int = Field(default=365, ge=1, le=3650)  # 1 day to 10 years
    description: Optional[str] = None


class ApiKeyResponse(BaseModel):
    id: str
    node_id: str
    permissions: List[str]
    expires_at: datetime
    is_active: bool
    created_at: datetime
    last_used: Optional[datetime]
    # Note: We never return the actual key after creation
    
    class Config:
        from_attributes = True


class ApiKeyCreateResponse(BaseModel):
    """Response when creating a new API key - includes the actual key."""
    api_key: str  # The actual key - only shown once!
    key_info: ApiKeyResponse


class AuditLogResponse(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    user_id: Optional[str]
    node_id: str
    endpoint: Optional[str]
    ip_address: Optional[str]
    response_status: Optional[int]
    duration_ms: Optional[int]
    details: Optional[Dict[str, Any]]
    
    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle JSON string in details field."""
        import json
        data = {
            'id': obj.id,
            'timestamp': obj.timestamp,
            'event_type': obj.event_type,
            'user_id': obj.user_id,
            'node_id': obj.node_id,
            'endpoint': obj.endpoint,
            'ip_address': obj.ip_address,
            'response_status': obj.response_status,
            'duration_ms': obj.duration_ms,
            'details': json.loads(obj.details) if obj.details and isinstance(obj.details, str) else obj.details
        }
        return cls.model_validate(data)
    
    model_config = {"from_attributes": True}


class SecurityMetrics(BaseModel):
    """Security metrics for monitoring dashboard."""
    authentication: Dict[str, int]
    authorization: Dict[str, int]
    rate_limiting: Dict[str, int]
    audit: Dict[str, int]
    active_sessions: int
    failed_logins_last_hour: int


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
    healthy: bool
    uptime_seconds: int
    disk_used_gb: float
    disk_total_gb: float
    models: Dict[str, int]
    jobs: Dict[str, int]
    datasets: int
    active_datasets: int


# ============================================================================
# Models
# ============================================================================

class ModelInfo(BaseModel):
    model_id: str
    model_name: str
    version: str
    type: str
    labels: Optional[List[str]] = []
    round_id: Optional[str]
    metrics: Optional[Dict[str, Any]]  # Changed from Dict[str, float] to support lists like confusion_matrix
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
    status: Optional[str] = None  # Alias for local_status for compatibility
    job_id: Optional[str] = None
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
    is_active: bool = False
    created_at: str


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    path: str
    num_samples: int
    num_normal: int
    num_pneumonia: int


class DatasetRegisterRequest(BaseModel):
    path: str
    name: str
    split: str = "train"


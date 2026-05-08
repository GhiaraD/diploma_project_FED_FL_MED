"""
Database models and session management.
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid
from .config import settings

def get_local_now():
    """
    Get current datetime in local system timezone.
    Automatically detects the timezone from the system.
    """
    return datetime.now().astimezone()

def generate_uuid():
    """Generate UUID for primary keys."""
    return str(uuid.uuid4())

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# ============================================================================
# Security Models
# ============================================================================

class User(Base):
    """User authentication and authorization table."""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, index=True)  # admin, doctor, researcher, viewer
    node_id = Column(String, nullable=False, index=True)  # node1, node2, node3
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=get_local_now, nullable=False)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=get_local_now, nullable=False)


class ApiKey(Base):
    """API keys for inter-node communication."""
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    key_hash = Column(String, unique=True, nullable=False, index=True)  # SHA256 hash of the key
    node_id = Column(String, nullable=False, index=True)  # Source node ID
    permissions = Column(Text, nullable=False)  # JSON array of permissions
    expires_at = Column(DateTime, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=get_local_now, nullable=False)
    last_used = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)  # User ID who created the key


class AuditLog(Base):
    """Security audit logging table."""
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=get_local_now, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)  # login, api_request, data_access, etc.
    user_id = Column(String, nullable=True, index=True)  # User who performed the action
    node_id = Column(String, nullable=False, index=True)  # Node where action occurred
    endpoint = Column(String, nullable=True)  # API endpoint accessed
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    request_id = Column(String, nullable=True, index=True)
    response_status = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)  # JSON with additional details


class Session(Base):
    """Active user sessions for JWT management."""
    __tablename__ = "sessions"
    
    jti = Column(String, primary_key=True)  # JWT ID
    user_id = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=get_local_now, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)


# ============================================================================
# Existing Application Models
# ============================================================================

class Model(Base):
    """Model registry table."""
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String, unique=True, index=True)  # e.g., "resnet18_R-1_candidate"
    model_name = Column(String, index=True)  # e.g., "resnet18"
    version = Column(String)  # e.g., "R-1"
    type = Column(String, index=True)  # "candidate", "deployed", "archived" (kept for backward compatibility)
    labels = Column(JSON, nullable=True)  # ["global", "active", "candidate"] - can have 1-2 labels
    session_id = Column(String, nullable=True, index=True)  # FL session (job_id) that produced this model
    file_path = Column(String)  # Path to .pt file
    metrics = Column(JSON, nullable=True)  # Training/validation metrics
    created_at = Column(DateTime, default=get_local_now)
    promoted_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)


class Job(Base):
    """Job tracking table."""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)  # Celery task ID
    job_type = Column(String, index=True)  # "train", "infer", "federated_train"
    status = Column(String, index=True)  # "pending", "running", "completed", "failed"
    params = Column(JSON)  # Job parameters
    result = Column(JSON, nullable=True)  # Job result
    error = Column(Text, nullable=True)  # Error message if failed
    created_at = Column(DateTime, default=get_local_now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class Dataset(Base):
    """Dataset metadata table."""
    __tablename__ = "datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(String, unique=True, index=True)
    name = Column(String)
    path = Column(String)  # Path to dataset directory
    split = Column(String)  # "train", "val", "test"
    num_samples = Column(Integer)
    num_normal = Column(Integer, nullable=True)
    num_pneumonia = Column(Integer, nullable=True)
    is_active = Column(Integer, default=0)  # 1 if active dataset for training, 0 otherwise
    created_at = Column(DateTime, default=get_local_now)


class InferenceResult(Base):
    """Inference results table."""
    __tablename__ = "inference_results"
    
    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(String, unique=True, index=True)
    job_id = Column(String, index=True)
    model_id = Column(String, index=True)
    image_path = Column(String)
    predicted_class = Column(Integer)  # 0=NORMAL, 1=PNEUMONIA
    confidence = Column(Float)
    probabilities = Column(JSON)  # [prob_normal, prob_pneumonia]
    gradcam_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=get_local_now)


# Create all tables
Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

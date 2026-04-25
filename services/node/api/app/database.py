"""
Database models and session management.
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from .config import settings

def get_local_now():
    """
    Get current datetime in local system timezone.
    Automatically detects the timezone from the system.
    """
    return datetime.now().astimezone()

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


class Model(Base):
    """Model registry table."""
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String, unique=True, index=True)  # e.g., "resnet18_R-1_candidate"
    model_name = Column(String, index=True)  # e.g., "resnet18"
    version = Column(String)  # e.g., "R-1"
    type = Column(String, index=True)  # "candidate", "deployed", "archived" (kept for backward compatibility)
    labels = Column(JSON, nullable=True)  # ["global", "active", "candidate"] - can have 1-2 labels
    round_id = Column(String, nullable=True, index=True)  # FL round ID
    base_model_hash = Column(String, nullable=True)  # Hash of base model for FL
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

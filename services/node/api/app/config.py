"""
Configuration module for Node API.
"""
import os
from pathlib import Path


class Settings:
    """Application settings from environment variables."""
    
    # Node identification
    NODE_ID: str = os.getenv("NODE_ID", "node1")
    
    # Storage paths
    STORAGE_ROOT: str = os.getenv("STORAGE_ROOT", "/storage")
    DATASETS_DIR: str = os.path.join(STORAGE_ROOT, "datasets")
    MODELS_DIR: str = os.path.join(STORAGE_ROOT, "models")
    RESULTS_DIR: str = os.path.join(STORAGE_ROOT, "results")
    DELTAS_DIR: str = os.path.join(STORAGE_ROOT, "deltas")
    
    # Model registry subdirectories
    MODELS_CANDIDATE_DIR: str = os.path.join(MODELS_DIR, "candidate")
    MODELS_DEPLOYED_DIR: str = os.path.join(MODELS_DIR, "deployed")
    MODELS_ARCHIVED_DIR: str = os.path.join(MODELS_DIR, "archived")
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{STORAGE_ROOT}/node.db"
    )
    
    # Redis/Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL
    
    # Security settings
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "fed-med-fl-secret-key-2026-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
    
    # Redis for security (sessions, rate limiting)
    REDIS_HOST: str = os.getenv("REDIS_HOST", f"{NODE_ID}-redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_SECURITY_DB: int = int(os.getenv("REDIS_SECURITY_DB", "1"))
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    
    # API Keys
    API_KEY_EXPIRE_DAYS: int = int(os.getenv("API_KEY_EXPIRE_DAYS", "365"))
    INTER_NODE_API_KEY: str = os.getenv("INTER_NODE_API_KEY", "")
    
    # Audit logging
    AUDIT_LOG_LEVEL: str = os.getenv("AUDIT_LOG_LEVEL", "INFO")
    AUDIT_LOG_RETENTION_DAYS: int = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "2555"))  # 7 years
    
    # Central server
    CENTRAL_URL: str = os.getenv("CENTRAL_URL", "http://central:8081")
    FLOWER_SERVER: str = os.getenv("FLOWER_SERVER", "central:8080")
    
    # API settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    # ML settings
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "resnet18")
    DEFAULT_BATCH_SIZE: int = int(os.getenv("DEFAULT_BATCH_SIZE", "32"))
    DEFAULT_NUM_EPOCHS: int = int(os.getenv("DEFAULT_NUM_EPOCHS", "10"))
    DEFAULT_LEARNING_RATE: float = float(os.getenv("DEFAULT_LEARNING_RATE", "0.001"))
    
    # Device
    DEVICE: str = os.getenv("DEVICE", "cuda" if os.path.exists("/dev/nvidia0") else "cpu")
    
    @classmethod
    def create_directories(cls):
        """Create all required storage directories."""
        dirs = [
            cls.STORAGE_ROOT,
            cls.DATASETS_DIR,
            cls.MODELS_DIR,
            cls.RESULTS_DIR,
            cls.DELTAS_DIR,
            cls.MODELS_CANDIDATE_DIR,
            cls.MODELS_DEPLOYED_DIR,
            cls.MODELS_ARCHIVED_DIR,
            os.path.join(cls.RESULTS_DIR, "inference"),
            os.path.join(cls.RESULTS_DIR, "training"),
        ]
        
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)


# Create settings instance
settings = Settings()

# Create directories on import
settings.create_directories()
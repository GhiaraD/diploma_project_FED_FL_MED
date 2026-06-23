from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import logging
import mimetypes
import os
import shutil
import time
import uuid
import asyncio
import json

from .config import settings
from .database import get_db, Model, Job, Dataset, InferenceResult, NodeParticipation
from .schemas import (
    ModelInfo, ModelPromoteRequest, ModelListResponse,
    JobInfo, JobCreateResponse,
    InferRequest, InferResponse,
    FederatedStatusResponse,
    DatasetInfo, DatasetUploadResponse, DatasetRegisterRequest,
    HealthResponse, NodeStatusResponse
)
from .security import (
    get_current_user, require_permission, require_role, require_role_exact,
    rate_limit_check, audit_log_middleware, optional_auth, security_manager
)
from .auth import router as auth_router
from .audit_helper import (
    log_dataset_action, log_model_action, log_inference_action,
    log_training_action, log_federated_action, log_job_action
)

app = FastAPI(
    title=f"Node API - {settings.NODE_ID}",
    version="0.2.0",
    description="Hospital Node API for Federated Learning Medical Imaging with Security"
)

# CORS middleware - Allow requests from UI (MUST be added before routers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://localhost:3002", 
        "http://localhost:3003",
        "http://localhost:3000",
        "http://localhost:3004",
          # Dev mode
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers to frontend
)

# Add middleware to prevent caching and ensure CORS headers
@app.middleware("http")
async def add_cors_and_cache_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add cache prevention headers
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    # Ensure CORS headers are present for all responses
    origin = request.headers.get("origin")
    if origin in ["http://localhost:3001", "http://localhost:3002", "http://localhost:3003", "http://localhost:3000"]:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

# Include authentication routes (AFTER CORS middleware)
app.include_router(auth_router)


# ============================================================================
# Health & Status Endpoints (Public)
# ============================================================================

@app.get("/api/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint - no authentication required."""
    return {
        "ok": True,
        "node_id": settings.NODE_ID,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/node/status", response_model=NodeStatusResponse)
def node_status(
    current_user: dict = Depends(require_permission("read:status")),
    db: Session = Depends(get_db)
):
    """Get node status and statistics - requires authentication."""
    uptime_seconds = int(time.time() % 86400)  # Simplified: seconds since midnight
    
    # Get disk usage for storage directory
    try:
        disk_usage = shutil.disk_usage(settings.STORAGE_ROOT)
        disk_total_gb = disk_usage.total / (1024**3)  # Convert to GB
        disk_used_gb = disk_usage.used / (1024**3)
    except Exception:
        disk_total_gb = 0.0
        disk_used_gb = 0.0
    
    # Count models by type
    models_count = {
        "candidate": db.query(Model).filter(Model.type == "candidate").count(),
        "deployed": db.query(Model).filter(Model.type == "deployed").count(),
        "archived": db.query(Model).filter(Model.type == "archived").count()
    }
    
    # Count jobs by status
    jobs_count = {
        "pending": db.query(Job).filter(Job.status == "pending").count(),
        "running": db.query(Job).filter(Job.status == "running").count(),
        "completed": db.query(Job).filter(Job.status == "completed").count(),
        "failed": db.query(Job).filter(Job.status == "failed").count()
    }
    
    # Count datasets
    datasets_count = db.query(Dataset).count()
    active_datasets_count = db.query(Dataset).filter(Dataset.is_active == True).count()
    
    return {
        "node_id": settings.NODE_ID,
        "storage_root": settings.STORAGE_ROOT,
        "central_url": settings.CENTRAL_URL,
        "device": settings.DEVICE,
        "healthy": True,
        "uptime_seconds": uptime_seconds,
        "disk_used_gb": round(disk_used_gb, 2),
        "disk_total_gb": round(disk_total_gb, 2),
        "models": models_count,
        "jobs": jobs_count,
        "datasets": datasets_count,
        "active_datasets": active_datasets_count
    }


# ============================================================================
# Dataset Management Endpoints
# ============================================================================

@app.get("/api/data/browse")
def browse_filesystem(
    directory: str = None,
    current_user: dict = Depends(require_permission("read:datasets")),
    db: Session = Depends(get_db)
):
    """
    Browse filesystem for existing datasets.
    
    Simulates hospital system where data already exists on-premise.
    Returns directories and their contents for dataset selection.
    
    Args:
        directory: Path to browse (defaults to storage root)
    
    Returns:
        List of directories and files
    """
    # Default to datasets directory
    if not directory:
        directory = settings.DATASETS_DIR
    
    # Security: restrict to allowed directories
    allowed_dirs = [
        settings.DATASETS_DIR,
        settings.STORAGE_ROOT,
        "/hospital_data",
        "/mnt/radiology"
    ]
    
    # Check if directory is allowed
    if not any(directory.startswith(allowed) for allowed in allowed_dirs):
        raise HTTPException(
            status_code=403,
            detail=f"Access to directory '{directory}' is not allowed"
        )
    
    if not os.path.exists(directory):
        raise HTTPException(
            status_code=404,
            detail=f"Directory not found: {directory}"
        )
    
    # List contents
    subdirs = []
    files = []
    
    try:
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            
            if os.path.isdir(item_path):
                # A valid dataset must have all three splits: train, val, test
                # each containing NORMAL and PNEUMONIA subfolders
                def _split_valid(base, split):
                    return (
                        os.path.exists(os.path.join(base, split, "NORMAL")) and
                        os.path.exists(os.path.join(base, split, "PNEUMONIA"))
                    )

                is_dataset = (
                    _split_valid(item_path, "train") and
                    _split_valid(item_path, "val") and
                    _split_valid(item_path, "test")
                )

                # Count samples across all splits if it's a valid dataset
                num_samples = 0
                num_normal = 0
                num_pneumonia = 0

                if is_dataset:
                    for split in ("train", "val", "test"):
                        n_path = os.path.join(item_path, split, "NORMAL")
                        p_path = os.path.join(item_path, split, "PNEUMONIA")
                        num_normal += len([f for f in os.listdir(n_path) if os.path.isfile(os.path.join(n_path, f))])
                        num_pneumonia += len([f for f in os.listdir(p_path) if os.path.isfile(os.path.join(p_path, f))])
                    num_samples = num_normal + num_pneumonia
                
                subdirs.append({
                    "name": item,
                    "path": item_path,
                    "type": "directory",
                    "is_dataset": is_dataset,
                    "num_samples": num_samples,
                    "num_normal": num_normal,
                    "num_pneumonia": num_pneumonia
                })
            elif os.path.isfile(item_path):
                files.append({
                    "name": item,
                    "path": item_path,
                    "type": "file",
                    "size": os.path.getsize(item_path)
                })
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail=f"No permission to read directory: {directory}"
        )
    
    # Get parent directory
    parent_dir = os.path.dirname(directory) if directory != "/" else None
    
    return {
        "current_directory": directory,
        "parent_directory": parent_dir,
        "subdirectories": subdirs,
        "files": files,
        "total_subdirs": len(subdirs),
        "total_files": len(files)
    }


@app.post("/api/data/register")
async def register_dataset(
    request_data: DatasetRegisterRequest,
    request: Request,
    current_user: dict = Depends(require_permission("write:datasets")),
    db: Session = Depends(get_db)
):
    """
    Register an existing dataset from filesystem.
    
    Instead of uploading, this registers a dataset that already exists
    on the hospital system (on-premise data).
    
    Args:
        request_data: DatasetRegisterRequest with path, name, and split
    
    Returns:
        Dataset information
    """
    logger = logging.getLogger(__name__)
    start_time = time.time()
    
    # Log the incoming request data for debugging
    logger.info(f"Dataset register request: path={request_data.path}, name={request_data.name}")
    
    # Validate path exists
    if not os.path.exists(request_data.path):
        logger.error(f"Dataset path not found: {request_data.path}")
        raise HTTPException(
            status_code=404,
            detail=f"Dataset path not found: {request_data.path}"
        )
    
    if not os.path.isdir(request_data.path):
        logger.error(f"Path is not a directory: {request_data.path}")
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a directory: {request_data.path}"
        )
    
    # Validate dataset structure: must have train/val/test, each with NORMAL and PNEUMONIA
    for split in ("train", "val", "test"):
        for cls in ("NORMAL", "PNEUMONIA"):
            cls_path = os.path.join(request_data.path, split, cls)
            if not os.path.exists(cls_path):
                logger.error(f"Missing folder: {cls_path}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Dataset must contain {split}/{cls} folder at {cls_path}"
                )
    
    # Count samples across all splits
    num_normal = 0
    num_pneumonia = 0
    for split in ("train", "val", "test"):
        n_path = os.path.join(request_data.path, split, "NORMAL")
        p_path = os.path.join(request_data.path, split, "PNEUMONIA")
        num_normal += len([f for f in os.listdir(n_path) if os.path.isfile(os.path.join(n_path, f))])
        num_pneumonia += len([f for f in os.listdir(p_path) if os.path.isfile(os.path.join(p_path, f))])
    num_samples = num_normal + num_pneumonia
    
    # Check if dataset already registered
    existing = db.query(Dataset).filter(Dataset.path == request_data.path).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Dataset already registered with ID: {existing.dataset_id}"
        )
    
    # Generate dataset ID
    dataset_id = f"dataset_{uuid.uuid4().hex[:8]}"
    
    # Save to database
    dataset = Dataset(
        dataset_id=dataset_id,
        name=request_data.name,
        path=request_data.path,
        split="all",
        num_samples=num_samples,
        num_normal=num_normal,
        num_pneumonia=num_pneumonia
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    
    # Log dataset registration
    await log_dataset_action(
        action="registered",
        user_id=current_user["id"],
        request=request,
        db=db,
        dataset_id=dataset_id,
        dataset_name=request_data.name,
        details={
            "num_samples": num_samples,
            "num_normal": num_normal,
            "num_pneumonia": num_pneumonia
        },
        response_status=200,
        start_time=start_time
    )
    
    return {
        "dataset_id": dataset_id,
        "name": request_data.name,
        "path": request_data.path,
        "split": "all",
        "num_samples": num_samples,
        "num_normal": num_normal,
        "num_pneumonia": num_pneumonia,
        "created_at": dataset.created_at.isoformat()
    }


@app.get("/api/data/list", response_model=List[DatasetInfo])
def list_datasets(
    current_user: dict = Depends(require_permission("read:datasets")),
    db: Session = Depends(get_db)
):
    """List all registered datasets."""
    datasets = db.query(Dataset).all()
    return [
        {
            "dataset_id": d.dataset_id,
            "name": d.name,
            "split": d.split,
            "num_samples": d.num_samples,
            "num_normal": d.num_normal,
            "num_pneumonia": d.num_pneumonia,
            "is_active": bool(d.is_active),
            "created_at": d.created_at.isoformat()
        }
        for d in datasets
    ]


@app.post("/api/data/set-active/{dataset_id}")
async def set_active_dataset(
    dataset_id: str,
    request: Request,
    current_user: dict = Depends(require_permission("write:datasets")),
    db: Session = Depends(get_db)
):
    """
    Set a dataset as active for training.
    
    The active dataset will be used by default in training operations.
    """
    start_time = time.time()
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Deactivate all other datasets
    db.query(Dataset).update({"is_active": False})
    
    # Activate selected dataset
    dataset.is_active = True
    db.commit()
    
    # Log dataset activation
    await log_dataset_action(
        action="activated",
        user_id=current_user["id"],
        request=request,
        db=db,
        dataset_id=dataset_id,
        dataset_name=dataset.name,
        details={
            "split": dataset.split,
            "num_samples": dataset.num_samples
        },
        response_status=200,
        start_time=start_time
    )
    
    return {
        "status": "success",
        "dataset_id": dataset_id,
        "message": f"Dataset {dataset.name} set as active"
    }


@app.get("/api/data/active")
def get_active_dataset(
    current_user: dict = Depends(require_permission("read:datasets")),
    db: Session = Depends(get_db)
):
    """Get the currently active dataset."""
    dataset = db.query(Dataset).filter(Dataset.is_active == True).first()
    
    if not dataset:
        return {"active_dataset": None}
    
    return {
        "active_dataset": {
            "dataset_id": dataset.dataset_id,
            "name": dataset.name,
            "split": dataset.split,
            "num_samples": dataset.num_samples,
            "num_normal": dataset.num_normal,
            "num_pneumonia": dataset.num_pneumonia,
            "created_at": dataset.created_at.isoformat()
        }
    }


@app.delete("/api/data/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    request: Request,
    current_user: dict = Depends(require_permission("write:datasets")),
    db: Session = Depends(get_db)
):
    """
    Unregister a dataset.
    
    Note: This only removes the dataset from the registry,
    it does NOT delete the actual files (on-premise data is preserved).
    """
    start_time = time.time()
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Log before deletion
    await log_dataset_action(
        action="deleted",
        user_id=current_user["id"],
        request=request,
        db=db,
        dataset_id=dataset_id,
        dataset_name=dataset.name,
        details={
            "split": dataset.split,
            "num_samples": dataset.num_samples
        },
        response_status=200,
        start_time=start_time
    )
    
    db.delete(dataset)
    db.commit()
    
    return {
        "status": "success",
        "message": f"Dataset {dataset_id} unregistered (files preserved on system)"
    }


# ============================================================================
# Model Registry Endpoints
# ============================================================================

def compute_model_labels(models_list, db: Session):
    """
    Compute labels for models based on F2 score and deployed status.

    Labels:
    - "active": deployed model (used for inference)
    - "global": best model by F2 score on local test data
               (falls back to accuracy if F2 not available)
    - "candidate": neither active nor global (or both)

    A model can have 1-2 labels (e.g., both "global" and "active" if best model is deployed)
    Note: No "archived" label - old deployed models return to "candidate" status
    """
    # Find deployed model
    deployed_model_id = None
    for m in models_list:
        if m.type == "deployed":
            deployed_model_id = m.model_id
            break

    # Find best model by F2 score; fall back to accuracy for models without F2
    best_model_id = None
    best_score = -1.0
    for m in models_list:
        if not m.metrics:
            continue
        # Prefer f2, fall back to accuracy for backward compatibility
        score = m.metrics.get("f2") or m.metrics.get("val_f2")
        if score is None:
            score = m.metrics.get("accuracy")
        if score is not None and float(score) > best_score:
            best_score = float(score)
            best_model_id = m.model_id
    
    # Assign labels
    for m in models_list:
        labels = []
        
        # Check if active (deployed)
        if m.model_id == deployed_model_id:
            labels.append("active")
        
        # Check if global (best)
        if m.model_id == best_model_id:
            labels.append("global")
        
        # If no labels, it's a candidate
        if not labels:
            labels.append("candidate")
        
        # Update database if labels changed
        if m.labels != labels:
            m.labels = labels
        
        # Update type to match labels (for backward compatibility)
        # If model has "active" label, type should be "deployed"
        # Otherwise, type should be "candidate"
        if "active" in labels:
            if m.type != "deployed":
                m.type = "deployed"
        else:
            if m.type != "candidate":
                m.type = "candidate"
    
    db.commit()
    return models_list


@app.get("/api/models/registry", response_model=ModelListResponse)
def list_models(
    type: Optional[str] = None,
    current_user: dict = Depends(require_permission("read:models")),
    db: Session = Depends(get_db)
):
    """List models in registry with computed labels."""
    query = db.query(Model)
    
    if type:
        query = query.filter(Model.type == type)
    
    models = query.order_by(Model.created_at.desc()).all()
    
    # Compute labels for all models
    models = compute_model_labels(models, db)
    
    def normalize_metrics(metrics):
        """Normalize metric names for UI compatibility."""
        if not metrics:
            return metrics
        
        normalized = dict(metrics) if isinstance(metrics, dict) else {}
        
        # Map f1_score to f1 for UI compatibility
        if 'f1_score' in normalized and 'f1' not in normalized:
            normalized['f1'] = normalized['f1_score']
        
        # Expose val_f2 as f2 if top-level f2 is missing
        if 'f2' not in normalized and 'val_f2' in normalized:
            normalized['f2'] = normalized['val_f2']
        
        return normalized
    
    return {
        "models": [
            {
                "model_id": m.model_id,
                "model_name": m.model_name,
                "version": m.version,
                "type": m.type,  # Keep for backward compatibility
                "labels": m.labels or [],
                "session_id": m.session_id,
                "metrics": normalize_metrics(m.metrics),                "created_at": m.created_at.isoformat()
            }
            for m in models
        ]
    }


@app.post("/api/models/promote")
async def promote_model(
    request_data: ModelPromoteRequest,
    request: Request,
    current_user: dict = Depends(require_permission("write:models")),
    db: Session = Depends(get_db)
):
    """
    Promote model to deployed (active).
    
    - Changes current deployed model back to candidate
    - Promotes selected model to deployed
    - Recalculates labels for all models
    """
    start_time = time.time()
    # Get model to promote
    model_to_promote = db.query(Model).filter(
        Model.model_id == request_data.model_id
    ).first()
    
    if not model_to_promote:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Change current deployed model back to candidate
    # Note: We demote ALL deployed models, not just same architecture
    current_deployed = db.query(Model).filter(
        Model.type == "deployed"
    ).first()
    
    if current_deployed:
        current_deployed.type = "candidate"
        
        # Move file back to candidate directory
        old_path = current_deployed.file_path
        
        # Handle case where file might already be in candidate directory
        if "/candidate/" in old_path:
            # File is already in candidate directory, just update the path
            new_path = old_path
        else:
            # Move from deployed to candidate
            new_path = old_path.replace("/deployed/", "/candidate/")
            if os.path.exists(old_path):
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                shutil.move(old_path, new_path)
        
        current_deployed.file_path = new_path
    
    # Promote selected model
    model_to_promote.type = "deployed"
    model_to_promote.promoted_at = datetime.utcnow()
    
    # Move file to deployed directory
    old_path = model_to_promote.file_path
    
    # Handle case where file might already be in deployed directory
    if "/deployed/" in old_path:
        # File is already in deployed directory, just update the path
        new_path = old_path
    else:
        # Move from candidate to deployed
        new_path = old_path.replace("/candidate/", "/deployed/")
        if os.path.exists(old_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)
    
    model_to_promote.file_path = new_path
    
    db.commit()
    
    # Recalculate labels for all models
    all_models = db.query(Model).all()
    compute_model_labels(all_models, db)
    
    # Log model promotion
    await log_model_action(
        action="promoted",
        user_id=current_user["id"],
        request=request,
        db=db,
        model_id=model_to_promote.model_id,
        model_name=model_to_promote.model_name,
        details={
            "version": model_to_promote.version,
            "metrics": model_to_promote.metrics,
            "session_id": model_to_promote.session_id
        },
        response_status=200,
        start_time=start_time
    )
    
    return {
        "status": "success",
        "model_id": model_to_promote.model_id,
        "message": f"Model {model_to_promote.model_id} promoted to active"
    }


@app.get("/api/models/{model_id}")
def get_model_info(
    model_id: str,
    current_user: dict = Depends(require_permission("read:models")),
    db: Session = Depends(get_db)
):
    """Get model information with computed labels."""
    model = db.query(Model).filter(Model.model_id == model_id).first()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Compute labels for this model
    all_models = db.query(Model).all()
    compute_model_labels(all_models, db)
    
    # Refresh model to get updated labels
    db.refresh(model)
    
    return {
        "model_id": model.model_id,
        "model_name": model.model_name,
        "version": model.version,
        "type": model.type,
        "labels": model.labels or [],
        "session_id": model.session_id,
        "file_path": model.file_path,
        "metrics": model.metrics,
        "created_at": model.created_at.isoformat()
    }


# ============================================================================
# Inference Endpoints
# ============================================================================

@app.get("/api/infer/browse")
def browse_hospital_images(
    directory: str = "/hospital_data",
    limit: int = 200,
    current_user: dict = Depends(require_permission("read:datasets")),
    db: Session = Depends(get_db)
):
    """
    Browse available images in hospital data directories.
    
    This helps UI users select images without uploading them.
    Images remain in their original location (on-premise security).
    
    Args:
        directory: Path to directory to browse (must be in allowed list)
        limit: Maximum number of files to return (default 200)
    
    Returns:
        List of image files with metadata
    """
    # Security: restrict to allowed directories only
    allowed_dirs = [
        "/hospital_data",
        "/mnt/radiology",
        os.path.join(settings.STORAGE_ROOT, "test_images"),
        os.path.join(settings.STORAGE_ROOT, "datasets")
    ]
    
    # Check if directory is allowed
    if not any(directory.startswith(allowed) for allowed in allowed_dirs):
        raise HTTPException(
            status_code=403,
            detail=f"Access to directory '{directory}' is not allowed. Allowed directories: {allowed_dirs}"
        )
    
    if not os.path.exists(directory):
        raise HTTPException(
            status_code=404, 
            detail=f"Directory not found: {directory}"
        )
    
    # List image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.dcm', '.dicom', '.tif', '.tiff'}
    files = []
    subdirs = []
    
    try:
        entries = sorted(os.listdir(directory))
        for item in entries:
            item_path = os.path.join(directory, item)
            
            if os.path.isdir(item_path):
                subdirs.append({
                    "name": item,
                    "path": item_path,
                    "type": "directory"
                })
            elif os.path.isfile(item_path):
                ext = os.path.splitext(item)[1].lower()
                if ext in image_extensions:
                    if len(files) < limit:
                        files.append({
                            "name": item,
                            "path": item_path,
                            "size": os.path.getsize(item_path),
                            "type": "file",
                            "extension": ext,
                            "modified": datetime.fromtimestamp(
                                os.path.getmtime(item_path)
                            ).isoformat()
                        })
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail=f"No permission to read directory: {directory}"
        )
    
    return {
        "directory": directory,
        "subdirectories": subdirs,
        "files": files,
        "total_files": len(files),
        "total_subdirs": len(subdirs),
        "truncated": len(files) == limit
    }


@app.post("/api/infer", response_model=InferResponse)
async def run_inference(
    request_data: InferRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_permission("write:inference")),
    db: Session = Depends(get_db)
):
    """
    Run inference on images at specified filesystem paths.
    
    IMPORTANT - On-Premise Medical Imaging:
    - Images must already exist on the server filesystem
    - Paths should be absolute paths to mounted volumes
    - Images are NOT uploaded - they are read from existing locations
    - This ensures medical data never leaves the hospital premises
    - Only inference results (predictions, Grad-CAM) are stored
    
    Example paths:
    - /hospital_data/studies/patient_001/chest_xray.jpg
    - /mnt/radiology/2024/04/study_12345.dcm
    - /storage/datasets/dataset_train_abc123/NORMAL/image001.jpeg
    
    Args:
        request_data: InferRequest with image_paths, model_id, generate_gradcam
    
    Returns:
        Job information (job_id, task_id, status)
    """
    start_time = time.time()
    from .tasks import run_inference_task
    
    # Validate that all image paths exist and are readable
    for path in request_data.image_paths:
        if not os.path.exists(path):
            raise HTTPException(
                status_code=400, 
                detail=f"Image path does not exist: {path}"
            )
        if not os.path.isfile(path):
            raise HTTPException(
                status_code=400,
                detail=f"Path is not a file: {path}"
            )
        if not os.access(path, os.R_OK):
            raise HTTPException(
                status_code=403,
                detail=f"No read permission for path: {path}"
            )
    
    # Create job record
    job_id = f"infer_{uuid.uuid4().hex[:8]}"
    
    job = Job(
        job_id=job_id,
        job_type="infer",
        status="pending",
        params=request_data.dict()
    )
    db.add(job)
    db.commit()
    
    # Log inference start
    await log_inference_action(
        action="started",
        user_id=current_user["id"],
        request=request,
        db=db,
        job_id=job_id,
        num_images=len(request_data.image_paths),
        details={
            "model_id": request_data.model_id,
            "generate_gradcam": request_data.generate_gradcam,
            "num_images": len(request_data.image_paths)
        },
        response_status=200,
        start_time=start_time
    )
    
    # Start Celery task
    task = run_inference_task.delay(
        job_id=job_id,
        image_paths=request_data.image_paths,
        model_id=request_data.model_id,
        generate_gradcam=request_data.generate_gradcam
    )
    
    return {
        "job_id": job_id,
        "task_id": task.id,
        "status": "pending"
    }


@app.get("/api/infer/results/{job_id}")
async def get_inference_results(
    job_id: str,
    request: Request,
    current_user: dict = Depends(require_permission("read:inference_history")),
    db: Session = Depends(get_db)
):
    """Get inference results."""
    start_time = time.time()
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get inference results
    results = db.query(InferenceResult).filter(
        InferenceResult.job_id == job_id
    ).all()
    
    # Check if this is the first time viewing completed results
    if job.status == "completed" and results:
        # Check if we already logged completion for this job
        from .database import AuditLog
        existing_completion_log = db.query(AuditLog).filter(
            AuditLog.event_type == "inference_completed",
            AuditLog.details.like(f'%"job_id": "{job_id}"%')
        ).first()
        
        if not existing_completion_log:
            # First time viewing completed results - log completion
            await log_inference_action(
                action="completed",
                user_id=current_user["id"],
                request=request,
                db=db,
                job_id=job_id,
                num_images=len(results),
                details={
                    "num_predictions": len(results),
                    "duration_seconds": (job.completed_at - job.started_at).total_seconds() if job.completed_at and job.started_at else None,
                    "first_view": True
                },
                response_status=200,
                start_time=start_time
            )
        else:
            # Subsequent viewing - log as results viewed
            await log_inference_action(
                action="results_viewed",
                user_id=current_user["id"],
                request=request,
                db=db,
                job_id=job_id,
                num_images=len(results),
                details={
                    "job_status": job.status,
                    "num_results": len(results),
                    "subsequent_view": True
                },
                response_status=200,
                start_time=start_time
            )
    else:
        # Job not completed or no results - log as results viewed
        await log_inference_action(
            action="results_viewed",
            user_id=current_user["id"],
            request=request,
            db=db,
            job_id=job_id,
            num_images=len(results),
            details={
                "job_status": job.status,
                "num_results": len(results)
            },
            response_status=200,
            start_time=start_time
        )
    
    return {
        "job_id": job_id,
        "status": job.status,
        "results": [
            {
                "result_id": r.result_id,
                "image_path": r.image_path,
                "predicted_class": r.predicted_class,
                "confidence": r.confidence,
                "probabilities": r.probabilities,
                "gradcam_path": r.gradcam_path
            }
            for r in results
        ]
    }


@app.get("/api/infer/image")
@app.head("/api/infer/image")
def serve_image(
    path: str
):
    """
    Serve an image file for viewing in UI.
    
    Security: Only serves images from allowed directories.
    Note: Made public for UI image display compatibility.
    """
    # Security: restrict to allowed directories
    allowed_dirs = [
        "/storage/datasets",
        "/storage/results",
        "/hospital_data",
        "/mnt/radiology"
    ]
    
    # Check if path is in allowed directories
    if not any(path.startswith(allowed) for allowed in allowed_dirs):
        raise HTTPException(
            status_code=403,
            detail=f"Access to path '{path}' is not allowed"
        )
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail="Path is not a file")
    
    # Determine content type based on file extension
    content_type, _ = mimetypes.guess_type(path)
    if not content_type:
        content_type = "application/octet-stream"
    
    return FileResponse(
        path,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )


# ============================================================================
# Federated Learning Endpoints
# ============================================================================


@app.post("/api/federated/participation")
async def set_participation(
    ready: bool,
    request: Request,
    current_user: dict = Depends(require_role_exact("admin_spital")),
    db: Session = Depends(get_db),
):
    """
    Set this node's readiness for federated learning.

    Only admin_spital can call this endpoint. The state is persisted in the
    database and can be read back via GET /api/federated/participation.

    Args:
        ready: True = node is ready to participate; False = node opts out
    """
    record = db.query(NodeParticipation).filter(
        NodeParticipation.node_id == settings.NODE_ID
    ).first()

    if record is None:
        record = NodeParticipation(
            node_id=settings.NODE_ID,
            is_ready=ready,
            updated_by=current_user["id"],
        )
        db.add(record)
    else:
        record.is_ready = ready
        record.updated_at = datetime.utcnow()
        record.updated_by = current_user["id"]

    db.commit()

    await security_manager.log_audit_event(
        event_type="federated_participation_changed",
        user_id=current_user["id"],
        request=request,
        additional_data={"is_ready": ready, "node_id": settings.NODE_ID},
        db=db,
        response_status=200,
    )

    return {
        "node_id": settings.NODE_ID,
        "is_ready": ready,
        "updated_at": record.updated_at.isoformat(),
    }


@app.get("/api/federated/participation")
def get_participation(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get this node's current readiness state for federated learning.

    Readable by any authenticated user.
    """
    record = db.query(NodeParticipation).filter(
        NodeParticipation.node_id == settings.NODE_ID
    ).first()

    is_ready = record.is_ready if record is not None else False
    updated_at = record.updated_at.isoformat() if record is not None else None

    return {
        "node_id": settings.NODE_ID,
        "is_ready": is_ready,
        "updated_at": updated_at,
    }


@app.post("/api/federated/train", response_model=JobCreateResponse)
async def start_federated_training(
    dataset_id: str,
    model_name: str = "efficientnet_b0",
    batch_size: int = 32,
    splits_dir: str = None,
    request: Request = None,
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(require_role_exact("admin_central")),
    db: Session = Depends(get_db)
):
    """
    Start federated training.

    Creates a Celery task for FL training. The job_id serves as the unique
    session identifier for tracking purposes.

    Args:
        dataset_id: Dataset to use for training
        model_name: Model architecture (resnet18, densenet121, efficientnet_b0)
        batch_size: Batch size for training on this node
        splits_dir: Opțional — directorul cu split-urile fixe CSV (experiments/splits/).
                    Dacă e furnizat, se folosesc split-urile fixe în loc de random_split.
    """
    start_time = time.time()
    from .tasks import federated_training_task

    job_id = f"fl_{uuid.uuid4().hex[:8]}"

    job = Job(
        job_id=job_id,
        job_type="federated_train",
        status="pending",
        params={"dataset_id": dataset_id, "model_name": model_name, "batch_size": batch_size}
    )
    db.add(job)
    db.commit()

    await log_federated_action(
        action="training_started",
        user_id=current_user["id"],
        request=request,
        db=db,
        session_id=job_id,
        details={
            "job_id": job_id,
            "dataset_id": dataset_id,
            "model_name": model_name,
            "batch_size": batch_size,
            "node_id": settings.NODE_ID
        },
        response_status=200,
        start_time=start_time
    )

    task = federated_training_task.delay(
        job_id=job_id,
        dataset_id=dataset_id,
        model_name=model_name,
        batch_size=batch_size,
        splits_dir=splits_dir,
    )

    return {
        "job_id": job_id,
        "task_id": task.id,
        "status": "pending",
    }


@app.get("/api/federated/status/{job_id}", response_model=FederatedStatusResponse)
def get_federated_status(
    job_id: str,
    current_user: dict = Depends(require_permission("read:federated")),
    db: Session = Depends(get_db)
):
    """Get federated learning status for a session by job_id."""
    job = db.query(Job).filter(
        Job.job_id == job_id,
        Job.job_type == "federated_train"
    ).first()

    if job:
        local_status = job.status
    else:
        local_status = "not_started"

    return {
        "session_id": job_id,
        "node_id": settings.NODE_ID,
        "status": local_status,
        "job_id": job_id,
        "local_status": local_status,
        "central_status": {
            "note": "Using Flower framework - check Flower server logs for round status"
        }
    }


@app.get("/api/federated/history")
def get_federated_history(
    current_user: dict = Depends(require_permission("read:federated")),
    db: Session = Depends(get_db)
):
    """
    Get history of all federated learning sessions this node participated in.

    Each job is its own session, identified by job_id.
    Returns sessions sorted by most recent first, active sessions at the top.
    """
    jobs = db.query(Job).filter(
        Job.job_type == "federated_train"
    ).order_by(Job.created_at.desc()).all()

    sessions = []
    for job in jobs:
        # Get model linked to this job
        model = db.query(Model).filter(
            Model.session_id == job.job_id
        ).order_by(Model.created_at.desc()).first()

        is_active = job.status in ["pending", "running"]

        dataset_id = job.params.get("dataset_id") if job.params else None
        dataset_name = None
        if job.result:
            dataset_name = job.result.get("dataset_name")

        metrics = job.result.get("metrics") if job.result else None

        sessions.append({
            "session_id": job.job_id,
            "is_active": is_active,
            "local_status": job.status,
            "job_id": job.job_id,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "model_id": model.model_id if model else None,
            "model_type": model.type if model else None,
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "metrics": metrics,
            "central_status": {
                "note": "Using Flower framework - check Flower server logs for session status"
            }
        })

    # Active sessions first, then by created_at descending
    sessions.sort(key=lambda x: (not x["is_active"], x["created_at"] or ""), reverse=True)

    return {
        "total_rounds": len(sessions),
        "rounds": sessions
    }


# ============================================================================
# Observability & Management Endpoints
# ============================================================================

@app.get("/api/jobs/list")
def list_jobs(
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(require_permission("read:jobs")),
    db: Session = Depends(get_db)
):
    """
    List all jobs with filtering and pagination.
    
    Args:
        status: Filter by status (pending, running, completed, failed)
        job_type: Filter by type (train, infer, federated_train)
        limit: Maximum number of jobs to return
    
    Returns:
        List of jobs with details
    """
    query = db.query(Job)
    
    if status:
        query = query.filter(Job.status == status)
    
    if job_type:
        query = query.filter(Job.job_type == job_type)
    
    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()
    
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": j.job_id,
                "job_type": j.job_type,
                "status": j.status,
                "params": j.params,
                "result": j.result,
                "error": j.error,
                "created_at": j.created_at.isoformat(),
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "duration": (j.completed_at - j.started_at).total_seconds() if j.completed_at and j.started_at else None
            }
            for j in jobs
        ]
    }


@app.get("/api/jobs/{job_id}/status")
async def get_job_status(
    job_id: str,
    request: Request,
    current_user: dict = Depends(require_permission("read:jobs")),
    db: Session = Depends(get_db)
):
    """
    Get detailed status of a specific job.
    
    Returns:
        Detailed job information including Celery task status
    """
    start_time = time.time()
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Log job status view
    await log_job_action(
        action="viewed",
        user_id=current_user["id"],
        request=request,
        db=db,
        job_id=job_id,
        job_type=job.job_type,
        details={
            "status": job.status
        },
        response_status=200,
        start_time=start_time
    )
    
    # Try to get Celery task status if available
    celery_status = None
    try:
        from celery.result import AsyncResult
        from .tasks import celery_app
        
        # Find task_id from job params or result
        task_id = job.params.get("task_id") if job.params else None
        
        if task_id:
            task_result = AsyncResult(task_id, app=celery_app)
            celery_status = {
                "task_id": task_id,
                "state": task_result.state,
                "info": str(task_result.info) if task_result.info else None
            }
    except Exception as e:
        celery_status = {"error": str(e)}
    
    return {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "status": job.status,
        "params": job.params,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "duration": (job.completed_at - job.started_at).total_seconds() if job.completed_at and job.started_at else None,
        "celery_status": celery_status
    }


@app.get("/api/jobs/{job_id}/logs")
async def stream_job_logs(
    job_id: str,
    current_user: dict = Depends(require_permission("read:jobs")),
    db: Session = Depends(get_db)
):
    """
    Stream job logs in real-time using Server-Sent Events (SSE).
    
    For containerized deployment, this returns job status updates instead of worker logs.
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def log_generator():
        """
        Generate job status events for SSE streaming.
        
        Since we cannot access Docker logs from inside the container,
        we provide job status updates instead.
        """
        # Send initial status
        yield f"data: {json.dumps({'type': 'status', 'status': job.status, 'job_id': job_id})}\n\n"
        
        # Send job information
        yield f"data: {json.dumps({'type': 'info', 'message': f'Job {job_id} ({job.job_type}) - Status: {job.status}'})}\n\n"
        
        if job.created_at:
            yield f"data: {json.dumps({'type': 'log', 'timestamp': job.created_at.isoformat(), 'message': f'Job created at {job.created_at.isoformat()}'})}\n\n"
        
        if job.started_at:
            yield f"data: {json.dumps({'type': 'log', 'timestamp': job.started_at.isoformat(), 'message': f'Job started at {job.started_at.isoformat()}'})}\n\n"
        
        if job.completed_at:
            yield f"data: {json.dumps({'type': 'log', 'timestamp': job.completed_at.isoformat(), 'message': f'Job completed at {job.completed_at.isoformat()}'})}\n\n"
            
            if job.status == "completed" and job.result:
                yield f"data: {json.dumps({'type': 'log', 'timestamp': job.completed_at.isoformat(), 'message': f'Result: {str(job.result)[:200]}...'})}\n\n"
            elif job.status == "failed" and job.error:
                yield f"data: {json.dumps({'type': 'log', 'timestamp': job.completed_at.isoformat(), 'message': f'Error: {job.error}'})}\n\n"
        
        # Send note about detailed logs
        yield f"data: {json.dumps({'type': 'info', 'message': 'For detailed worker logs, use: docker logs diploma_project_fed_fl_med-node1-worker-1'})}\n\n"
        
        # Monitor job status changes for a short period
        for i in range(30):  # Monitor for 30 seconds
            await asyncio.sleep(1)
            
            # Refresh job from database
            db.refresh(job)
            
            # If job status changed, send update
            current_status = job.status
            yield f"data: {json.dumps({'type': 'status', 'status': current_status, 'job_id': job_id})}\n\n"
            
            # If job completed, send final status and close
            if current_status in ['completed', 'failed']:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
        
        # Send final done message
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.get("/api/jobs/{job_id}/logs/static")
def get_job_logs_static(
    job_id: str,
    lines: int = 100,
    current_user: dict = Depends(require_permission("read:jobs")),
    db: Session = Depends(get_db)
):
    """
    Get static snapshot of job logs (non-streaming).
    
    Useful for completed jobs or when streaming is not needed.
    
    Args:
        job_id: Job identifier
        lines: Number of log lines to return (default 100)
    
    Returns:
        List of log lines
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if this is a federated training job with saved logs
    log_file = Path(settings.STORAGE_ROOT) / "logs" / f"federated_train_{job_id}.log"
    if job.job_type == "federated_train" and log_file.exists():
        try:
            # Read logs from file
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
            
            # Get last N lines
            log_lines = []
            for line in all_lines[-lines:]:
                log_lines.append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'message': line.strip()
                })
            
            return {
                "job_id": job_id,
                "status": job.status,
                "total_lines": len(log_lines),
                "logs": log_lines,
                "source": "file"
            }
        except Exception as e:
            # Fall through to mock logs if file read fails
            pass
    
    # For containerized deployment, we cannot access Docker logs from inside the API container
    # Return job information and status instead
    mock_logs = []
    
    if job.status == "pending":
        mock_logs.append({
            'timestamp': job.created_at.isoformat(),
            'message': f"Job {job_id} created and queued for execution"
        })
        mock_logs.append({
            'timestamp': datetime.utcnow().isoformat(),
            'message': f"Job status: {job.status} - waiting for worker to pick up the task"
        })
    elif job.status == "running":
        mock_logs.append({
            'timestamp': job.created_at.isoformat(),
            'message': f"Job {job_id} created"
        })
        if job.started_at:
            mock_logs.append({
                'timestamp': job.started_at.isoformat(),
                'message': f"Job {job_id} started execution"
            })
        mock_logs.append({
            'timestamp': datetime.utcnow().isoformat(),
            'message': f"Job status: {job.status} - currently executing"
        })
    elif job.status == "completed":
        mock_logs.append({
            'timestamp': job.created_at.isoformat(),
            'message': f"Job {job_id} created"
        })
        if job.started_at:
            mock_logs.append({
                'timestamp': job.started_at.isoformat(),
                'message': f"Job {job_id} started execution"
            })
        if job.completed_at:
            mock_logs.append({
                'timestamp': job.completed_at.isoformat(),
                'message': f"Job {job_id} completed successfully"
            })
            duration = (job.completed_at - job.started_at).total_seconds() if job.started_at else 0
            mock_logs.append({
                'timestamp': job.completed_at.isoformat(),
                'message': f"Execution time: {duration:.2f} seconds"
            })
        if job.result:
            mock_logs.append({
                'timestamp': job.completed_at.isoformat() if job.completed_at else datetime.utcnow().isoformat(),
                'message': f"Result: {str(job.result)[:200]}..."
            })
    elif job.status == "failed":
        mock_logs.append({
            'timestamp': job.created_at.isoformat(),
            'message': f"Job {job_id} created"
        })
        if job.started_at:
            mock_logs.append({
                'timestamp': job.started_at.isoformat(),
                'message': f"Job {job_id} started execution"
            })
        if job.completed_at:
            mock_logs.append({
                'timestamp': job.completed_at.isoformat(),
                'message': f"Job {job_id} failed"
            })
        if job.error:
            mock_logs.append({
                'timestamp': job.completed_at.isoformat() if job.completed_at else datetime.utcnow().isoformat(),
                'message': f"Error: {job.error}"
            })
    
    return {
        "job_id": job_id,
        "status": job.status,
        "total_lines": len(mock_logs),
        "logs": mock_logs,
        "source": "job_status",
        "note": "Detailed worker logs are available in the worker container. Use 'docker logs diploma_project_fed_fl_med-node1-worker-1' to view them."
    }


if __name__ == "__main__":
    import uvicorn
    import sys
    
    # Add node_core to path
    sys.path.insert(0, '/app/shared/python/node_core')
    
    from node_core import configure_fastapi_ssl, get_uvicorn_config
    
    # Check if SSL should be enabled
    enable_ssl = os.getenv("ENABLE_SSL", "true").lower() == "true"
    certificates_path = os.getenv("CERTIFICATES_PATH", "/certificates")
    
    ssl_config = None
    if enable_ssl:
        print(f"\n{'='*70}")
        print(f"CONFIGURING HTTPS FOR NODE API - {settings.NODE_ID}")
        print(f"{'='*70}")
        
        # Configure SSL
        ssl_config = configure_fastapi_ssl(
            app=app,
            node_id=settings.NODE_ID,
            is_central=False,
            certificates_path=certificates_path,
            require_client_cert=False,  # Optional: enable for mTLS
            enforce_client_cert=False
        )
        
        if ssl_config:
            print(f"✓ HTTPS enabled for {settings.NODE_ID}")
        else:
            print(f"⚠️  HTTPS configuration failed, falling back to HTTP")
        
        print(f"{'='*70}\n")
    
    # Get Uvicorn configuration
    uvicorn_config = get_uvicorn_config(
        ssl_config=ssl_config,
        host=settings.API_HOST,
        port=settings.API_PORT
    )
    
    # Start server
    uvicorn.run(app, **uvicorn_config)


from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import os
import uuid
import shutil
import asyncio
import json

from .config import settings
from .database import get_db, Model, Job, Dataset, InferenceResult
from .schemas import (
    ModelInfo, ModelPromoteRequest, ModelListResponse,
    JobInfo, JobCreateResponse,
    TrainRequest, InferRequest, InferResponse,
    FederatedJoinRequest, FederatedStatusResponse,
    DatasetInfo, DatasetUploadResponse, DatasetRegisterRequest,
    HealthResponse, NodeStatusResponse
)

app = FastAPI(
    title=f"Node API - {settings.NODE_ID}",
    version="0.1.0",
    description="Hospital Node API for Federated Learning Medical Imaging"
)

# CORS middleware - Allow requests from UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:3000",  # Dev mode
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/api/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return {
        "ok": True,
        "node_id": settings.NODE_ID,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/node/status", response_model=NodeStatusResponse)
def node_status(db: Session = Depends(get_db)):
    """Get node status and statistics."""
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
    
    return {
        "node_id": settings.NODE_ID,
        "storage_root": settings.STORAGE_ROOT,
        "central_url": settings.CENTRAL_URL,
        "device": settings.DEVICE,
        "models": models_count,
        "jobs": jobs_count,
        "datasets": datasets_count
    }


# ============================================================================
# Dataset Management Endpoints
# ============================================================================

@app.get("/api/data/browse")
def browse_filesystem(
    directory: str = None,
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
                # Check if it looks like a dataset (has NORMAL/PNEUMONIA folders)
                is_dataset = (
                    os.path.exists(os.path.join(item_path, "NORMAL")) and
                    os.path.exists(os.path.join(item_path, "PNEUMONIA"))
                )
                
                # Count samples if it's a dataset
                num_samples = 0
                num_normal = 0
                num_pneumonia = 0
                
                if is_dataset:
                    normal_path = os.path.join(item_path, "NORMAL")
                    pneumonia_path = os.path.join(item_path, "PNEUMONIA")
                    num_normal = len([f for f in os.listdir(normal_path) if os.path.isfile(os.path.join(normal_path, f))])
                    num_pneumonia = len([f for f in os.listdir(pneumonia_path) if os.path.isfile(os.path.join(pneumonia_path, f))])
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
def register_dataset(
    request: DatasetRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register an existing dataset from filesystem.
    
    Instead of uploading, this registers a dataset that already exists
    on the hospital system (on-premise data).
    
    Args:
        request: DatasetRegisterRequest with path, name, and split
    
    Returns:
        Dataset information
    """
    # Validate path exists
    if not os.path.exists(request.path):
        raise HTTPException(
            status_code=404,
            detail=f"Dataset path not found: {request.path}"
        )
    
    if not os.path.isdir(request.path):
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a directory: {request.path}"
        )
    
    # Validate dataset structure (must have split/NORMAL and split/PNEUMONIA folders)
    # The path should be the base directory, and we check for {path}/{split}/NORMAL and {path}/{split}/PNEUMONIA
    split_path = os.path.join(request.path, request.split)
    
    if not os.path.exists(split_path):
        raise HTTPException(
            status_code=400,
            detail=f"Split directory not found: {split_path}"
        )
    
    normal_path = os.path.join(split_path, "NORMAL")
    pneumonia_path = os.path.join(split_path, "PNEUMONIA")
    
    if not os.path.exists(normal_path):
        raise HTTPException(
            status_code=400,
            detail=f"Dataset must contain NORMAL folder at {normal_path}"
        )
    
    if not os.path.exists(pneumonia_path):
        raise HTTPException(
            status_code=400,
            detail=f"Dataset must contain PNEUMONIA folder at {pneumonia_path}"
        )
    
    # Count samples
    num_normal = len([f for f in os.listdir(normal_path) if os.path.isfile(os.path.join(normal_path, f))])
    num_pneumonia = len([f for f in os.listdir(pneumonia_path) if os.path.isfile(os.path.join(pneumonia_path, f))])
    num_samples = num_normal + num_pneumonia
    
    # Check if dataset already registered
    existing = db.query(Dataset).filter(Dataset.path == request.path).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Dataset already registered with ID: {existing.dataset_id}"
        )
    
    # Generate dataset ID
    dataset_id = f"dataset_{request.split}_{uuid.uuid4().hex[:8]}"
    
    # Save to database
    dataset = Dataset(
        dataset_id=dataset_id,
        name=request.name,
        path=request.path,
        split=request.split,
        num_samples=num_samples,
        num_normal=num_normal,
        num_pneumonia=num_pneumonia
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    
    return {
        "dataset_id": dataset_id,
        "name": request.name,
        "path": request.path,
        "split": request.split,
        "num_samples": num_samples,
        "num_normal": num_normal,
        "num_pneumonia": num_pneumonia,
        "created_at": dataset.created_at.isoformat()
    }


@app.get("/api/data/list", response_model=List[DatasetInfo])
def list_datasets(db: Session = Depends(get_db)):
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
def set_active_dataset(dataset_id: str, db: Session = Depends(get_db)):
    """
    Set a dataset as active for training.
    
    The active dataset will be used by default in training operations.
    """
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Deactivate all other datasets
    db.query(Dataset).update({"is_active": False})
    
    # Activate selected dataset
    dataset.is_active = True
    db.commit()
    
    return {
        "status": "success",
        "dataset_id": dataset_id,
        "message": f"Dataset {dataset.name} set as active"
    }


@app.get("/api/data/active")
def get_active_dataset(db: Session = Depends(get_db)):
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
def delete_dataset(dataset_id: str, db: Session = Depends(get_db)):
    """
    Unregister a dataset.
    
    Note: This only removes the dataset from the registry,
    it does NOT delete the actual files (on-premise data is preserved).
    """
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
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
    Compute labels for models based on accuracy and deployed status.
    
    Labels:
    - "active": deployed model (used for inference)
    - "global": best model (highest accuracy)
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
    
    # Find best model (highest accuracy) - include all models
    best_model_id = None
    best_accuracy = -1
    for m in models_list:
        if m.metrics and "accuracy" in m.metrics:
            acc = m.metrics["accuracy"]
            if acc > best_accuracy:
                best_accuracy = acc
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
    db: Session = Depends(get_db)
):
    """List models in registry with computed labels."""
    query = db.query(Model)
    
    if type:
        query = query.filter(Model.type == type)
    
    models = query.order_by(Model.created_at.desc()).all()
    
    # Compute labels for all models
    models = compute_model_labels(models, db)
    
    return {
        "models": [
            {
                "model_id": m.model_id,
                "model_name": m.model_name,
                "version": m.version,
                "type": m.type,  # Keep for backward compatibility
                "labels": m.labels or [],
                "round_id": m.round_id,
                "metrics": m.metrics,
                "created_at": m.created_at.isoformat()
            }
            for m in models
        ]
    }


@app.post("/api/models/promote")
def promote_model(
    request: ModelPromoteRequest,
    db: Session = Depends(get_db)
):
    """
    Promote model to deployed (active).
    
    - Changes current deployed model back to candidate
    - Promotes selected model to deployed
    - Recalculates labels for all models
    """
    # Get model to promote
    model_to_promote = db.query(Model).filter(
        Model.model_id == request.model_id
    ).first()
    
    if not model_to_promote:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Change current deployed model back to candidate
    current_deployed = db.query(Model).filter(
        Model.type == "deployed",
        Model.model_name == model_to_promote.model_name
    ).first()
    
    if current_deployed:
        current_deployed.type = "candidate"
        
        # Move file back to candidate directory
        old_path = current_deployed.file_path
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
    new_path = old_path.replace("/candidate/", "/deployed/")
    if os.path.exists(old_path):
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(old_path, new_path)
        model_to_promote.file_path = new_path
    
    db.commit()
    
    # Recalculate labels for all models
    all_models = db.query(Model).all()
    compute_model_labels(all_models, db)
    
    return {
        "status": "success",
        "model_id": model_to_promote.model_id,
        "message": f"Model {model_to_promote.model_id} promoted to active"
    }


@app.get("/api/models/{model_id}")
def get_model_info(model_id: str, db: Session = Depends(get_db)):
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
        "round_id": model.round_id,
        "base_model_hash": model.base_model_hash,
        "file_path": model.file_path,
        "metrics": model.metrics,
        "created_at": model.created_at.isoformat()
    }


# ============================================================================
# Training Endpoints
# ============================================================================

@app.post("/api/train/local", response_model=JobCreateResponse)
async def start_local_training(
    request: TrainRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start local training job.
    
    Creates a Celery task for training.
    """
    from .tasks import train_local_model_task
    
    # Create job record
    job_id = f"train_{uuid.uuid4().hex[:8]}"
    
    job = Job(
        job_id=job_id,
        job_type="train",
        status="pending",
        params=request.dict()
    )
    db.add(job)
    db.commit()
    
    # Start Celery task
    task = train_local_model_task.delay(
        job_id=job_id,
        dataset_id=request.dataset_id,
        model_name=request.model_name,
        num_epochs=request.num_epochs,
        batch_size=request.batch_size,
        learning_rate=request.learning_rate
    )
    
    return {
        "job_id": job_id,
        "task_id": task.id,
        "status": "pending"
    }


@app.get("/api/train/status/{job_id}")
def get_training_status(job_id: str, db: Session = Depends(get_db)):
    """Get training job status."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "params": job.params,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }


# ============================================================================
# Inference Endpoints
# ============================================================================

@app.get("/api/infer/browse")
def browse_hospital_images(
    directory: str = "/hospital_data",
    db: Session = Depends(get_db)
):
    """
    Browse available images in hospital data directories.
    
    This helps UI users select images without uploading them.
    Images remain in their original location (on-premise security).
    
    Args:
        directory: Path to directory to browse (must be in allowed list)
    
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
        for item in os.listdir(directory):
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
        "total_subdirs": len(subdirs)
    }


@app.post("/api/infer", response_model=InferResponse)
async def run_inference(
    request: InferRequest,
    background_tasks: BackgroundTasks,
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
        request: InferRequest with image_paths, model_id, generate_gradcam
    
    Returns:
        Job information (job_id, task_id, status)
    """
    from .tasks import run_inference_task
    
    # Validate that all image paths exist and are readable
    for path in request.image_paths:
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
        params=request.dict()
    )
    db.add(job)
    db.commit()
    
    # Start Celery task
    task = run_inference_task.delay(
        job_id=job_id,
        image_paths=request.image_paths,
        model_id=request.model_id,
        generate_gradcam=request.generate_gradcam
    )
    
    return {
        "job_id": job_id,
        "task_id": task.id,
        "status": "pending"
    }


@app.get("/api/infer/results/{job_id}")
def get_inference_results(job_id: str, db: Session = Depends(get_db)):
    """Get inference results."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get inference results
    results = db.query(InferenceResult).filter(
        InferenceResult.job_id == job_id
    ).all()
    
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
def serve_image(path: str):
    """
    Serve an image file for viewing in UI.
    
    Security: Only serves images from allowed directories.
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
    
    return FileResponse(path)


# ============================================================================
# Federated Learning Endpoints
# ============================================================================

@app.post("/api/federated/join/{round_id}")
async def join_federated_round(
    round_id: str,
    request: FederatedJoinRequest,
    db: Session = Depends(get_db)
):
    """
    Join a federated learning round.
    
    With Flower, this is informational only - the actual connection
    happens when the Flower client starts.
    """
    # Just log the intent to join
    print(f"[{settings.NODE_ID}] Node will join round {round_id} when training starts")
    
    return {
        "status": "success",
        "round_id": round_id,
        "node_id": settings.NODE_ID,
        "message": f"Node {settings.NODE_ID} will join round {round_id}",
        "note": "Using Flower framework - connection happens during training"
    }


@app.post("/api/federated/train/{round_id}", response_model=JobCreateResponse)
async def start_federated_training(
    round_id: str,
    dataset_id: str,
    model_name: str = "efficientnet_b0",
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Start federated training for a round.
    
    Creates a Celery task for FL training.
    
    Args:
        round_id: FL round identifier
        dataset_id: Dataset to use for training
        model_name: Model architecture (resnet18, densenet121, efficientnet_b0)
    """
    from .tasks import federated_training_task
    
    # Create job record
    job_id = f"fl_train_{round_id}_{uuid.uuid4().hex[:8]}"
    
    job = Job(
        job_id=job_id,
        job_type="federated_train",
        status="pending",
        params={"round_id": round_id, "dataset_id": dataset_id, "model_name": model_name}
    )
    db.add(job)
    db.commit()
    
    # Start Celery task
    task = federated_training_task.delay(
        job_id=job_id,
        round_id=round_id,
        dataset_id=dataset_id,
        model_name=model_name
    )
    
    return {
        "job_id": job_id,
        "task_id": task.id,
        "status": "pending"
    }


@app.get("/api/federated/status/{round_id}", response_model=FederatedStatusResponse)
def get_federated_status(round_id: str, db: Session = Depends(get_db)):
    """
    Get federated learning status for a round.
    
    With Flower, we check local job status only.
    """
    # Get local job status
    job = db.query(Job).filter(
        Job.job_type == "federated_train",
        Job.params["round_id"].astext == round_id
    ).order_by(Job.created_at.desc()).first()
    
    local_status = job.status if job else "not_started"
    
    return {
        "round_id": round_id,
        "node_id": settings.NODE_ID,
        "local_status": local_status,
        "central_status": {
            "note": "Using Flower framework - check Flower server logs for round status"
        }
    }


@app.get("/api/federated/history")
def get_federated_history(db: Session = Depends(get_db)):
    """
    Get history of all federated learning rounds this node participated in.
    
    Returns rounds sorted by most recent first, with active rounds at the top.
    """
    import requests
    
    # Get all FL training jobs from database
    jobs = db.query(Job).filter(
        Job.job_type == "federated_train"
    ).order_by(Job.created_at.desc()).all()
    
    # Get unique round IDs
    round_ids = list(set([job.params.get("round_id") for job in jobs if job.params.get("round_id")]))
    
    # Fetch status for each round from central server
    rounds_history = []
    
    for round_id in round_ids:
        try:
            # Get central server status
            response = requests.get(
                f"{settings.CENTRAL_URL}/round/{round_id}/status",
                timeout=5
            )
            
            if response.ok:
                central_status = response.json()
            else:
                central_status = None
        except:
            central_status = None
        
        # Get local jobs for this round
        round_jobs = [j for j in jobs if j.params.get("round_id") == round_id]
        latest_job = round_jobs[0] if round_jobs else None
        
        # Get model info if exists
        model = db.query(Model).filter(
            Model.round_id == round_id
        ).order_by(Model.created_at.desc()).first()
        
        # Determine if round is active
        is_active = False
        if central_status:
            central_round_status = central_status.get("status", "")
            is_active = central_round_status in ["created", "training", "collecting"]
        
        # Extract dataset info from job result or params
        dataset_id = None
        dataset_name = None
        if latest_job and latest_job.result:
            dataset_id = latest_job.result.get("dataset_id")
            dataset_name = latest_job.result.get("dataset_name")
        if not dataset_id and latest_job:
            dataset_id = latest_job.params.get("dataset_id")
        
        # Extract metrics from job result
        metrics = None
        if latest_job and latest_job.result:
            metrics = latest_job.result.get("metrics")
        
        # Build round info
        round_info = {
            "round_id": round_id,
            "is_active": is_active,
            "local_status": latest_job.status if latest_job else "not_started",
            "job_id": latest_job.job_id if latest_job else None,
            "created_at": latest_job.created_at.isoformat() if latest_job else None,
            "completed_at": latest_job.completed_at.isoformat() if latest_job and latest_job.completed_at else None,
            "model_id": model.model_id if model else None,
            "model_type": model.type if model else None,
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "metrics": metrics,
            "central_status": central_status
        }
        
        rounds_history.append(round_info)
    
    # Sort: active rounds first, then by created_at descending
    rounds_history.sort(key=lambda x: (not x["is_active"], x["created_at"] or ""), reverse=True)
    
    return {
        "total_rounds": len(rounds_history),
        "rounds": rounds_history
    }


# ============================================================================
# Observability & Management Endpoints
# ============================================================================

@app.get("/api/jobs/list")
def list_jobs(
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 50,
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
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Get detailed status of a specific job.
    
    Returns:
        Detailed job information including Celery task status
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
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
async def stream_job_logs(job_id: str, db: Session = Depends(get_db)):
    """
    Stream job logs in real-time using Server-Sent Events (SSE).
    
    This endpoint streams logs from the Celery worker for the specified job.
    The client should use EventSource to receive updates.
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def log_generator():
        """
        Generate log events for SSE streaming.
        
        This reads logs from:
        1. Docker container logs (filtered by job_id)
        2. Job status updates from database
        """
        import subprocess
        import re
        
        # Send initial status
        yield f"data: {json.dumps({'type': 'status', 'status': job.status, 'job_id': job_id})}\n\n"
        
        # Get worker container name
        worker_container = f"diploma_project_fed_fl_med-{settings.NODE_ID}-worker-1"
        
        try:
            # Stream logs from Docker container
            # Use --since to only get new logs (not historical ones already loaded)
            # Get logs from the last 10 seconds to avoid missing anything
            process = subprocess.Popen(
                ["docker", "logs", "-f", "--since", "10s", worker_container],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Track seen log lines to avoid duplicates
            seen_logs = set()
            
            # Filter logs related to this job
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                
                # Check if line contains job_id (strict filtering)
                if job_id in line:
                    line_stripped = line.strip()
                    
                    # Skip if we've already sent this exact log line
                    if line_stripped in seen_logs:
                        continue
                    
                    seen_logs.add(line_stripped)
                    
                    # Clean and format log line
                    log_entry = {
                        'type': 'log',
                        'timestamp': datetime.utcnow().isoformat(),
                        'message': line_stripped
                    }
                    yield f"data: {json.dumps(log_entry)}\n\n"
                
                # Check job status periodically
                await asyncio.sleep(0.1)
                
                # Refresh job from database
                db.refresh(job)
                
                # If job completed, send final status and close
                if job.status in ['completed', 'failed']:
                    yield f"data: {json.dumps({'type': 'status', 'status': job.status, 'result': job.result, 'error': job.error})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break
            
            process.terminate()
            
        except Exception as e:
            error_msg = {
                'type': 'error',
                'message': f"Error streaming logs: {str(e)}"
            }
            yield f"data: {json.dumps(error_msg)}\n\n"
    
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
def get_job_logs_static(job_id: str, lines: int = 100, db: Session = Depends(get_db)):
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
            # Fall through to Docker logs if file read fails
            pass
    
    import subprocess
    
    # Get worker container name
    worker_container = f"diploma_project_fed_fl_med-{settings.NODE_ID}-worker-1"
    
    try:
        # Get logs from Docker container
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), worker_container],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Combine stdout and stderr
        all_logs = result.stdout + result.stderr
        
        # Filter logs related to this job (only by job_id)
        log_lines = []
        for line in all_logs.split('\n'):
            if job_id in line:
                log_lines.append({
                    'timestamp': datetime.utcnow().isoformat(),
                    'message': line.strip()
                })
        
        return {
            "job_id": job_id,
            "status": job.status,
            "total_lines": len(log_lines),
            "logs": log_lines,
            "source": "docker"
        }
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout fetching logs")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching logs: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import os
import uuid
import shutil

from .config import settings
from .database import get_db, Model, Job, Dataset, InferenceResult
from .schemas import (
    ModelInfo, ModelPromoteRequest, ModelListResponse,
    JobInfo, JobCreateResponse,
    TrainRequest, InferRequest, InferResponse,
    FederatedJoinRequest, FederatedStatusResponse,
    DatasetInfo, DatasetUploadResponse,
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

@app.post("/api/data/upload", response_model=DatasetUploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    split: str = "train",
    db: Session = Depends(get_db)
):
    """
    Upload dataset (ZIP file with NORMAL/PNEUMONIA folders).
    
    Expected structure:
        dataset.zip
        ├── NORMAL/
        │   ├── image1.jpg
        │   └── ...
        └── PNEUMONIA/
            ├── image1.jpg
            └── ...
    """
    # Generate dataset ID
    dataset_id = f"dataset_{split}_{uuid.uuid4().hex[:8]}"
    dataset_path = os.path.join(settings.DATASETS_DIR, dataset_id)
    
    # Save uploaded file
    zip_path = f"{dataset_path}.zip"
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Extract ZIP
    import zipfile
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dataset_path)
    
    # Remove ZIP file
    os.remove(zip_path)
    
    # Count samples
    normal_path = os.path.join(dataset_path, "NORMAL")
    pneumonia_path = os.path.join(dataset_path, "PNEUMONIA")
    
    num_normal = len(os.listdir(normal_path)) if os.path.exists(normal_path) else 0
    num_pneumonia = len(os.listdir(pneumonia_path)) if os.path.exists(pneumonia_path) else 0
    num_samples = num_normal + num_pneumonia
    
    # Save to database
    dataset = Dataset(
        dataset_id=dataset_id,
        name=file.filename,
        path=dataset_path,
        split=split,
        num_samples=num_samples,
        num_normal=num_normal,
        num_pneumonia=num_pneumonia
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    
    return {
        "dataset_id": dataset_id,
        "path": dataset_path,
        "num_samples": num_samples,
        "num_normal": num_normal,
        "num_pneumonia": num_pneumonia
    }


@app.get("/api/data/list", response_model=List[DatasetInfo])
def list_datasets(db: Session = Depends(get_db)):
    """List all datasets."""
    datasets = db.query(Dataset).all()
    return [
        {
            "dataset_id": d.dataset_id,
            "name": d.name,
            "split": d.split,
            "num_samples": d.num_samples,
            "num_normal": d.num_normal,
            "num_pneumonia": d.num_pneumonia,
            "created_at": d.created_at.isoformat()
        }
        for d in datasets
    ]


# ============================================================================
# Model Registry Endpoints
# ============================================================================

@app.get("/api/models/registry", response_model=ModelListResponse)
def list_models(
    type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List models in registry."""
    query = db.query(Model)
    
    if type:
        query = query.filter(Model.type == type)
    
    models = query.order_by(Model.created_at.desc()).all()
    
    return {
        "models": [
            {
                "model_id": m.model_id,
                "model_name": m.model_name,
                "version": m.version,
                "type": m.type,
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
    Promote candidate model to deployed.
    
    - Archives current deployed model
    - Promotes candidate to deployed
    """
    # Get candidate model
    candidate = db.query(Model).filter(
        Model.model_id == request.model_id,
        Model.type == "candidate"
    ).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate model not found")
    
    # Archive current deployed model
    current_deployed = db.query(Model).filter(
        Model.type == "deployed",
        Model.model_name == candidate.model_name
    ).first()
    
    if current_deployed:
        current_deployed.type = "archived"
        current_deployed.archived_at = datetime.utcnow()
        
        # Move file to archived directory
        old_path = current_deployed.file_path
        new_path = old_path.replace("/candidate/", "/archived/")
        if os.path.exists(old_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)
            current_deployed.file_path = new_path
    
    # Promote candidate
    candidate.type = "deployed"
    candidate.promoted_at = datetime.utcnow()
    
    # Move file to deployed directory
    old_path = candidate.file_path
    new_path = old_path.replace("/candidate/", "/deployed/")
    if os.path.exists(old_path):
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(old_path, new_path)
        candidate.file_path = new_path
    
    db.commit()
    
    return {
        "status": "success",
        "model_id": candidate.model_id,
        "message": f"Model {candidate.model_id} promoted to deployed"
    }


@app.get("/api/models/{model_id}")
def get_model_info(model_id: str, db: Session = Depends(get_db)):
    """Get model information."""
    model = db.query(Model).filter(Model.model_id == model_id).first()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return {
        "model_id": model.model_id,
        "model_name": model.model_name,
        "version": model.version,
        "type": model.type,
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start federated training for a round.
    
    Creates a Celery task for FL training.
    """
    from .tasks import federated_training_task
    
    # Create job record
    job_id = f"fl_train_{round_id}_{uuid.uuid4().hex[:8]}"
    
    job = Job(
        job_id=job_id,
        job_type="federated_train",
        status="pending",
        params={"round_id": round_id, "dataset_id": dataset_id}
    )
    db.add(job)
    db.commit()
    
    # Start Celery task
    task = federated_training_task.delay(
        job_id=job_id,
        round_id=round_id,
        dataset_id=dataset_id
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
    from node_core import FederatedClient
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
            "metrics": latest_job.result.get("metrics") if latest_job and latest_job.result else None,
            "central_status": central_status
        }
        
        rounds_history.append(round_info)
    
    # Sort: active rounds first, then by created_at descending
    rounds_history.sort(key=lambda x: (not x["is_active"], x["created_at"] or ""), reverse=True)
    
    return {
        "total_rounds": len(rounds_history),
        "rounds": rounds_history
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)

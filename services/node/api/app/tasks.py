"""
Celery tasks for asynchronous job processing.
"""
from celery import Celery
from datetime import datetime
import os
import sys

# Add node_core to path
sys.path.insert(0, '/app/shared/python/node_core')

from node_core import (
    get_model, load_model, save_model,
    load_dataset, create_dataloaders,
    train_model, get_optimizer, get_scheduler, EarlyStopping,
    predict_batch, GradCAM, get_final_conv_layer,
    save_gradcam_overlay, compute_metrics,
    compute_model_hash
)

def get_local_now():
    """
    Get current datetime in local system timezone.
    Automatically detects the timezone from the system.
    """
    return datetime.now().astimezone()

from .config import settings
from .database import SessionLocal, Job, Model, InferenceResult
import torch
import uuid

# Initialize Celery
celery_app = Celery(
    "node-worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)


def update_job_status(job_id: str, status: str, result=None, error=None):
    """Update job status in database."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.status = status
            if status == "running" and not job.started_at:
                job.started_at = get_local_now()
            if status in ["completed", "failed"]:
                job.completed_at = get_local_now()
            if result:
                job.result = result
            if error:
                job.error = error
            db.commit()
    finally:
        db.close()


@celery_app.task(name="train_local_model")
def train_local_model_task(
    job_id: str,
    dataset_id: str,
    model_name: str = "resnet18",
    num_epochs: int = 10,
    batch_size: int = 32,
    learning_rate: float = 0.001
):
    """
    Train a model locally on node dataset.
    
    Args:
        job_id: Job identifier
        dataset_id: Dataset identifier
        model_name: Model architecture
        num_epochs: Number of training epochs
        batch_size: Batch size
        learning_rate: Learning rate
    """
    try:
        update_job_status(job_id, "running")
        
        # Get dataset path
        db = SessionLocal()
        from .database import Dataset
        dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
        db.close()
        
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")
        
        dataset_path = dataset.path
        
        # Load datasets
        print(f"[{settings.NODE_ID}] Loading dataset from {dataset_path}...")
        train_dataset = load_dataset(dataset_path, split='train')
        
        # Create validation split if needed
        from torch.utils.data import random_split
        train_size = int(0.8 * len(train_dataset))
        val_size = len(train_dataset) - train_size
        train_dataset, val_dataset = random_split(train_dataset, [train_size, val_size])
        
        # Create data loaders (num_workers=0 for Celery compatibility)
        train_loader, val_loader = create_dataloaders(
            train_dataset, val_dataset,
            batch_size=batch_size,
            num_workers=0
        )
        
        # Initialize model
        print(f"[{settings.NODE_ID}] Initializing {model_name}...")
        model = get_model(model_name, num_classes=2, pretrained=True)
        model = model.to(settings.DEVICE)
        
        # Setup training
        criterion = torch.nn.CrossEntropyLoss()
        optimizer = get_optimizer(model, 'adam', lr=learning_rate)
        scheduler = get_scheduler(optimizer, 'cosine', num_epochs=num_epochs)
        early_stopping = EarlyStopping(patience=5, mode='max')
        
        # Train
        print(f"[{settings.NODE_ID}] Starting training...")
        history = train_model(
            model=model,
            train_loader=train_loader,
            val_loader=val_loader,
            criterion=criterion,
            optimizer=optimizer,
            device=settings.DEVICE,
            num_epochs=num_epochs,
            scheduler=scheduler,
            early_stopping=early_stopping,
            verbose=True
        )
        
        # Save model as candidate
        model_id = f"{model_name}_local_{uuid.uuid4().hex[:8]}"
        model_path = os.path.join(settings.MODELS_CANDIDATE_DIR, f"{model_id}.pt")
        
        metadata = {
            'model_name': model_name,
            'epochs': history['epochs_trained'],
            'best_val_acc': history['best_val_acc'],
            'history': history
        }
        
        save_model(model, model_path, metadata)
        
        # Save to database
        db = SessionLocal()
        model_record = Model(
            model_id=model_id,
            model_name=model_name,
            version="local",
            type="candidate",
            file_path=model_path,
            metrics={
                'accuracy': history['best_val_acc'],
                'train_loss': history['train_loss'][-1],
                'val_loss': history['val_loss'][-1]
            }
        )
        db.add(model_record)
        db.commit()
        db.close()
        
        result = {
            'model_id': model_id,
            'model_path': model_path,
            'metrics': metadata
        }
        
        update_job_status(job_id, "completed", result=result)
        
        print(f"[{settings.NODE_ID}] ✓ Training completed: {model_id}")
        
        return result
        
    except Exception as e:
        print(f"[{settings.NODE_ID}] ✗ Training failed: {e}")
        update_job_status(job_id, "failed", error=str(e))
        raise


@celery_app.task(name="run_inference")
def run_inference_task(
    job_id: str,
    image_paths: list,
    model_id: str = None,
    generate_gradcam: bool = True
):
    """
    Run inference on images.
    
    Args:
        job_id: Job identifier
        image_paths: List of image paths
        model_id: Model ID (if None, uses deployed model)
        generate_gradcam: Whether to generate Grad-CAM overlays
    """
    try:
        print(f"[{job_id}] 🚀 Starting inference job")
        print(f"[{job_id}] 📊 Processing {len(image_paths)} image(s)")
        print(f"[{job_id}] 🎨 Grad-CAM visualization: {'enabled' if generate_gradcam else 'disabled'}")
        
        update_job_status(job_id, "running")
        
        # Get model
        db = SessionLocal()
        
        print(f"[{job_id}] 🔍 Looking for model...")
        if model_id:
            model_record = db.query(Model).filter(Model.model_id == model_id).first()
            print(f"[{job_id}] 📦 Using specified model: {model_id}")
        else:
            # Use deployed model
            model_record = db.query(Model).filter(Model.type == "deployed").first()
            print(f"[{job_id}] 📦 Using deployed model")
        
        if not model_record:
            raise ValueError("No model found")
        
        model_name = model_record.model_name
        model_path = model_record.file_path
        
        # Load model
        print(f"[{job_id}] 🧠 Loading model: {model_name}")
        print(f"[{job_id}] 📂 Model path: {model_path}")
        print(f"[{job_id}] 💻 Device: {settings.DEVICE}")
        model, metadata = load_model(model_name, model_path, device=settings.DEVICE)
        print(f"[{job_id}] ✓ Model loaded successfully")
        
        # Prepare images
        print(f"[{job_id}] 🖼️  Preparing images for inference...")
        from PIL import Image
        from node_core import get_val_transforms
        
        transform = get_val_transforms()
        images_tensors = []
        
        for idx, img_path in enumerate(image_paths, 1):
            print(f"[{job_id}]   └─ Loading image {idx}/{len(image_paths)}: {os.path.basename(img_path)}")
            img = Image.open(img_path).convert('RGB')
            img_tensor = transform(img)
            images_tensors.append(img_tensor)
        
        print(f"[{job_id}] ✓ All images prepared")
        
        # Run inference
        print(f"[{job_id}] 🔮 Running inference...")
        batch_tensor = torch.stack(images_tensors)
        
        pred_classes, confidences, probs = predict_batch(
            model, batch_tensor, device=settings.DEVICE
        )
        print(f"[{job_id}] ✓ Inference completed")
        
        # Generate Grad-CAM if requested
        gradcam_paths = []
        if generate_gradcam:
            print(f"[{job_id}] 🎨 Generating Grad-CAM visualizations...")
            target_layer = get_final_conv_layer(model, model_name)
            gradcam = GradCAM(model, target_layer)
            
            for i, (img_path, img_tensor) in enumerate(zip(image_paths, images_tensors)):
                print(f"[{job_id}]   └─ Generating Grad-CAM {i+1}/{len(image_paths)}")
                # Load original image to get dimensions
                img = Image.open(img_path).convert('RGB')
                import numpy as np
                img_np = np.array(img).astype(np.float32) / 255.0
                
                # Generate heatmap and resize to match original image dimensions
                heatmap, _ = gradcam.generate(img_tensor, device=settings.DEVICE)
                
                # Resize heatmap to match original image size (H, W)
                import cv2
                heatmap_resized = cv2.resize(heatmap, (img_np.shape[1], img_np.shape[0]))
                
                # Save overlay
                overlay_path = os.path.join(
                    settings.RESULTS_DIR, "inference",
                    f"{job_id}_{i}_gradcam.png"
                )
                save_gradcam_overlay(img_np, heatmap_resized, overlay_path)
                gradcam_paths.append(overlay_path)
            
            print(f"[{job_id}] ✓ Grad-CAM visualizations saved")
        else:
            gradcam_paths = [None] * len(image_paths)
        
        # Save results to database
        print(f"[{job_id}] 💾 Saving results to database...")
        results = []
        for i, (img_path, pred_cls, conf, prob) in enumerate(
            zip(image_paths, pred_classes, confidences, probs)
        ):
            result_id = f"{job_id}_{i}"
            
            # Log prediction details
            class_name = "PNEUMONIA" if pred_cls == 1 else "NORMAL"
            print(f"[{job_id}]   └─ Image {i+1}: {class_name} (confidence: {conf:.2%})")
            
            result_record = InferenceResult(
                result_id=result_id,
                job_id=job_id,
                model_id=model_record.model_id,
                image_path=img_path,
                predicted_class=pred_cls,
                confidence=conf,
                probabilities=prob.tolist(),
                gradcam_path=gradcam_paths[i]
            )
            db.add(result_record)
            
            results.append({
                'result_id': result_id,
                'predicted_class': pred_cls,
                'confidence': conf,
                'gradcam_path': gradcam_paths[i]
            })
        
        db.commit()
        db.close()
        
        print(f"[{job_id}] ✓ Results saved to database")
        
        result = {
            'num_images': len(image_paths),
            'results': results
        }
        
        update_job_status(job_id, "completed", result=result)
        
        print(f"[{job_id}] ✅ Inference job completed successfully")
        print(f"[{job_id}] 📈 Summary: {len(image_paths)} image(s) processed")
        
        return result
        
    except Exception as e:
        print(f"[{job_id}] ❌ Inference job failed: {str(e)}")
        print(f"[{job_id}] 🔍 Error details: {type(e).__name__}")
        update_job_status(job_id, "failed", error=str(e))
        raise


@celery_app.task(name="federated_training")
def federated_training_task(
    job_id: str,
    round_id: str,
    dataset_id: str
):
    """
    Federated training with Flower.
    
    This task starts a Flower client that connects to the Flower server
    and participates in federated learning rounds.
    
    Args:
        job_id: Job identifier
        round_id: FL round identifier (for tracking)
        dataset_id: Local dataset identifier
    """
    try:
        update_job_status(job_id, "running")
        
        # Get dataset path
        db = SessionLocal()
        from .database import Dataset
        dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
        
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")
        
        dataset_path = dataset.path
        n_samples = dataset.num_samples
        
        print(f"[{settings.NODE_ID}] Starting Flower client for round {round_id}...")
        print(f"[{settings.NODE_ID}] Dataset: {dataset_path} ({n_samples} samples)")
        
        # Import and start Flower client directly
        # Note: This runs in the worker container which has flower_client.py
        sys.path.insert(0, '/app/worker')
        from flower_client import start_flower_client
        
        # Get model name from environment or default to efficientnet_b0
        model_name = os.getenv("MODEL_NAME", "efficientnet_b0")
        
        # Start Flower client (blocking call - will run until FL rounds complete)
        start_flower_client(
            server_address=settings.FLOWER_SERVER,
            node_id=settings.NODE_ID,
            model_name=model_name,
            num_classes=2,
            dataset_path=dataset_path,
            device=settings.DEVICE,
            batch_size=32
        )
        
        print(f"[{settings.NODE_ID}] Flower client completed successfully")
        
        # After FL completes, save final model as candidate
        # Note: The actual model is saved by Flower client during training
        # Here we just update the database
        model_id = f"resnet18_{round_id}_flower"
        
        result = {
            'round_id': round_id,
            'model_id': model_id,
            'n_samples': n_samples,
            'status': 'completed',
            'note': 'Trained with Flower framework'
        }
        
        db.close()
        update_job_status(job_id, "completed", result=result)
        
        print(f"[{settings.NODE_ID}] ✓ Flower training completed for round {round_id}")
        
        return result
        
    except Exception as e:
        print(f"[{settings.NODE_ID}] ✗ Flower training failed: {e}")
        import traceback
        traceback.print_exc()
        update_job_status(job_id, "failed", error=str(e))
        raise


if __name__ == "__main__":
    celery_app.worker_main(["worker", "--loglevel=INFO"])

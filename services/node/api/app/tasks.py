"""
Celery tasks for asynchronous job processing.
"""
from celery import Celery
from datetime import datetime
from pathlib import Path
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

from node_core import get_logger

_log = get_logger(settings.NODE_ID if hasattr(settings, 'NODE_ID') else "worker")

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
        _log.info(f"Loading dataset from {dataset_path}...")
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
        _log.info(f"Initializing {model_name}...")
        model = get_model(model_name, num_classes=2, pretrained=True)
        model = model.to(settings.DEVICE)
        
        # Setup training
        criterion = torch.nn.CrossEntropyLoss()
        optimizer = get_optimizer(model, 'adam', lr=learning_rate)
        scheduler = get_scheduler(optimizer, 'cosine', num_epochs=num_epochs)
        early_stopping = EarlyStopping(patience=5, mode='max')
        
        # Train
        _log.info("Starting training...")
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
        
        # Compute comprehensive metrics on validation set
        _log.info("Computing final metrics...")
        model.eval()
        y_true = []
        y_pred = []
        y_probs = []
        
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs = inputs.to(settings.DEVICE)
                outputs = model(inputs)
                probs = torch.softmax(outputs, dim=1)
                _, predicted = torch.max(outputs, 1)
                
                y_true.extend(labels.cpu().numpy().tolist())
                y_pred.extend(predicted.cpu().numpy().tolist())
                y_probs.extend(probs[:, 1].cpu().numpy().tolist())  # Probability of positive class
        
        # Compute all metrics
        final_metrics = compute_metrics(y_true, y_pred, y_probs)
        
        # Save model as candidate
        model_id = f"{model_name}_local_{uuid.uuid4().hex[:8]}"
        model_path = os.path.join(settings.MODELS_CANDIDATE_DIR, f"{model_id}.pt")
        
        metadata = {
            'model_name': model_name,
            'epochs': history['epochs_trained'],
            'best_val_acc': history['best_val_acc'],
            'history': history,
            'final_metrics': final_metrics
        }
        
        save_model(model, model_path, metadata)
        
        # Prepare metrics for database (only scalar values)
        db_metrics = {
            'accuracy': final_metrics['accuracy'],
            'f1': final_metrics['f1'],
            'precision': final_metrics['precision'],
            'recall': final_metrics['recall'],
            'auc': final_metrics.get('auc'),
            'sensitivity': final_metrics.get('sensitivity'),
            'specificity': final_metrics.get('specificity'),
            'train_loss': history['train_loss'][-1],
            'val_loss': history['val_loss'][-1]
        }
        
        _log.info("Final Metrics:")
        _log.step(f"Accuracy: {db_metrics['accuracy']:.4f}")
        _log.step(f"F1 Score: {db_metrics['f1']:.4f}")
        _log.step(f"Precision: {db_metrics['precision']:.4f}")
        _log.step(f"Recall: {db_metrics['recall']:.4f}")
        if db_metrics['auc']:
            _log.step(f"AUC: {db_metrics['auc']:.4f}")
        _log.step(f"Sensitivity: {db_metrics['sensitivity']:.4f}")
        _log.step(f"Specificity: {db_metrics['specificity']:.4f}")
        
        # Save to database
        db = SessionLocal()
        model_record = Model(
            model_id=model_id,
            model_name=model_name,
            version="local",
            type="candidate",
            file_path=model_path,
            metrics=db_metrics
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
        
        _log.ok(f"Training completed: {model_id}")

        return result

    except Exception as e:
        _log.fail(f"Training failed: {e}")
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
        job_log = get_logger(job_id)
        job_log.info(f"Starting inference job")
        job_log.step(f"Processing {len(image_paths)} image(s)")
        job_log.step(f"Grad-CAM: {'enabled' if generate_gradcam else 'disabled'}")

        update_job_status(job_id, "running")

        db = SessionLocal()

        job_log.info("Looking for model...")
        if model_id:
            model_record = db.query(Model).filter(Model.model_id == model_id).first()
            job_log.step(f"Using specified model: {model_id}")
        else:
            model_record = db.query(Model).filter(Model.type == "deployed").first()
            job_log.step("Using deployed model")
        
        if not model_record:
            raise ValueError("No model found")
        
        job_log.info(f"Loading model: {model_name}")
        job_log.step(f"Model path: {model_path}")
        job_log.step(f"Device: {settings.DEVICE}")
        model, metadata = load_model(model_name, model_path, device=settings.DEVICE)
        job_log.ok("Model loaded successfully")

        job_log.info("Preparing images for inference...")
        from PIL import Image
        from node_core import get_val_transforms

        transform = get_val_transforms()
        images_tensors = []

        for idx, img_path in enumerate(image_paths, 1):
            job_log.step(f"Loading image {idx}/{len(image_paths)}: {os.path.basename(img_path)}")
            img = Image.open(img_path).convert('RGB')
            img_tensor = transform(img)
            images_tensors.append(img_tensor)

        job_log.ok("All images prepared")

        job_log.info("Running inference...")
        batch_tensor = torch.stack(images_tensors)

        pred_classes, confidences, probs = predict_batch(
            model, batch_tensor, device=settings.DEVICE
        )
        job_log.ok("Inference completed")
        
        # Generate Grad-CAM if requested
        gradcam_paths = []
        if generate_gradcam:
            job_log.info("Generating Grad-CAM visualizations...")
            target_layer = get_final_conv_layer(model, model_name)
            gradcam = GradCAM(model, target_layer)

            for i, (img_path, img_tensor) in enumerate(zip(image_paths, images_tensors)):
                job_log.step(f"Generating Grad-CAM {i+1}/{len(image_paths)}")
                img = Image.open(img_path).convert('RGB')
                import numpy as np
                img_np = np.array(img).astype(np.float32) / 255.0
                heatmap, _ = gradcam.generate(img_tensor, device=settings.DEVICE)
                import cv2
                heatmap_resized = cv2.resize(heatmap, (img_np.shape[1], img_np.shape[0]))
                overlay_path = os.path.join(
                    settings.RESULTS_DIR, "inference",
                    f"{job_id}_{i}_gradcam.png"
                )
                save_gradcam_overlay(img_np, heatmap_resized, overlay_path)
                gradcam_paths.append(overlay_path)

            job_log.ok("Grad-CAM visualizations saved")
        else:
            gradcam_paths = [None] * len(image_paths)
        
        job_log.info("Saving results to database...")
        results = []
        for i, (img_path, pred_cls, conf, prob) in enumerate(
            zip(image_paths, pred_classes, confidences, probs)
        ):
            result_id = f"{job_id}_{i}"
            class_name = "PNEUMONIA" if pred_cls == 1 else "NORMAL"
            job_log.step(f"Image {i+1}: {class_name} (confidence: {conf:.2%})")
            
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

        job_log.ok("Results saved to database")

        result = {'num_images': len(image_paths), 'results': results}
        update_job_status(job_id, "completed", result=result)

        job_log.ok(f"Inference job completed — {len(image_paths)} image(s) processed")
        return result

    except Exception as e:
        get_logger(job_id).fail(f"Inference job failed: {e}")
        update_job_status(job_id, "failed", error=str(e))
        raise


@celery_app.task(name="federated_training")
def federated_training_task(
    job_id: str,
    dataset_id: str,
    model_name: str = "efficientnet_b0",
    batch_size: int = 32,
    # Experiment logging (NOU)
    run_id: str = None,
    experiments_dir: str = "experiments",
    splits_dir: str = None,
):
    """
    Federated training with Flower.

    Args:
        job_id: Job identifier (also used as session identifier for model naming)
        dataset_id: Local dataset identifier
        model_name: Model architecture name
        batch_size: Batch size for training on this node
    """
    import sys
    
    # Setup log file for real-time logging
    log_dir = Path(settings.STORAGE_ROOT) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"federated_train_{job_id}.log"
    
    # Open log file in unbuffered mode for real-time writing
    log_handle = open(log_file, 'w', buffering=1)  # Line buffered
    
    class TeeOutput:
        """Write to both original stream and log file."""
        def __init__(self, original, log_file):
            self.original = original
            self.log_file = log_file
        
        def write(self, data):
            self.original.write(data)
            self.log_file.write(data)
            self.log_file.flush()  # Force immediate write
        
        def flush(self):
            self.original.flush()
            self.log_file.flush()
    
    # Redirect stdout and stderr to log file (while keeping console output)
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = TeeOutput(old_stdout, log_handle)
    sys.stderr = TeeOutput(old_stderr, log_handle)
    
    try:
        update_job_status(job_id, "running")
        
        # Rezolvă splits_dir la cale absolută (dacă e relativ, prefixăm cu /)
        effective_splits_dir = splits_dir or os.getenv("SPLITS_DIR", None)
        if effective_splits_dir and not os.path.isabs(effective_splits_dir):
            effective_splits_dir = "/" + effective_splits_dir
        
        # Get dataset path
        db = SessionLocal()
        from .database import Dataset
        dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()

        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        dataset_path = dataset.path
        n_samples = dataset.num_samples
        dataset_name = dataset.name

        _log.info(f"Starting Flower client for session {job_id}...")
        _log.step(f"Model: {model_name}")
        _log.step(f"Dataset: {dataset_name} ({dataset_id})")
        _log.step(f"Path: {dataset_path}")
        _log.step(f"Samples: {n_samples}")
        
        sys.path.insert(0, '/app/worker')
        from flower_client import start_flower_client, get_last_training_metrics
        
        _log.info("Connecting to Flower server...")
        
        start_flower_client(
            server_address=settings.FLOWER_SERVER,
            node_id=settings.NODE_ID,
            model_name=model_name,
            num_classes=2,
            dataset_path=dataset_path,
            device=settings.DEVICE,
            batch_size=batch_size,
            session_id=job_id,
            enable_ssl=os.getenv("ENABLE_SSL", "true").lower() == "true",
            certificates_path=os.getenv("CERTIFICATES_PATH", "/certificates"),
            enable_dp=os.getenv("ENABLE_DP", "false").lower() == "true",
            dp_target_epsilon=float(os.getenv("DP_TARGET_EPSILON", "1.0")),
            dp_target_delta=float(os.getenv("DP_TARGET_DELTA", "1e-5")),
            dp_noise_multiplier=float(os.getenv("DP_NOISE_MULTIPLIER", "1.0")),
            dp_max_grad_norm=float(os.getenv("DP_MAX_GRAD_NORM", "1.0")),
            dp_max_epochs=int(os.getenv("DP_MAX_EPOCHS", "10")),
            # Split-uri fixe (NOU)
            splits_dir=effective_splits_dir,
        )        
        _log.ok("Flower client completed successfully")
        
        metrics = get_last_training_metrics()
        
        model_id = f"{model_name}_{job_id}_flower"
        model_dir = Path(settings.STORAGE_ROOT) / "models" / "candidate"
        model_path = model_dir / f"{model_id}.pt"
        
        model_saved = False
        if model_path.exists():
            _log.ok(f"Model found at {model_path}")
            model_saved = True
            
            from .database import Model
            db_model = Model(
                model_id=model_id,
                model_name=model_name,
                version=job_id,
                type="candidate",
                labels=["candidate", "federated"],
                session_id=job_id,
                file_path=str(model_path),
                metrics=metrics
            )
            db.add(db_model)
            db.commit()
            _log.ok("Model registered in database")
        else:
            _log.warn(f"Model file not found at {model_path}")
        
        result = {
            'job_id': job_id,
            'model_id': model_id,
            'model_name': model_name,
            'dataset_id': dataset_id,
            'dataset_name': dataset_name,
            'n_samples': n_samples,
            'metrics': metrics,
            'model_path': str(model_path) if model_saved else None,
            'status': 'completed',
            'note': 'Trained with Flower framework'
        }
        
        _log.info(f"Final metrics: {metrics}")
        _log.ok(f"Training completed for session {job_id}")
        _log.step(f"Logs saved to {log_file}")
        
        db.close()
        update_job_status(job_id, "completed", result=result)
        
        return result
        
    except Exception as e:
        _log.fail(f"Flower training failed: {e}")
        import traceback
        traceback.print_exc()
        update_job_status(job_id, "failed", error=str(e))
        raise
    finally:
        # Restore original stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        log_handle.close()


if __name__ == "__main__":
    celery_app.worker_main(["worker", "--loglevel=INFO"])

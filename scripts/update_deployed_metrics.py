#!/usr/bin/env python3
"""
Script to update metrics for the deployed model.
"""
import sys
import os
sys.path.insert(0, 'services/node/api')

import torch
from app.database import SessionLocal, Model, Dataset
from node_core import (
    load_model, load_dataset, create_dataloaders,
    compute_metrics
)

def update_deployed_model_metrics():
    """Update metrics for deployed model."""
    db = SessionLocal()
    
    # Get deployed model
    deployed = db.query(Model).filter(Model.type == 'deployed').first()
    if not deployed:
        print("No deployed model found")
        db.close()
        return
    
    print(f"Found deployed model: {deployed.model_name}")
    print(f"Current metrics: {list(deployed.metrics.keys()) if deployed.metrics else None}")
    
    # Get active dataset
    dataset = db.query(Dataset).filter(Dataset.is_active == True).first()
    if not dataset:
        print("No active dataset found")
        db.close()
        return
    
    print(f"Using dataset: {dataset.name}")
    
    # Load model
    print("Loading model...")
    model = load_model(deployed.file_path, device='cpu')
    model.eval()
    
    # Load validation data
    print("Loading validation data...")
    val_dataset = load_dataset(dataset.path, split='val')
    _, val_loader = create_dataloaders(
        val_dataset, val_dataset,
        batch_size=32,
        num_workers=0
    )
    
    # Compute predictions
    print("Computing predictions...")
    y_true = []
    y_pred = []
    y_probs = []
    
    with torch.no_grad():
        for inputs, labels in val_loader:
            outputs = model(inputs)
            probs = torch.softmax(outputs, dim=1)
            _, predicted = torch.max(outputs, 1)
            
            y_true.extend(labels.cpu().numpy().tolist())
            y_pred.extend(predicted.cpu().numpy().tolist())
            y_probs.extend(probs[:, 1].cpu().numpy().tolist())
    
    # Compute metrics
    print("Computing metrics...")
    metrics = compute_metrics(y_true, y_pred, y_probs)
    
    # Update database
    db_metrics = {
        'accuracy': metrics['accuracy'],
        'f1': metrics['f1'],
        'precision': metrics['precision'],
        'recall': metrics['recall'],
        'auc': metrics.get('auc'),
        'sensitivity': metrics.get('sensitivity'),
        'specificity': metrics.get('specificity'),
    }
    
    # Keep old train/val loss if they exist
    if deployed.metrics:
        if 'train_loss' in deployed.metrics:
            db_metrics['train_loss'] = deployed.metrics['train_loss']
        if 'val_loss' in deployed.metrics:
            db_metrics['val_loss'] = deployed.metrics['val_loss']
    
    deployed.metrics = db_metrics
    db.commit()
    
    print("\n✅ Metrics updated successfully!")
    print(f"  • Accuracy: {db_metrics['accuracy']:.4f}")
    print(f"  • F1 Score: {db_metrics['f1']:.4f}")
    print(f"  • Precision: {db_metrics['precision']:.4f}")
    print(f"  • Recall: {db_metrics['recall']:.4f}")
    if db_metrics['auc']:
        print(f"  • AUC: {db_metrics['auc']:.4f}")
    print(f"  • Sensitivity: {db_metrics['sensitivity']:.4f}")
    print(f"  • Specificity: {db_metrics['specificity']:.4f}")
    
    db.close()

if __name__ == '__main__':
    update_deployed_model_metrics()

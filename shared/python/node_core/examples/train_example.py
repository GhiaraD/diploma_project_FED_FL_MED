"""
Example: Training a chest X-ray classifier with the node_core library.

This demonstrates how to use the modularized ML code extracted from the notebook.
"""
import os
import sys
import torch
import torch.nn as nn

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from node_core import (
    get_model,
    load_dataset,
    create_dataloaders,
    train_model,
    get_optimizer,
    get_scheduler,
    EarlyStopping,
    compute_metrics,
    format_metrics_for_display,
    save_model
)


def main():
    # Configuration
    DATA_DIR = os.path.expanduser("~/data/chest_xray")
    MODEL_NAME = "resnet18"
    BATCH_SIZE = 32
    NUM_EPOCHS = 10
    LEARNING_RATE = 0.001
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    
    print(f"Using device: {DEVICE}")
    print(f"Training {MODEL_NAME} for {NUM_EPOCHS} epochs")
    print("=" * 60)
    
    # Load datasets
    print("\n📂 Loading datasets...")
    train_dataset = load_dataset(DATA_DIR, split='train', image_size=224)
    val_dataset = load_dataset(DATA_DIR, split='val', image_size=224)
    
    print(f"Train samples: {len(train_dataset)}")
    print(f"Val samples: {len(val_dataset)}")
    
    # Create data loaders
    train_loader, val_loader = create_dataloaders(
        train_dataset, val_dataset,
        batch_size=BATCH_SIZE,
        num_workers=4
    )
    
    # Initialize model
    print(f"\n🔧 Initializing {MODEL_NAME}...")
    model = get_model(MODEL_NAME, num_classes=2, pretrained=True)
    model = model.to(DEVICE)
    
    # Setup training
    criterion = nn.CrossEntropyLoss()
    optimizer = get_optimizer(model, 'adam', lr=LEARNING_RATE)
    scheduler = get_scheduler(optimizer, 'cosine', num_epochs=NUM_EPOCHS)
    early_stopping = EarlyStopping(patience=5, mode='max')
    
    # Train
    print("\n🚀 Starting training...")
    history = train_model(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        criterion=criterion,
        optimizer=optimizer,
        device=DEVICE,
        num_epochs=NUM_EPOCHS,
        scheduler=scheduler,
        early_stopping=early_stopping,
        verbose=True
    )
    
    # Print results
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Epochs trained: {history['epochs_trained']}")
    print(f"Best validation accuracy: {history['best_val_acc']:.4f}")
    print(f"Final train loss: {history['train_loss'][-1]:.4f}")
    print(f"Final val loss: {history['val_loss'][-1]:.4f}")
    
    # Save model
    output_path = f"{MODEL_NAME}_trained.pt"
    metadata = {
        'model_name': MODEL_NAME,
        'epochs': history['epochs_trained'],
        'best_val_acc': history['best_val_acc'],
        'history': history
    }
    save_model(model, output_path, metadata)
    print(f"\n💾 Model saved to: {output_path}")
    
    # Evaluate on test set
    print("\n📊 Evaluating on test set...")
    test_dataset = load_dataset(DATA_DIR, split='test', image_size=224)
    test_loader = torch.utils.data.DataLoader(
        test_dataset, batch_size=BATCH_SIZE, shuffle=False
    )
    
    model.eval()
    y_true, y_pred, y_probs = [], [], []
    
    with torch.no_grad():
        for inputs, labels in test_loader:
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
            outputs = model(inputs)
            probs = torch.softmax(outputs, dim=1)
            preds = torch.argmax(outputs, dim=1)
            
            y_true.extend(labels.cpu().numpy())
            y_pred.extend(preds.cpu().numpy())
            y_probs.extend(probs[:, 1].cpu().numpy())
    
    # Compute metrics
    metrics = compute_metrics(y_true, y_pred, y_probs)
    print(format_metrics_for_display(metrics))


if __name__ == "__main__":
    main()

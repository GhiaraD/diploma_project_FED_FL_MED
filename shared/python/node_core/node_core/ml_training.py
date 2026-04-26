"""
ML Training Module - Training loops, validation, and optimization utilities.
"""
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from typing import Tuple, Optional, Dict
from tqdm import tqdm


class EarlyStopping:
    """
    Early stopping to prevent overfitting.
    
    Stops training when validation metric doesn't improve for 'patience' epochs.
    """
    
    def __init__(self, patience: int = 5, min_delta: float = 0.0, mode: str = 'max'):
        """
        Args:
            patience: Number of epochs to wait before stopping
            min_delta: Minimum change to qualify as improvement
            mode: 'max' for metrics to maximize (accuracy), 'min' for loss
        """
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.counter = 0
        self.best_score = None
        self.early_stop = False
        
    def __call__(self, score: float) -> bool:
        """
        Check if training should stop.
        
        Args:
            score: Current validation metric
            
        Returns:
            True if should stop, False otherwise
        """
        if self.best_score is None:
            self.best_score = score
            return False
        
        if self.mode == 'max':
            improved = score > (self.best_score + self.min_delta)
        else:
            improved = score < (self.best_score - self.min_delta)
        
        if improved:
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
                return True
        
        return False


def train_epoch(
    model: nn.Module,
    train_loader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: str,
    scheduler: Optional[optim.lr_scheduler._LRScheduler] = None
) -> Tuple[float, float]:
    """
    Train model for one epoch.
    
    Args:
        model: PyTorch model
        train_loader: Training data loader
        criterion: Loss function
        optimizer: Optimizer
        device: Device to train on ('cpu' or 'cuda')
        scheduler: Optional learning rate scheduler
        
    Returns:
        Tuple of (average_loss, accuracy)
    """
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    pbar = tqdm(train_loader, desc="Training", leave=False)
    
    for inputs, labels in pbar:
        inputs, labels = inputs.to(device), labels.to(device)
        
        # Zero gradients
        optimizer.zero_grad()
        
        # Forward pass
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        # Statistics
        running_loss += loss.item() * inputs.size(0)
        _, predicted = torch.max(outputs, 1)
        total += labels.size(0)
        correct += (predicted == labels).sum().item()
        
        # Update progress bar
        pbar.set_postfix({
            'loss': f'{loss.item():.4f}',
            'acc': f'{100 * correct / total:.2f}%'
        })
    
    # Step scheduler if provided
    if scheduler is not None:
        scheduler.step()
    
    epoch_loss = running_loss / total
    epoch_acc = correct / total
    
    return epoch_loss, epoch_acc


def validate(
    model: nn.Module,
    val_loader: DataLoader,
    criterion: nn.Module,
    device: str
) -> Tuple[float, float, list, list]:
    """
    Validate model on validation set.
    
    Args:
        model: PyTorch model
        val_loader: Validation data loader
        criterion: Loss function
        device: Device to validate on
        
    Returns:
        Tuple of (loss, accuracy, true_labels, predictions)
    """
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    
    all_labels = []
    all_preds = []
    
    with torch.no_grad():
        for inputs, labels in tqdm(val_loader, desc="Validating", leave=False):
            inputs, labels = inputs.to(device), labels.to(device)
            
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            
            running_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
            all_labels.extend(labels.cpu().numpy())
            all_preds.extend(predicted.cpu().numpy())
    
    val_loss = running_loss / total
    val_acc = correct / total
    
    return val_loss, val_acc, all_labels, all_preds


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: str,
    num_epochs: int = 10,
    scheduler: Optional[optim.lr_scheduler._LRScheduler] = None,
    early_stopping: Optional[EarlyStopping] = None,
    verbose: bool = True
) -> Dict:
    """
    Complete training loop with validation.
    
    Args:
        model: PyTorch model
        train_loader: Training data loader
        val_loader: Validation data loader
        criterion: Loss function
        optimizer: Optimizer
        device: Device to train on
        num_epochs: Maximum number of epochs
        scheduler: Optional learning rate scheduler
        early_stopping: Optional early stopping callback
        verbose: Whether to print progress
        
    Returns:
        Dict with training history (losses, accuracies, etc.)
    """
    history = {
        'train_loss': [],
        'train_acc': [],
        'val_loss': [],
        'val_acc': [],
        'epochs_trained': 0
    }
    
    best_val_acc = 0.0
    best_model_state = None
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Starting Training: {num_epochs} epochs")
        print(f"{'='*60}")
    
    for epoch in range(num_epochs):
        if verbose:
            print(f"\n{'─'*60}")
            print(f"📚 Epoch {epoch + 1}/{num_epochs}")
            print(f"{'─'*60}")
        
        # Train
        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, device, scheduler
        )
        
        # Validate
        val_loss, val_acc, _, _ = validate(model, val_loader, criterion, device)
        
        # Save history
        history['train_loss'].append(train_loss)
        history['train_acc'].append(train_acc)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        history['epochs_trained'] = epoch + 1
        
        if verbose:
            print(f"  📊 Train → Loss: {train_loss:.4f} | Accuracy: {train_acc:.2%}")
            print(f"  📈 Val   → Loss: {val_loss:.4f} | Accuracy: {val_acc:.2%}")
        
        # Save best model
        if val_acc > best_val_acc:
            if verbose and best_val_acc > 0:
                print(f"  ⭐ New best accuracy: {val_acc:.2%} (previous: {best_val_acc:.2%})")
            best_val_acc = val_acc
            best_model_state = model.state_dict().copy()
        
        # Early stopping check
        if early_stopping is not None:
            if early_stopping(val_acc):
                if verbose:
                    print(f"\n⚠️  Early stopping triggered at epoch {epoch + 1}")
                break
    
    # Restore best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
    
    history['best_val_acc'] = best_val_acc
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"✅ Training Complete!")
        print(f"  • Epochs trained: {history['epochs_trained']}")
        print(f"  • Best validation accuracy: {best_val_acc:.2%}")
        print(f"  • Final train loss: {history['train_loss'][-1]:.4f}")
        print(f"  • Final val loss: {history['val_loss'][-1]:.4f}")
        print(f"{'='*60}\n")
    
    return history


def get_optimizer(
    model: nn.Module,
    optimizer_name: str = 'adam',
    lr: float = 0.001,
    weight_decay: float = 1e-4
) -> optim.Optimizer:
    """
    Get optimizer for model.
    
    Args:
        model: PyTorch model
        optimizer_name: 'adam', 'sgd', or 'adamw'
        lr: Learning rate
        weight_decay: L2 regularization
        
    Returns:
        Optimizer instance
    """
    optimizer_name = optimizer_name.lower()
    
    if optimizer_name == 'adam':
        return optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    elif optimizer_name == 'sgd':
        return optim.SGD(model.parameters(), lr=lr, momentum=0.9, weight_decay=weight_decay)
    elif optimizer_name == 'adamw':
        return optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    else:
        raise ValueError(f"Unsupported optimizer: {optimizer_name}")


def get_scheduler(
    optimizer: optim.Optimizer,
    scheduler_name: str = 'cosine',
    num_epochs: int = 10
) -> Optional[optim.lr_scheduler._LRScheduler]:
    """
    Get learning rate scheduler.
    
    Args:
        optimizer: Optimizer instance
        scheduler_name: 'cosine', 'step', or None
        num_epochs: Total number of epochs
        
    Returns:
        Scheduler instance or None
    """
    if scheduler_name is None or scheduler_name.lower() == 'none':
        return None
    
    scheduler_name = scheduler_name.lower()
    
    if scheduler_name == 'cosine':
        return optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)
    elif scheduler_name == 'step':
        return optim.lr_scheduler.StepLR(optimizer, step_size=num_epochs // 3, gamma=0.1)
    else:
        raise ValueError(f"Unsupported scheduler: {scheduler_name}")

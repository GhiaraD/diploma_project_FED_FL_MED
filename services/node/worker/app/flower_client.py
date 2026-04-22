"""
Flower Client for Fed-Med-FL Node Worker

This replaces the custom FL client with Flower's NumPyClient.
"""
import flwr as fl
import torch
import torch.nn as nn
import sys
import os
from typing import Dict, List, Tuple
import numpy as np
from pathlib import Path

# Add node_core to path
sys.path.insert(0, '/app/shared/python/node_core')

from node_core import (
    get_model,
    load_dataset,
    create_dataloaders,
    train_model,
    get_optimizer,
    get_scheduler,
    compute_metrics,
)


class FedMedClient(fl.client.NumPyClient):
    """
    Flower Client for Fed-Med-FL.
    
    Implements:
    - get_parameters(): Return model parameters
    - set_parameters(): Set model parameters
    - fit(): Train model locally
    - evaluate(): Evaluate model locally
    """
    
    def __init__(
        self,
        node_id: str,
        model_name: str,
        num_classes: int,
        dataset_path: str,
        device: str = "cpu",
        batch_size: int = 32,
    ):
        """
        Initialize Flower client.
        
        Args:
            node_id: Node identifier
            model_name: Model architecture
            num_classes: Number of classes
            dataset_path: Path to dataset
            device: Device (cpu/cuda)
            batch_size: Batch size for training
        """
        self.node_id = node_id
        self.model_name = model_name
        self.num_classes = num_classes
        self.dataset_path = dataset_path
        self.device = device
        self.batch_size = batch_size
        
        # Initialize model
        self.model = get_model(model_name, num_classes=num_classes, pretrained=False)
        self.model.to(device)
        
        # Load dataset
        self.train_loader, self.val_loader = self._load_data()
        
        print(f"[{node_id}] Flower client initialized")
        print(f"[{node_id}] Model: {model_name}")
        print(f"[{node_id}] Dataset: {dataset_path}")
        print(f"[{node_id}] Device: {device}")
    
    def _load_data(self):
        """Load and prepare datasets."""
        print(f"[{self.node_id}] Loading dataset from {self.dataset_path}...")
        
        # Load dataset
        train_dataset = load_dataset(self.dataset_path, split='train')
        
        # Split for validation
        from torch.utils.data import random_split
        train_size = int(0.8 * len(train_dataset))
        val_size = len(train_dataset) - train_size
        train_dataset, val_dataset = random_split(
            train_dataset, [train_size, val_size]
        )
        
        # Create dataloaders
        train_loader, val_loader = create_dataloaders(
            train_dataset,
            val_dataset,
            batch_size=self.batch_size,
            num_workers=0  # Must be 0 for Celery workers
        )
        
        print(f"[{self.node_id}] ✓ Dataset loaded:")
        print(f"  - Training samples: {len(train_dataset)}")
        print(f"  - Validation samples: {len(val_dataset)}")
        
        return train_loader, val_loader
    
    def get_parameters(self, config: Dict) -> List[np.ndarray]:
        """
        Return current model parameters as numpy arrays.
        
        Args:
            config: Configuration dict (unused)
        
        Returns:
            List of numpy arrays (model parameters)
        """
        return [val.cpu().numpy() for val in self.model.state_dict().values()]
    
    def set_parameters(self, parameters: List[np.ndarray]):
        """
        Set model parameters from numpy arrays.
        
        Args:
            parameters: List of numpy arrays
        """
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = {k: torch.tensor(v) for k, v in params_dict}
        self.model.load_state_dict(state_dict, strict=True)
    
    def fit(
        self,
        parameters: List[np.ndarray],
        config: Dict
    ) -> Tuple[List[np.ndarray], int, Dict]:
        """
        Train model locally.
        
        Args:
            parameters: Global model parameters from server
            config: Training configuration
        
        Returns:
            - Updated parameters
            - Number of training samples
            - Metrics dict
        """
        print(f"\n[{self.node_id}] {'='*50}")
        print(f"[{self.node_id}] Starting local training...")
        print(f"[{self.node_id}] {'='*50}")
        
        # Set global parameters
        self.set_parameters(parameters)
        
        # Get hyperparameters from config
        num_epochs = config.get("num_epochs", 5)
        learning_rate = config.get("learning_rate", 0.001)
        optimizer_name = config.get("optimizer", "adam")
        
        print(f"[{self.node_id}] Hyperparameters:")
        print(f"  - Epochs: {num_epochs}")
        print(f"  - Learning rate: {learning_rate}")
        print(f"  - Optimizer: {optimizer_name}")
        print(f"  - Batch size: {self.batch_size}")
        
        # Setup training
        criterion = torch.nn.CrossEntropyLoss()
        optimizer = get_optimizer(self.model, optimizer_name, lr=learning_rate)
        scheduler = get_scheduler(optimizer, 'cosine', num_epochs=num_epochs)
        
        # Train
        history = train_model(
            model=self.model,
            train_loader=self.train_loader,
            val_loader=self.val_loader,
            criterion=criterion,
            optimizer=optimizer,
            device=self.device,
            num_epochs=num_epochs,
            scheduler=scheduler,
            verbose=True
        )
        
        # Get updated parameters
        updated_parameters = self.get_parameters({})
        
        # Number of training samples
        num_samples = len(self.train_loader.dataset)
        
        # Metrics
        metrics = {
            "accuracy": history['best_val_acc'],
            "train_loss": history['train_loss'][-1],
            "val_loss": history['val_loss'][-1],
        }
        
        print(f"\n[{self.node_id}] ✓ Training complete:")
        print(f"  - Best accuracy: {metrics['accuracy']:.4f}")
        print(f"  - Final train loss: {metrics['train_loss']:.4f}")
        print(f"  - Final val loss: {metrics['val_loss']:.4f}")
        print(f"[{self.node_id}] {'='*50}\n")
        
        return updated_parameters, num_samples, metrics
    
    def evaluate(
        self,
        parameters: List[np.ndarray],
        config: Dict
    ) -> Tuple[float, int, Dict]:
        """
        Evaluate model locally.
        
        Args:
            parameters: Model parameters to evaluate
            config: Evaluation configuration
        
        Returns:
            - Loss
            - Number of evaluation samples
            - Metrics dict
        """
        print(f"[{self.node_id}] Evaluating model...")
        
        # Set parameters
        self.set_parameters(parameters)
        
        # Evaluate
        self.model.eval()
        criterion = torch.nn.CrossEntropyLoss()
        
        total_loss = 0.0
        y_true, y_pred, y_probs = [], [], []
        
        with torch.no_grad():
            for inputs, labels in self.val_loader:
                inputs, labels = inputs.to(self.device), labels.to(self.device)
                outputs = self.model(inputs)
                loss = criterion(outputs, labels)
                
                total_loss += loss.item() * inputs.size(0)
                
                probs = torch.softmax(outputs, dim=1)
                preds = torch.argmax(outputs, dim=1)
                
                y_true.extend(labels.cpu().numpy())
                y_pred.extend(preds.cpu().numpy())
                y_probs.extend(probs[:, 1].cpu().numpy())
        
        # Calculate metrics
        avg_loss = total_loss / len(self.val_loader.dataset)
        num_samples = len(self.val_loader.dataset)
        
        metrics_full = compute_metrics(y_true, y_pred, y_probs)
        
        # Filter only scalar metrics for Flower (no lists/arrays)
        metrics = {
            'accuracy': float(metrics_full.get('accuracy', 0)),
            'f1': float(metrics_full.get('f1', 0)),
            'precision': float(metrics_full.get('precision', 0)),
            'recall': float(metrics_full.get('recall', 0)),
            'auc': float(metrics_full.get('auc', 0)),
        }
        
        print(f"[{self.node_id}] Evaluation results:")
        print(f"  - Loss: {avg_loss:.4f}")
        print(f"  - Accuracy: {metrics.get('accuracy', 0):.4f}")
        print(f"  - F1: {metrics.get('f1', 0):.4f}")
        
        return avg_loss, num_samples, metrics


def start_flower_client(
    server_address: str,
    node_id: str,
    model_name: str,
    num_classes: int,
    dataset_path: str,
    device: str = "cpu",
    batch_size: int = 32,
):
    """
    Start Flower client and connect to server.
    
    Args:
        server_address: Flower server address (host:port)
        node_id: Node identifier
        model_name: Model architecture
        num_classes: Number of classes
        dataset_path: Path to dataset
        device: Device (cpu/cuda)
        batch_size: Batch size
    """
    print("=" * 70)
    print(f"FED-MED-FL FLOWER CLIENT - {node_id}")
    print("=" * 70)
    print(f"Server: {server_address}")
    print(f"Model: {model_name}")
    print(f"Dataset: {dataset_path}")
    print(f"Device: {device}")
    print("=" * 70)
    
    # Create client
    client = FedMedClient(
        node_id=node_id,
        model_name=model_name,
        num_classes=num_classes,
        dataset_path=dataset_path,
        device=device,
        batch_size=batch_size,
    )
    
    # Connect to server
    print(f"\n[{node_id}] Connecting to Flower server at {server_address}...\n")
    
    try:
        fl.client.start_numpy_client(
            server_address=server_address,
            client=client,
        )
        
        print(f"\n[{node_id}] ✓ Disconnected from server")
        
    except KeyboardInterrupt:
        print(f"\n[{node_id}] Interrupted by user")
    except Exception as e:
        print(f"\n[{node_id}] ✗ Error: {e}")
        raise


def main():
    """Main entry point."""
    # Get configuration from environment
    server_address = os.getenv("FLOWER_SERVER", "central:8082")
    node_id = os.getenv("NODE_ID", "node1")
    model_name = os.getenv("MODEL_NAME", "resnet18")
    num_classes = int(os.getenv("NUM_CLASSES", "2"))
    dataset_path = os.getenv("DATASET_PATH")
    device = os.getenv("DEVICE", "cpu")
    batch_size = int(os.getenv("BATCH_SIZE", "32"))
    
    if not dataset_path:
        raise ValueError("DATASET_PATH environment variable is required")
    
    # Start client
    start_flower_client(
        server_address=server_address,
        node_id=node_id,
        model_name=model_name,
        num_classes=num_classes,
        dataset_path=dataset_path,
        device=device,
        batch_size=batch_size,
    )


if __name__ == "__main__":
    main()

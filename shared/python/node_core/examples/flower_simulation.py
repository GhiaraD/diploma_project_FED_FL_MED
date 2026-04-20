"""
Flower Simulation for Fed-Med-FL

This script runs a complete FL simulation with virtual clients.
Useful for testing without Docker or multiple processes.
"""
import flwr as fl
import torch
import torch.nn as nn
from typing import Dict, List, Tuple
import numpy as np
import sys
import os

# Add node_core to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from node_core import (
    FedMedStrategy,
    get_model,
    get_train_transforms,
    get_val_transforms,
)


class SimulatedFedMedClient(fl.client.NumPyClient):
    """
    Simulated Flower client for testing.
    
    Uses dummy data instead of real medical images.
    """
    
    def __init__(self, cid: str, model_name: str = "resnet18", num_classes: int = 2):
        self.cid = cid
        self.model_name = model_name
        self.num_classes = num_classes
        
        # Initialize model
        self.model = get_model(model_name, num_classes=num_classes, pretrained=False)
        self.device = "cpu"
        self.model.to(self.device)
        
        print(f"[Client {cid}] Initialized with {model_name}")
    
    def get_parameters(self, config: Dict) -> List[np.ndarray]:
        """Return model parameters."""
        return [val.cpu().numpy() for val in self.model.state_dict().values()]
    
    def set_parameters(self, parameters: List[np.ndarray]):
        """Set model parameters."""
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = {k: torch.tensor(v) for k, v in params_dict}
        self.model.load_state_dict(state_dict, strict=True)
    
    def fit(
        self,
        parameters: List[np.ndarray],
        config: Dict
    ) -> Tuple[List[np.ndarray], int, Dict]:
        """
        Train model with dummy data.
        """
        print(f"[Client {self.cid}] Starting training...")
        
        # Set parameters
        self.set_parameters(parameters)
        
        # Get config
        num_epochs = config.get("num_epochs", 2)
        learning_rate = config.get("learning_rate", 0.001)
        batch_size = config.get("batch_size", 32)
        
        # Dummy training
        self.model.train()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        criterion = nn.CrossEntropyLoss()
        
        num_samples = 100
        losses = []
        
        for epoch in range(num_epochs):
            # Generate dummy batch (simulating chest X-ray: 224x224x3)
            x = torch.randn(batch_size, 3, 224, 224).to(self.device)
            y = torch.randint(0, self.num_classes, (batch_size,)).to(self.device)
            
            optimizer.zero_grad()
            outputs = self.model(x)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()
            
            losses.append(loss.item())
            
            print(f"[Client {self.cid}] Epoch {epoch+1}/{num_epochs}, Loss: {loss.item():.4f}")
        
        # Get updated parameters
        updated_parameters = self.get_parameters({})
        
        # Metrics
        metrics = {
            "loss": np.mean(losses),
            "accuracy": 0.5 + np.random.rand() * 0.4,  # Simulated: 0.5-0.9
        }
        
        print(f"[Client {self.cid}] ✓ Training complete: {metrics}")
        
        return updated_parameters, num_samples, metrics
    
    def evaluate(
        self,
        parameters: List[np.ndarray],
        config: Dict
    ) -> Tuple[float, int, Dict]:
        """
        Evaluate model with dummy data.
        """
        print(f"[Client {self.cid}] Evaluating...")
        
        # Set parameters
        self.set_parameters(parameters)
        
        # Dummy evaluation
        self.model.eval()
        criterion = nn.CrossEntropyLoss()
        
        with torch.no_grad():
            # Generate dummy batch
            x = torch.randn(32, 3, 224, 224).to(self.device)
            y = torch.randint(0, self.num_classes, (32,)).to(self.device)
            
            outputs = self.model(x)
            loss = criterion(outputs, y)
            
            preds = torch.argmax(outputs, dim=1)
            accuracy = (preds == y).float().mean().item()
        
        metrics = {
            "accuracy": accuracy,
        }
        
        print(f"[Client {self.cid}] Evaluation: Loss={loss.item():.4f}, Acc={accuracy:.4f}")
        
        return loss.item(), 32, metrics


def run_simulation(
    num_clients: int = 3,
    num_rounds: int = 3,
    model_name: str = "resnet18",
    num_classes: int = 2,
    num_epochs: int = 2,
    batch_size: int = 32,
    learning_rate: float = 0.001,
):
    """
    Run Flower simulation with virtual clients.
    
    Args:
        num_clients: Number of virtual clients
        num_rounds: Number of FL rounds
        model_name: Model architecture
        num_classes: Number of classes
        num_epochs: Epochs per round
        batch_size: Batch size
        learning_rate: Learning rate
    """
    print("=" * 70)
    print("FLOWER SIMULATION - Fed-Med-FL")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  - Clients: {num_clients}")
    print(f"  - Rounds: {num_rounds}")
    print(f"  - Model: {model_name}")
    print(f"  - Epochs per round: {num_epochs}")
    print(f"  - Batch size: {batch_size}")
    print(f"  - Learning rate: {learning_rate}")
    print("=" * 70)
    print("")
    
    # Create strategy
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    strategy = FedMedStrategy(
        model_name=model_name,
        num_classes=num_classes,
        storage_path=temp_dir,
        save_models=True,
        fraction_fit=1.0,
        fraction_evaluate=1.0,
        min_fit_clients=num_clients,
        min_evaluate_clients=num_clients,
        min_available_clients=num_clients,
    )
    
    # Client function
    def client_fn(cid: str) -> SimulatedFedMedClient:
        """Create a client for simulation."""
        return SimulatedFedMedClient(cid=cid, model_name=model_name, num_classes=num_classes)
    
    # Configure training
    def fit_config(server_round: int) -> Dict:
        """Return training configuration."""
        return {
            "num_epochs": num_epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
        }
    
    strategy.on_fit_config_fn = fit_config
    
    # Run simulation
    print(f"Starting simulation with {num_clients} clients for {num_rounds} rounds...\n")
    
    history = fl.simulation.start_simulation(
        client_fn=client_fn,
        num_clients=num_clients,
        config=fl.server.ServerConfig(num_rounds=num_rounds),
        strategy=strategy,
    )
    
    # Print results
    print("\n" + "=" * 70)
    print("SIMULATION RESULTS")
    print("=" * 70)
    print(f"Rounds completed: {len(history.losses_distributed)}")
    
    if history.losses_distributed:
        print(f"\nLoss progression:")
        for round_num, (_, loss) in enumerate(history.losses_distributed, 1):
            print(f"  Round {round_num}: {loss:.4f}")
        
        print(f"\nFinal loss: {history.losses_distributed[-1][1]:.4f}")
    
    if history.metrics_distributed:
        print(f"\nAccuracy progression:")
        for round_num, metrics in enumerate(history.metrics_distributed, 1):
            if 'accuracy' in metrics[1]:
                print(f"  Round {round_num}: {metrics[1]['accuracy']:.4f}")
    
    # Print saved models
    print(f"\nSaved models:")
    import os
    models_dir = os.path.join(temp_dir, "models")
    if os.path.exists(models_dir):
        for f in sorted(os.listdir(models_dir)):
            print(f"  - {f}")
    
    print("=" * 70)
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    return history


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Flower FL simulation")
    parser.add_argument("--clients", type=int, default=3, help="Number of clients")
    parser.add_argument("--rounds", type=int, default=3, help="Number of rounds")
    parser.add_argument("--model", type=str, default="resnet18", help="Model architecture")
    parser.add_argument("--epochs", type=int, default=2, help="Epochs per round")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=0.001, help="Learning rate")
    
    args = parser.parse_args()
    
    run_simulation(
        num_clients=args.clients,
        num_rounds=args.rounds,
        model_name=args.model,
        num_classes=2,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )

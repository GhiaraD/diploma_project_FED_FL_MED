"""
Flower Quickstart Example - Learning the API

This is a simple example to understand Flower's API before implementing
the full Fed-Med-FL migration.

Based on: https://flower.dev/docs/framework/tutorial-quickstart-pytorch.html
"""
import torch
import torch.nn as nn
import flwr as fl
from typing import Dict, List, Tuple
import numpy as np


# ============================================================================
# Simple Model for Testing
# ============================================================================

class SimpleNet(nn.Module):
    """Simple neural network for testing."""
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(10, 5)
        self.fc2 = nn.Linear(5, 2)
    
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = self.fc2(x)
        return x


# ============================================================================
# Flower Client
# ============================================================================

class FlowerClient(fl.client.NumPyClient):
    """
    Flower NumPyClient implementation.
    
    Key methods:
    - get_parameters(): Return model parameters as numpy arrays
    - set_parameters(): Set model parameters from numpy arrays
    - fit(): Train model locally and return updated parameters
    - evaluate(): Evaluate model and return loss + metrics
    """
    
    def __init__(self, model: nn.Module, device: str = "cpu"):
        self.model = model
        self.device = device
        self.model.to(device)
    
    def get_parameters(self, config: Dict) -> List[np.ndarray]:
        """
        Return current model parameters as list of numpy arrays.
        
        Flower will use these to:
        - Send to server for aggregation
        - Initialize clients with global model
        """
        return [val.cpu().numpy() for val in self.model.state_dict().values()]
    
    def set_parameters(self, parameters: List[np.ndarray]):
        """
        Set model parameters from list of numpy arrays.
        
        Called by Flower to:
        - Initialize client with global model
        - Update client after aggregation
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
            config: Training configuration (epochs, lr, etc.)
        
        Returns:
            - Updated parameters (numpy arrays)
            - Number of training samples
            - Metrics dict
        """
        print("[Client] Starting local training...")
        
        # Set global parameters
        self.set_parameters(parameters)
        
        # Get training config
        num_epochs = config.get("num_epochs", 1)
        learning_rate = config.get("learning_rate", 0.01)
        
        # Dummy training (replace with real training)
        self.model.train()
        optimizer = torch.optim.SGD(self.model.parameters(), lr=learning_rate)
        
        for epoch in range(num_epochs):
            # Dummy forward pass
            x = torch.randn(32, 10).to(self.device)
            y = torch.randint(0, 2, (32,)).to(self.device)
            
            optimizer.zero_grad()
            outputs = self.model(x)
            loss = nn.CrossEntropyLoss()(outputs, y)
            loss.backward()
            optimizer.step()
            
            print(f"[Client] Epoch {epoch+1}/{num_epochs}, Loss: {loss.item():.4f}")
        
        # Get updated parameters
        updated_parameters = self.get_parameters({})
        
        # Return: parameters, num_samples, metrics
        return updated_parameters, 32, {"loss": loss.item()}
    
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
            - Loss (float)
            - Number of evaluation samples
            - Metrics dict
        """
        print("[Client] Evaluating model...")
        
        # Set parameters
        self.set_parameters(parameters)
        
        # Dummy evaluation
        self.model.eval()
        with torch.no_grad():
            x = torch.randn(32, 10).to(self.device)
            y = torch.randint(0, 2, (32,)).to(self.device)
            
            outputs = self.model(x)
            loss = nn.CrossEntropyLoss()(outputs, y)
            
            preds = torch.argmax(outputs, dim=1)
            accuracy = (preds == y).float().mean().item()
        
        print(f"[Client] Loss: {loss.item():.4f}, Accuracy: {accuracy:.4f}")
        
        # Return: loss, num_samples, metrics
        return loss.item(), 32, {"accuracy": accuracy}


# ============================================================================
# Flower Strategy
# ============================================================================

class CustomStrategy(fl.server.strategy.FedAvg):
    """
    Custom Flower Strategy extending FedAvg.
    
    Key methods to override:
    - initialize_parameters(): Return initial global model
    - aggregate_fit(): Aggregate training results
    - aggregate_evaluate(): Aggregate evaluation results
    """
    
    def __init__(self, model: nn.Module, **kwargs):
        super().__init__(**kwargs)
        self.model = model
        print("[Strategy] Initialized with FedAvg")
    
    def initialize_parameters(self, client_manager):
        """
        Return initial global model parameters.
        
        Called once at the start of FL.
        """
        print("[Strategy] Initializing global model parameters...")
        parameters = [val.cpu().numpy() for val in self.model.state_dict().values()]
        return fl.common.ndarrays_to_parameters(parameters)
    
    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple[fl.server.client_proxy.ClientProxy, fl.common.FitRes]],
        failures: List[BaseException],
    ):
        """
        Aggregate training results from clients.
        
        Args:
            server_round: Current round number
            results: List of (client, fit_result) tuples
            failures: List of exceptions from failed clients
        
        Returns:
            - Aggregated parameters
            - Aggregated metrics
        """
        print(f"[Strategy] Aggregating round {server_round} with {len(results)} clients...")
        
        # Call parent FedAvg aggregation
        aggregated_parameters, aggregated_metrics = super().aggregate_fit(
            server_round, results, failures
        )
        
        if aggregated_parameters is not None:
            print(f"[Strategy] ✓ Aggregation complete for round {server_round}")
        
        return aggregated_parameters, aggregated_metrics


# ============================================================================
# Main Functions
# ============================================================================

def start_server(num_rounds: int = 3, min_clients: int = 2):
    """
    Start Flower server.
    
    Args:
        num_rounds: Number of FL rounds
        min_clients: Minimum number of clients required
    """
    print("=" * 70)
    print("FLOWER SERVER - Quickstart Example")
    print("=" * 70)
    
    # Initialize model
    model = SimpleNet()
    
    # Create strategy
    strategy = CustomStrategy(
        model=model,
        fraction_fit=1.0,  # Use all available clients for training
        fraction_evaluate=1.0,  # Use all available clients for evaluation
        min_fit_clients=min_clients,
        min_evaluate_clients=min_clients,
        min_available_clients=min_clients,
    )
    
    # Start server
    print(f"\n[Server] Starting Flower server for {num_rounds} rounds...")
    print(f"[Server] Waiting for {min_clients} clients to connect...\n")
    
    fl.server.start_server(
        server_address="0.0.0.0:8080",
        config=fl.server.ServerConfig(num_rounds=num_rounds),
        strategy=strategy,
    )
    
    print("\n[Server] ✓ FL training complete!")


def start_client(server_address: str = "localhost:8080"):
    """
    Start Flower client.
    
    Args:
        server_address: Address of Flower server (host:port)
    """
    print("=" * 70)
    print("FLOWER CLIENT - Quickstart Example")
    print("=" * 70)
    
    # Initialize model
    model = SimpleNet()
    
    # Create client
    client = FlowerClient(model=model, device="cpu")
    
    # Connect to server
    print(f"\n[Client] Connecting to server at {server_address}...\n")
    
    fl.client.start_numpy_client(
        server_address=server_address,
        client=client,
    )
    
    print("\n[Client] ✓ Disconnected from server")


# ============================================================================
# Simulation (for testing without multiple processes)
# ============================================================================

def run_simulation(num_clients: int = 3, num_rounds: int = 3):
    """
    Run Flower simulation with virtual clients.
    
    This is useful for:
    - Quick testing without Docker
    - CI/CD pipelines
    - Development
    
    Args:
        num_clients: Number of virtual clients
        num_rounds: Number of FL rounds
    """
    print("=" * 70)
    print("FLOWER SIMULATION - Quickstart Example")
    print("=" * 70)
    print(f"\nSimulating FL with {num_clients} clients for {num_rounds} rounds...\n")
    
    # Initialize model
    model = SimpleNet()
    
    # Create strategy
    strategy = CustomStrategy(
        model=model,
        fraction_fit=1.0,
        fraction_evaluate=1.0,
        min_fit_clients=num_clients,
        min_evaluate_clients=num_clients,
        min_available_clients=num_clients,
    )
    
    # Client function (creates a client for simulation)
    def client_fn(cid: str) -> FlowerClient:
        """Create a Flower client for simulation."""
        print(f"[Simulation] Creating client {cid}")
        model = SimpleNet()
        return FlowerClient(model=model, device="cpu")
    
    # Run simulation
    history = fl.simulation.start_simulation(
        client_fn=client_fn,
        num_clients=num_clients,
        config=fl.server.ServerConfig(num_rounds=num_rounds),
        strategy=strategy,
    )
    
    print("\n" + "=" * 70)
    print("SIMULATION RESULTS")
    print("=" * 70)
    print(f"Rounds completed: {len(history.losses_distributed)}")
    print(f"Final loss: {history.losses_distributed[-1][1]:.4f}")
    print("=" * 70)
    
    return history


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python flower_quickstart.py server    # Start server")
        print("  python flower_quickstart.py client    # Start client")
        print("  python flower_quickstart.py simulate  # Run simulation")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "server":
        start_server(num_rounds=3, min_clients=2)
    elif mode == "client":
        start_client(server_address="localhost:8080")
    elif mode == "simulate":
        run_simulation(num_clients=3, num_rounds=3)
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)

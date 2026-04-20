"""
Flower Server for Fed-Med-FL Central Orchestrator

This replaces the custom FL implementation with Flower's gRPC-based server.
"""
import flwr as fl
import sys
import os
from pathlib import Path

# Add node_core to path
sys.path.insert(0, '/app/shared/python/node_core')

from node_core import create_fedmed_strategy


def start_flower_server(
    server_address: str = "0.0.0.0:8080",
    num_rounds: int = 5,
    min_clients: int = 2,
    model_name: str = "resnet18",
    num_classes: int = 2,
    storage_path: str = "/storage",
    fraction_fit: float = 1.0,
    fraction_evaluate: float = 1.0,
):
    """
    Start Flower server for federated learning.
    
    Args:
        server_address: Server address (host:port)
        num_rounds: Number of FL rounds
        min_clients: Minimum number of clients required
        model_name: Model architecture
        num_classes: Number of output classes
        storage_path: Storage directory path
        fraction_fit: Fraction of clients for training
        fraction_evaluate: Fraction of clients for evaluation
    """
    print("=" * 70)
    print("FED-MED-FL FLOWER SERVER")
    print("=" * 70)
    print(f"Server address: {server_address}")
    print(f"Number of rounds: {num_rounds}")
    print(f"Minimum clients: {min_clients}")
    print(f"Model: {model_name}")
    print(f"Storage: {storage_path}")
    print("=" * 70)
    
    # Create strategy
    strategy = create_fedmed_strategy(
        model_name=model_name,
        num_classes=num_classes,
        storage_path=storage_path,
        min_clients=min_clients,
        fraction_fit=fraction_fit,
        fraction_evaluate=fraction_evaluate,
    )
    
    # Configure server
    config = fl.server.ServerConfig(num_rounds=num_rounds)
    
    # Start server
    print(f"\n[Server] Starting Flower server...")
    print(f"[Server] Waiting for {min_clients} clients to connect...\n")
    
    try:
        fl.server.start_server(
            server_address=server_address,
            config=config,
            strategy=strategy,
        )
        
        print("\n[Server] ✓ FL training complete!")
        print(f"[Server] Total rounds: {len(strategy.get_round_history())}")
        
        # Print final model path
        final_model = strategy.get_current_model_path()
        if final_model:
            print(f"[Server] Final model: {final_model}")
        
    except KeyboardInterrupt:
        print("\n[Server] Interrupted by user")
    except Exception as e:
        print(f"\n[Server] ✗ Error: {e}")
        raise


def main():
    """Main entry point."""
    # Get configuration from environment
    server_address = os.getenv("FLOWER_SERVER_ADDRESS", "0.0.0.0:8080")
    num_rounds = int(os.getenv("NUM_ROUNDS", "5"))
    min_clients = int(os.getenv("MIN_CLIENTS", "2"))
    model_name = os.getenv("MODEL_NAME", "resnet18")
    num_classes = int(os.getenv("NUM_CLASSES", "2"))
    storage_path = os.getenv("CENTRAL_STORAGE", "/storage")
    
    # Start server
    start_flower_server(
        server_address=server_address,
        num_rounds=num_rounds,
        min_clients=min_clients,
        model_name=model_name,
        num_classes=num_classes,
        storage_path=storage_path,
    )


if __name__ == "__main__":
    main()

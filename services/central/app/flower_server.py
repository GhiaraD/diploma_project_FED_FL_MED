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
    num_rounds: int = 2,
    min_clients: int = 2,
    model_name: str = "resnet18",
    num_classes: int = 2,
    storage_path: str = "/storage",
    fraction_fit: float = 2/3,
    fraction_evaluate: float = 1.0,
    min_fit_clients: int = 2,
    min_available_clients: int = 3,
    num_epochs: int = 2,
    learning_rate: float = 0.001,
    optimizer: str = "adam",
    enable_ssl: bool = True,
    certificates_path: str = "/certificates",
    signature_policy: str = "log",
    min_valid_signatures: float = 0.8,
    # Server-side Differential Privacy parameters
    enable_server_dp: bool = False,
    server_dp_noise_multiplier: float = 0.1,
    server_dp_sensitivity: float = 1.0,
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
        min_fit_clients: Minimum clients to train per round (1 = sequential)
        min_available_clients: Minimum clients that must be available
        num_epochs: Number of epochs per round
        learning_rate: Learning rate for training
        optimizer: Optimizer name
        enable_ssl: Enable mTLS for secure communication
        certificates_path: Path to SSL certificates
        signature_policy: Policy for invalid signatures
        min_valid_signatures: Minimum fraction of valid signatures
        enable_server_dp: Enable server-side Differential Privacy
        server_dp_noise_multiplier: Noise multiplier for server-side DP
        server_dp_sensitivity: Sensitivity for server-side DP
    """
    print("=" * 70)
    print("FED-MED-FL FLOWER SERVER")
    print("=" * 70)
    print(f"Server address: {server_address}")
    print(f"Number of rounds: {num_rounds}")
    print(f"Minimum clients: {min_clients}")
    print(f"Min fit clients per round: {min_fit_clients}")
    print(f"Min available clients: {min_available_clients}")
    print(f"Model: {model_name}")
    print(f"Storage: {storage_path}")
    print(f"Training: {num_epochs} epochs, lr={learning_rate}, optimizer={optimizer}")
    print(f"SSL/TLS: {'Enabled (mTLS)' if enable_ssl else 'Disabled'}")
    print(f"Server-side DP: {'Enabled' if enable_server_dp else 'Disabled'}")
    if enable_server_dp:
        print(f"  Noise multiplier: {server_dp_noise_multiplier}")
        print(f"  Sensitivity: {server_dp_sensitivity}")
    print("=" * 70)
    
    # Create strategy
    strategy = create_fedmed_strategy(
        model_name=model_name,
        num_classes=num_classes,
        storage_path=storage_path,
        min_clients=min_clients,
        min_fit_clients=min_fit_clients,
        min_available_clients=min_available_clients,
        fraction_fit=fraction_fit,
        fraction_evaluate=fraction_evaluate,
        num_epochs=num_epochs,
        learning_rate=learning_rate,
        optimizer=optimizer,
        enable_signing=enable_ssl,  # Use same flag as SSL
        certificates_path=certificates_path,
        signature_policy=signature_policy,
        min_valid_signatures=min_valid_signatures,
        # Server-side DP
        enable_server_dp=enable_server_dp,
        server_dp_noise_multiplier=server_dp_noise_multiplier,
        server_dp_sensitivity=server_dp_sensitivity,
    )
    
    # Configure server
    config = fl.server.ServerConfig(num_rounds=num_rounds)
    
    # Configure SSL/TLS if enabled
    ssl_config = None
    if enable_ssl:
        from pathlib import Path
        cert_path = Path(certificates_path) / "central"
        
        # Check if certificates exist
        server_cert = cert_path / "server-cert.pem"
        server_key = cert_path / "server-key.pem"
        ca_cert = cert_path / "ca-cert.pem"
        
        if server_cert.exists() and server_key.exists() and ca_cert.exists():
            print(f"\n[Server] 🔒 Configuring mTLS...")
            print(f"[Server]   Server cert: {server_cert}")
            print(f"[Server]   Server key: {server_key}")
            print(f"[Server]   CA cert: {ca_cert}")
            
            # Flower expects tuple of (ca_cert_bytes, server_cert_bytes, server_key_bytes)
            # Read certificate contents as bytes
            ca_cert_bytes = ca_cert.read_bytes()
            server_cert_bytes = server_cert.read_bytes()
            server_key_bytes = server_key.read_bytes()
            
            ssl_config = (
                ca_cert_bytes,
                server_cert_bytes,
                server_key_bytes,
            )
            print(f"[Server] ✓ mTLS configured successfully")
        else:
            print(f"\n[Server] ⚠️  SSL certificates not found at {cert_path}")
            print(f"[Server] ⚠️  Falling back to insecure connection")
            enable_ssl = False
    
    # Start server
    print(f"\n[Server] Starting Flower server...")
    print(f"[Server] Waiting for {min_clients} clients to connect...\n")
    
    try:
        if enable_ssl and ssl_config:
            fl.server.start_server(
                server_address=server_address,
                config=config,
                strategy=strategy,
                certificates=ssl_config,
            )
        else:
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
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Flower Server for Fed-Med-FL")
    parser.add_argument("--server-address", type=str, default=None, help="Server address (host:port)")
    parser.add_argument("--num-rounds", type=int, default=None, help="Number of FL rounds")
    parser.add_argument("--min-clients", type=int, default=None, help="Minimum number of clients")
    parser.add_argument("--min-fit-clients", type=int, default=None, help="Minimum clients to train per round")
    parser.add_argument("--min-available-clients", type=int, default=None, help="Minimum clients that must be available")
    parser.add_argument("--model-name", type=str, default=None, help="Model architecture")
    parser.add_argument("--num-classes", type=int, default=None, help="Number of output classes")
    parser.add_argument("--storage-path", type=str, default=None, help="Storage directory path")
    parser.add_argument("--fraction-fit", type=float, default=None, help="Fraction of clients for training")
    parser.add_argument("--fraction-evaluate", type=float, default=None, help="Fraction of clients for evaluation")
    parser.add_argument("--num-epochs", type=int, default=None, help="Number of epochs per round")
    parser.add_argument("--learning-rate", type=float, default=None, help="Learning rate")
    parser.add_argument("--optimizer", type=str, default=None, help="Optimizer name")
    parser.add_argument("--enable-ssl", type=str, default=None, help="Enable SSL (true/false)")
    parser.add_argument("--certificates-path", type=str, default=None, help="Path to certificates")
    parser.add_argument("--signature-policy", type=str, default=None, help="Signature policy (log/warn/reject)")
    parser.add_argument("--min-valid-signatures", type=float, default=None, help="Minimum fraction of valid signatures")
    parser.add_argument("--enable-server-dp", type=str, default=None, help="Enable server-side DP (true/false)")
    parser.add_argument("--server-dp-noise-multiplier", type=float, default=None, help="Server-side DP noise multiplier")
    parser.add_argument("--server-dp-sensitivity", type=float, default=None, help="Server-side DP sensitivity")
    
    args = parser.parse_args()
    
    # Get configuration from environment or command line (CLI takes precedence)
    server_address = args.server_address if args.server_address is not None else os.getenv("FLOWER_SERVER_ADDRESS", "0.0.0.0:8080")
    num_rounds = args.num_rounds if args.num_rounds is not None else int(os.getenv("NUM_ROUNDS", "5"))
    min_clients = args.min_clients if args.min_clients is not None else int(os.getenv("MIN_CLIENTS", "2"))
    min_fit_clients = args.min_fit_clients if args.min_fit_clients is not None else int(os.getenv("MIN_FIT_CLIENTS", "1"))
    min_available_clients = args.min_available_clients if args.min_available_clients is not None else int(os.getenv("MIN_AVAILABLE_CLIENTS", "3"))
    model_name = args.model_name if args.model_name is not None else os.getenv("MODEL_NAME", "resnet18")
    num_classes = args.num_classes if args.num_classes is not None else int(os.getenv("NUM_CLASSES", "2"))
    storage_path = args.storage_path if args.storage_path is not None else os.getenv("CENTRAL_STORAGE", "/storage")
    fraction_fit = args.fraction_fit if args.fraction_fit is not None else float(os.getenv("FRACTION_FIT", "1.0"))
    fraction_evaluate = args.fraction_evaluate if args.fraction_evaluate is not None else float(os.getenv("FRACTION_EVALUATE", "1.0"))
    num_epochs = args.num_epochs if args.num_epochs is not None else int(os.getenv("NUM_EPOCHS", "2"))
    learning_rate = args.learning_rate if args.learning_rate is not None else float(os.getenv("LEARNING_RATE", "0.001"))
    optimizer = args.optimizer if args.optimizer is not None else os.getenv("OPTIMIZER", "adam")
    enable_ssl_str = args.enable_ssl if args.enable_ssl is not None else os.getenv("FLOWER_ENABLE_SSL", "true")
    enable_ssl = enable_ssl_str.lower() == "true"
    certificates_path = args.certificates_path if args.certificates_path is not None else os.getenv("CERTIFICATES_PATH", "/certificates")
    signature_policy = args.signature_policy if args.signature_policy is not None else os.getenv("SIGNATURE_POLICY", "log")
    min_valid_signatures = args.min_valid_signatures if args.min_valid_signatures is not None else float(os.getenv("MIN_VALID_SIGNATURES", "0.8"))
    
    # Server-side Differential Privacy configuration
    enable_server_dp_str = args.enable_server_dp if args.enable_server_dp is not None else os.getenv("ENABLE_SERVER_DP", "false")
    enable_server_dp = enable_server_dp_str.lower() == "true"
    server_dp_noise_multiplier = args.server_dp_noise_multiplier if args.server_dp_noise_multiplier is not None else float(os.getenv("SERVER_DP_NOISE_MULTIPLIER", "0.1"))
    server_dp_sensitivity = args.server_dp_sensitivity if args.server_dp_sensitivity is not None else float(os.getenv("SERVER_DP_SENSITIVITY", "1.0"))
    
    # Start server
    start_flower_server(
        server_address=server_address,
        num_rounds=num_rounds,
        min_clients=min_clients,
        min_fit_clients=min_fit_clients,
        min_available_clients=min_available_clients,
        model_name=model_name,
        num_classes=num_classes,
        storage_path=storage_path,
        fraction_fit=fraction_fit,
        fraction_evaluate=fraction_evaluate,
        num_epochs=num_epochs,
        learning_rate=learning_rate,
        optimizer=optimizer,
        enable_ssl=enable_ssl,
        certificates_path=certificates_path,
        signature_policy=signature_policy,
        min_valid_signatures=min_valid_signatures,
        # Server-side DP
        enable_server_dp=enable_server_dp,
        server_dp_noise_multiplier=server_dp_noise_multiplier,
        server_dp_sensitivity=server_dp_sensitivity,
    )


if __name__ == "__main__":
    main()


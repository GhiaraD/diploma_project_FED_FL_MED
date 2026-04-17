"""
Federated Learning Client Module - Node-side FL operations.

Handles:
- Pulling global model from central server
- Computing delta updates (ΔW = W_local - W_global)
- Pushing updates with metadata to central
- Model hash verification
"""
import torch
import torch.nn as nn
import requests
from typing import Dict, Optional, Tuple
import hashlib
import json
from pathlib import Path

from .utils_hash import compute_model_hash


class FederatedClient:
    """
    Federated Learning client for hospital nodes.
    
    Manages communication with central server and delta computation.
    """
    
    def __init__(
        self,
        node_id: str,
        central_url: str,
        storage_path: str = "./storage"
    ):
        """
        Initialize FL client.
        
        Args:
            node_id: Unique identifier for this node (e.g., 'node1')
            central_url: Base URL of central server (e.g., 'http://central:8080')
            storage_path: Local storage path for models and deltas
        """
        self.node_id = node_id
        self.central_url = central_url.rstrip('/')
        self.storage_path = Path(storage_path)
        
        # Create storage directories
        self.models_dir = self.storage_path / "models"
        self.deltas_dir = self.storage_path / "deltas"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.deltas_dir.mkdir(parents=True, exist_ok=True)
    
    def pull_global_model(
        self,
        round_id: str,
        save_path: Optional[str] = None
    ) -> Tuple[Dict, str]:
        """
        Download global model from central server.
        
        Args:
            round_id: Round identifier (e.g., 'R-1')
            save_path: Optional path to save model (default: storage/models/global_{round_id}.pt)
            
        Returns:
            Tuple of (state_dict, model_hash)
            
        Raises:
            requests.RequestException: If download fails
        """
        url = f"{self.central_url}/model/global/{round_id}"
        
        print(f"[{self.node_id}] Pulling global model for round {round_id}...")
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Get model data
            model_data = response.json()
            
            # Extract state dict and hash
            state_dict_b64 = model_data.get('state_dict')
            model_hash = model_data.get('hash')
            
            if not state_dict_b64 or not model_hash:
                raise ValueError("Invalid model data received from central")
            
            # Decode state dict
            import base64
            import io
            state_dict_bytes = base64.b64decode(state_dict_b64)
            state_dict = torch.load(io.BytesIO(state_dict_bytes), map_location='cpu')
            
            # Verify hash
            computed_hash = compute_model_hash(state_dict)
            if computed_hash != model_hash:
                raise ValueError(
                    f"Model hash mismatch! Expected {model_hash}, got {computed_hash}"
                )
            
            # Save to disk if path provided
            if save_path is None:
                save_path = self.models_dir / f"global_{round_id}.pt"
            
            torch.save(state_dict, save_path)
            print(f"[{self.node_id}] ✓ Global model saved to {save_path}")
            print(f"[{self.node_id}] ✓ Model hash: {model_hash[:16]}...")
            
            return state_dict, model_hash
            
        except requests.RequestException as e:
            print(f"[{self.node_id}] ✗ Failed to pull global model: {e}")
            raise
    
    def compute_delta(
        self,
        model_local: nn.Module,
        model_global: nn.Module
    ) -> Dict[str, torch.Tensor]:
        """
        Compute delta update: ΔW = W_local - W_global
        
        Args:
            model_local: Locally trained model
            model_global: Global model (base model)
            
        Returns:
            Dict with delta weights for each parameter
        """
        print(f"[{self.node_id}] Computing delta update...")
        
        delta = {}
        local_state = model_local.state_dict()
        global_state = model_global.state_dict()
        
        # Compute difference for each parameter
        for key in local_state.keys():
            if key in global_state:
                delta[key] = local_state[key] - global_state[key]
            else:
                # New parameter in local model (shouldn't happen in FL)
                print(f"[{self.node_id}] Warning: {key} not in global model")
                delta[key] = local_state[key]
        
        # Calculate delta statistics (only for float tensors)
        total_params = sum(d.numel() for d in delta.values())
        delta_norm = sum(
            torch.norm(d.float()).item() ** 2 
            for d in delta.values() 
            if d.dtype in [torch.float32, torch.float64, torch.float16]
        ) ** 0.5
        
        print(f"[{self.node_id}] ✓ Delta computed: {total_params:,} params, norm={delta_norm:.4f}")
        
        return delta
    
    def compute_delta_from_state_dicts(
        self,
        state_dict_local: Dict[str, torch.Tensor],
        state_dict_global: Dict[str, torch.Tensor]
    ) -> Dict[str, torch.Tensor]:
        """
        Compute delta from state dicts directly.
        
        Args:
            state_dict_local: Local model state dict
            state_dict_global: Global model state dict
            
        Returns:
            Delta state dict
        """
        delta = {}
        
        for key in state_dict_local.keys():
            if key in state_dict_global:
                delta[key] = state_dict_local[key] - state_dict_global[key]
            else:
                delta[key] = state_dict_local[key]
        
        return delta
    
    def save_delta(
        self,
        delta: Dict[str, torch.Tensor],
        round_id: str,
        filename: Optional[str] = None
    ) -> str:
        """
        Save delta to disk.
        
        Args:
            delta: Delta state dict
            round_id: Round identifier
            filename: Optional custom filename
            
        Returns:
            Path to saved delta file
        """
        if filename is None:
            filename = f"delta_{self.node_id}_{round_id}.pt"
        
        save_path = self.deltas_dir / filename
        torch.save(delta, save_path)
        
        print(f"[{self.node_id}] ✓ Delta saved to {save_path}")
        
        return str(save_path)
    
    def push_update(
        self,
        delta: Dict[str, torch.Tensor],
        round_id: str,
        base_model_hash: str,
        n_samples: int,
        metrics: Dict,
        save_delta: bool = True
    ) -> Dict:
        """
        Push delta update to central server.
        
        Args:
            delta: Delta weights (ΔW)
            round_id: Round identifier
            base_model_hash: Hash of global model used as base
            n_samples: Number of training samples used
            metrics: Training metrics (accuracy, f1, etc.)
            save_delta: Whether to save delta locally
            
        Returns:
            Response from central server
            
        Raises:
            requests.RequestException: If upload fails
        """
        print(f"[{self.node_id}] Pushing update for round {round_id}...")
        
        # Save delta locally if requested
        if save_delta:
            delta_path = self.save_delta(delta, round_id)
        
        # Serialize delta
        import base64
        import io
        buffer = io.BytesIO()
        torch.save(delta, buffer)
        delta_bytes = buffer.getvalue()
        delta_b64 = base64.b64encode(delta_bytes).decode('utf-8')
        
        # Compute delta hash for verification
        delta_hash = hashlib.sha256(delta_bytes).hexdigest()
        
        # Prepare payload
        payload = {
            'node_id': self.node_id,
            'round_id': round_id,
            'base_model_hash': base_model_hash,
            'n_samples': n_samples,
            'metrics': metrics,
            'delta': delta_b64,
            'delta_hash': delta_hash
        }
        
        # Send to central
        url = f"{self.central_url}/update/submit"
        
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=60,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            
            result = response.json()
            
            print(f"[{self.node_id}] ✓ Update pushed successfully")
            print(f"[{self.node_id}]   - Samples: {n_samples}")
            print(f"[{self.node_id}]   - Metrics: {metrics}")
            print(f"[{self.node_id}]   - Delta hash: {delta_hash[:16]}...")
            
            return result
            
        except requests.RequestException as e:
            print(f"[{self.node_id}] ✗ Failed to push update: {e}")
            raise
    
    def get_round_plan(self, round_id: str) -> Dict:
        """
        Get training plan for a specific round.
        
        Args:
            round_id: Round identifier
            
        Returns:
            Dict with round plan (hyperparameters, model info, etc.)
        """
        url = f"{self.central_url}/round/{round_id}/plan"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            plan = response.json()
            
            print(f"[{self.node_id}] ✓ Round plan received:")
            print(f"[{self.node_id}]   - Model: {plan.get('model_name')}")
            print(f"[{self.node_id}]   - Epochs: {plan.get('num_epochs')}")
            print(f"[{self.node_id}]   - Learning rate: {plan.get('learning_rate')}")
            
            return plan
            
        except requests.RequestException as e:
            print(f"[{self.node_id}] ✗ Failed to get round plan: {e}")
            raise
    
    def join_round(self, round_id: str) -> Dict:
        """
        Register node participation in a round.
        
        Args:
            round_id: Round identifier
            
        Returns:
            Confirmation from central server
        """
        url = f"{self.central_url}/round/{round_id}/join"
        
        payload = {
            'node_id': self.node_id
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            print(f"[{self.node_id}] ✓ Joined round {round_id}")
            
            return result
            
        except requests.RequestException as e:
            print(f"[{self.node_id}] ✗ Failed to join round: {e}")
            raise
    
    def get_round_status(self, round_id: str) -> Dict:
        """
        Get current status of a round.
        
        Args:
            round_id: Round identifier
            
        Returns:
            Dict with round status (participants, updates received, etc.)
        """
        url = f"{self.central_url}/round/{round_id}/status"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            status = response.json()
            
            return status
            
        except requests.RequestException as e:
            print(f"[{self.node_id}] ✗ Failed to get round status: {e}")
            raise

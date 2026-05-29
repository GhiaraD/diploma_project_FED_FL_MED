"""
Flower Client for Fed-Med-FL Node Worker

This replaces the custom FL client with Flower's NumPyClient.
Supports Differential Privacy via Opacus.
"""
import flwr as fl
import torch
import torch.nn as nn
import sys
import os
import time
from typing import Dict, List, Tuple, Optional
import numpy as np
from pathlib import Path
from PIL import Image

# Differential Privacy imports
try:
    from opacus import PrivacyEngine
    from opacus.validators import ModuleValidator
    from opacus.utils.batch_memory_manager import BatchMemoryManager
    OPACUS_AVAILABLE = True
except ImportError:
    OPACUS_AVAILABLE = False
    # Can't use FedLogger here (not yet imported), plain print is acceptable at import time
    print("⚠️  Opacus not available. Differential Privacy will be disabled.")
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
    create_payload_signer,
    sign_model_parameters,
    get_logger,
    get_val_transforms,
)

# Global variable to store last training metrics
_last_training_metrics = None

# Import set_stage — graceful fallback if resource_monitor not available
try:
    from resource_monitor import set_stage as _set_stage
except ImportError:
    def _set_stage(stage: str) -> None:
        pass


# ============================================================================
# CsvDataset — dataset care citește din fișiere CSV cu split-uri fixe
# ============================================================================

class CsvDataset(torch.utils.data.Dataset):
    """
    Dataset care citește lista de fișiere dintr-un CSV cu split-uri fixe.

    Format CSV: filepath,label  (label: 0=NORMAL, 1=PNEUMONIA)
    """

    def __init__(self, csv_path: str, transform=None):
        """
        Args:
            csv_path: calea către fișierul CSV
            transform: transformări torchvision de aplicat imaginilor
        """
        import csv
        self.samples: List[Tuple[str, int]] = []
        self.transform = transform

        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(
                f"Fișierul de split nu există: {csv_path}\n"
                f"Rulează scripts/prepare_experiment_data.py pentru a genera split-urile."
            )

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.samples.append((row["filepath"], int(row["label"])))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        filepath, label = self.samples[idx]
        # Dacă path-ul e relativ, îl rezolvăm față de rădăcina sistemului de fișiere
        # În Docker, central_dataset e montat la /central_dataset,
        # deci "central_dataset/..." devine "/central_dataset/..."
        p = Path(filepath)
        if not p.is_absolute():
            p = Path("/") / p
        img = Image.open(str(p)).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, label


class FedMedClient(fl.client.NumPyClient):
    """
    Flower Client for Fed-Med-FL.
    
    Implements:
    - get_parameters(): Return model parameters
    - set_parameters(): Set model parameters
    - fit(): Train model locally
    - evaluate(): Evaluate model locally
    - Payload signing for parameter integrity
    """
    
    def __init__(
        self,
        node_id: str,
        model_name: str,
        num_classes: int,
        dataset_path: str,
        device: str = "cpu",
        batch_size: int = 32,
        enable_signing: bool = True,
        certificates_path: str = "/certificates",
        # Differential Privacy parameters
        enable_dp: bool = False,
        dp_target_epsilon: float = 1.0,
        dp_target_delta: float = 1e-5,
        dp_noise_multiplier: float = 1.0,
        dp_max_grad_norm: float = 1.0,
        dp_max_epochs: int = 10,
        # Split-uri fixe (NOU)
        splits_dir: str = None,
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
            enable_signing: Enable payload signing
            certificates_path: Path to certificates
            enable_dp: Enable Differential Privacy
            dp_target_epsilon: Target epsilon for DP
            dp_target_delta: Target delta for DP
            dp_noise_multiplier: Noise multiplier for DP
            dp_max_grad_norm: Maximum gradient norm for clipping
            dp_max_epochs: Maximum epochs for privacy accounting
            splits_dir: Directorul cu split-urile fixe (experiments/splits/).
                        Dacă e setat, se citesc node{N}_train.csv și node{N}_val.csv.
                        Dacă e None, se folosește random_split 80/20 (comportament vechi).
        """
        self.node_id = node_id
        self.model_name = model_name
        self.num_classes = num_classes
        self.dataset_path = dataset_path
        self.device = device
        self.batch_size = batch_size
        self.enable_signing = enable_signing
        self.splits_dir = splits_dir
        
        # Differential Privacy configuration
        self.enable_dp = enable_dp and OPACUS_AVAILABLE
        self.dp_target_epsilon = dp_target_epsilon
        self.dp_target_delta = dp_target_delta
        self.dp_noise_multiplier = dp_noise_multiplier
        self.dp_max_grad_norm = dp_max_grad_norm
        self.dp_max_epochs = dp_max_epochs
        self.privacy_engine = None
        
        if enable_dp and not OPACUS_AVAILABLE:
            get_logger(node_id).warn("DP requested but Opacus not available. DP disabled.")

        self._log = get_logger(node_id)
        
        # Initialize model
        self.model = get_model(model_name, num_classes=num_classes, pretrained=False)
        self.model.to(device)
        
        # Validate model for DP if enabled
        if self.enable_dp:
            self._validate_model_for_dp()
        
        # Initialize payload signer
        self.signer = None
        if enable_signing:
            try:
                self.signer = create_payload_signer(
                    node_id=node_id,
                    certificates_path=certificates_path,
                    is_central=False
                )
                if self.signer.is_ready():
                    self._log.ok("Payload signing enabled")
                else:
                    self._log.warn("Payload signing disabled (certificates not ready)")
                    self.enable_signing = False
            except Exception as e:
                self._log.warn(f"Failed to initialize signer: {e}")
                self.enable_signing = False

        # Load dataset
        self.train_loader, self.val_loader, self.test_loader = self._load_data()

        self._log.info("Flower client initialized")
        self._log.step(f"Model: {model_name}")
        self._log.step(f"Dataset: {dataset_path}")
        self._log.step(f"Device: {device}")
        self._log.step(f"Signing: {'Enabled' if self.enable_signing else 'Disabled'}")
        self._log.step(f"Differential Privacy: {'Enabled' if self.enable_dp else 'Disabled'}")
        if self.enable_dp:
            self._log.step(f"Target ε: {self.dp_target_epsilon}")
            self._log.step(f"Target δ: {self.dp_target_delta}")
            self._log.step(f"Noise multiplier: {self.dp_noise_multiplier}")
            self._log.step(f"Max grad norm: {self.dp_max_grad_norm}")
    
    def _load_data(self):
        """Load and prepare datasets."""
        _set_stage("loading_data")
        self._log.info(f"Loading dataset from {self.dataset_path}...")

        # NOU: Dacă splits_dir e setat, folosim split-urile fixe din CSV
        if self.splits_dir:
            train_csv = Path(self.splits_dir) / f"{self.node_id}_train.csv"
            val_csv = Path(self.splits_dir) / f"{self.node_id}_val.csv"

            if not train_csv.exists():
                raise FileNotFoundError(
                    f"Fișierul de split train nu există: {train_csv}\n"
                    f"Rulează scripts/prepare_experiment_data.py pentru a genera split-urile."
                )
            if not val_csv.exists():
                raise FileNotFoundError(
                    f"Fișierul de split val nu există: {val_csv}\n"
                    f"Rulează scripts/prepare_experiment_data.py pentru a genera split-urile."
                )

            transform_train = get_val_transforms(224)  # fără augmentare pentru reproducibilitate
            transform_val = get_val_transforms(224)

            train_dataset = CsvDataset(str(train_csv), transform=transform_train)
            val_dataset = CsvDataset(str(val_csv), transform=transform_val)

            train_loader, val_loader = create_dataloaders(
                train_dataset,
                val_dataset,
                batch_size=self.batch_size,
                num_workers=0,
            )

            self._log.ok("Dataset încărcat din split-uri fixe:")
            self._log.step(f"Train CSV: {train_csv} ({len(train_dataset)} imagini)")
            self._log.step(f"Val CSV: {val_csv} ({len(val_dataset)} imagini)")

            # Calea experiment nu are CSV de test — test_loader rămâne None
            return train_loader, val_loader, None

        # Calea UI: folosim cele 3 foldere din dataset
        train_dataset = load_dataset(self.dataset_path, split='train')
        val_dataset = load_dataset(self.dataset_path, split='val')
        test_dataset = load_dataset(self.dataset_path, split='test')

        train_loader, val_loader = create_dataloaders(
            train_dataset,
            val_dataset,
            batch_size=self.batch_size,
            num_workers=0  # Must be 0 for Celery workers
        )

        from torch.utils.data import DataLoader
        test_loader = DataLoader(
            test_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=True
        )

        self._log.ok("Dataset loaded:")
        self._log.step(f"Training samples: {len(train_dataset)}")
        self._log.step(f"Validation samples: {len(val_dataset)}")
        self._log.step(f"Test samples: {len(test_dataset)}")

        return train_loader, val_loader, test_loader
    
    def _validate_model_for_dp(self):
        """Validate and fix model for Differential Privacy compatibility."""
        if not self.enable_dp or not OPACUS_AVAILABLE:
            return
        
        self._log.info("Validating model for DP compatibility...")

        try:
            errors = ModuleValidator.validate(self.model, strict=False)
            if errors:
                self._log.warn(f"Model has {len(errors)} compatibility issue(s):")
                for i, error in enumerate(errors[:3], 1):
                    self._log.step(f"{i}. {error}")
                if len(errors) > 3:
                    self._log.step(f"... and {len(errors) - 3} more")
                self._log.info("Attempting automatic fix...")
                self.model = ModuleValidator.fix(self.model)
                self.model.to(self.device)
                self._log.ok("Model fixed for DP compatibility")
            else:
                self._log.ok("Model is DP-compatible")
        except Exception as e:
            self._log.warn(f"DP validation failed: {e}")
            self._log.warn("Disabling DP for this client")
            self.enable_dp = False
    
    def _compute_delta_norm(
        self,
        local_params: List[np.ndarray],
        global_params: List[np.ndarray],
    ) -> float:
        """
        Calculează ||W_local - W_global||_2.

        Args:
            local_params: parametrii modelului după antrenare locală
            global_params: parametrii modelului global primit de la server

        Returns:
            Norma L2 a diferenței
        """
        try:
            delta = np.concatenate([
                (l.flatten() - g.flatten())
                for l, g in zip(local_params, global_params)
            ])
            return float(np.linalg.norm(delta))
        except Exception:
            return 0.0

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
        global _last_training_metrics
        
        # Get current round from config
        current_round = config.get("server_round", "?")

        self._log.section(f"FEDERATED LEARNING ROUND {current_round}")

        self.set_parameters(parameters)
        self._log.ok("Received global model parameters from server")
        _set_stage(f"round_{current_round}_training")

        # NOU: salvăm o copie a parametrilor globali pentru delta_norm
        fit_start = time.time()
        global_parameters = [p.copy() for p in parameters]

        num_epochs = config.get("num_epochs", 5)
        learning_rate = config.get("learning_rate", 0.001)
        optimizer_name = config.get("optimizer", "adam")

        self._log.info("Training Configuration:")
        self._log.step(f"Epochs: {num_epochs}")
        self._log.step(f"Learning rate: {learning_rate}")
        self._log.step(f"Optimizer: {optimizer_name}")
        self._log.step(f"Batch size: {self.batch_size}")
        self._log.step(f"Training samples: {len(self.train_loader.dataset)}")
        self._log.step(f"Validation samples: {len(self.val_loader.dataset)}")
        
        # Setup training
        criterion = torch.nn.CrossEntropyLoss()
        optimizer = get_optimizer(self.model, optimizer_name, lr=learning_rate)
        scheduler = get_scheduler(optimizer, 'cosine', num_epochs=num_epochs)
        
        # Setup Differential Privacy if enabled
        train_loader = self.train_loader
        if self.enable_dp and OPACUS_AVAILABLE:
            self._log.info("Enabling Differential Privacy (DP-SGD)...")
            try:
                for m in self.model.modules():
                    if hasattr(m, "inplace"):
                        m.inplace = False
                self._log.ok("Disabled inplace operations for DP compatibility")

                privacy_engine = PrivacyEngine(secure_mode=False)
                self.model, optimizer, train_loader = privacy_engine.make_private(
                    module=self.model,
                    optimizer=optimizer,
                    data_loader=self.train_loader,
                    noise_multiplier=self.dp_noise_multiplier,
                    max_grad_norm=self.dp_max_grad_norm,
                )
                self.privacy_engine = privacy_engine
                self._log.ok("DP-SGD enabled successfully")
                self._log.step(f"Noise multiplier: {self.dp_noise_multiplier}")
                self._log.step(f"Max grad norm: {self.dp_max_grad_norm}")
                self._log.step("Secure mode: False (for compatibility)")
            except Exception as e:
                self._log.warn(f"Failed to enable DP: {e}")
                self._log.warn("Continuing without DP")
                self.enable_dp = False
                self.privacy_engine = None
        else:
            if not self.enable_dp:
                for m in self.model.modules():
                    if hasattr(m, "inplace"):
                        m.inplace = True
                self._log.ok("Enabled inplace operations for memory efficiency (DP disabled)")
        
        # Train with or without DP
        if self.enable_dp and self.privacy_engine:
            history = self._train_with_dp(
                train_loader=train_loader,
                criterion=criterion,
                optimizer=optimizer,
                scheduler=scheduler,
                num_epochs=num_epochs
            )
        else:
            history = train_model(
                model=self.model,
                train_loader=train_loader,
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
        
        # Run final evaluation to get detailed metrics
        _set_stage(f"round_{current_round}_evaluating")
        final_loss, _, eval_metrics = self.evaluate(updated_parameters, {})

        # NOU: calculare delta_norm
        delta_norm = self._compute_delta_norm(updated_parameters, global_parameters)

        # NOU: timp total antrenare
        local_train_time_sec = round(time.time() - fit_start, 2)

        # Metrics - include detailed evaluation metrics + câmpuri noi
        metrics = {
            "accuracy": history['best_val_acc'],
            "train_loss": history['train_loss'][-1],
            "val_loss": history['val_loss'][-1],
            # Metrici existente
            "f1_score": eval_metrics.get('f1', 0),
            "precision": eval_metrics.get('precision', 0),
            "recall": eval_metrics.get('recall', 0),
            "auc": eval_metrics.get('auc', 0),
            # NOU: metrici extinse pentru ExperimentLogger
            "node_id": self.node_id,
            "val_auc": float(eval_metrics.get('auc', 0) or 0),
            "val_f1": float(eval_metrics.get('f1', 0) or 0),
            "val_sensitivity": float(eval_metrics.get('sensitivity', eval_metrics.get('recall', 0)) or 0),
            "val_specificity": float(eval_metrics.get('specificity', 0) or 0),
            "val_pr_auc": float(eval_metrics.get('pr_auc', 0) or 0),
            "local_train_time_sec": local_train_time_sec,
            "delta_norm": round(delta_norm, 6),
            "n_train_samples_used": num_samples,
        }        
        # Add DP metrics if enabled
        if self.enable_dp and self.privacy_engine:
            try:
                final_epsilon = self.privacy_engine.get_epsilon(delta=self.dp_target_delta)
                metrics["dp_epsilon"] = float(final_epsilon)
                metrics["dp_delta"] = float(self.dp_target_delta)
                metrics["dp_enabled"] = True
                self._log.info(f"Privacy spent: ε = {final_epsilon:.2f} (δ = {self.dp_target_delta})")
            except Exception as e:
                self._log.warn(f"Failed to compute epsilon: {e}")
                metrics["dp_enabled"] = False
        else:
            metrics["dp_enabled"] = False
        
        # Sign parameters if enabled
        signature_package = {'signed': False}
        if self.enable_signing and self.signer:
            try:
                _, signature_package = sign_model_parameters(
                    parameters=updated_parameters,
                    signer=self.signer,
                    metadata={
                        'node_id': self.node_id,
                        'round': current_round,
                        'model_name': self.model_name,
                        'num_samples': num_samples,
                        'accuracy': history['best_val_acc']
                    }
                )
                if signature_package.get('signed'):
                    self._log.ok("Parameters signed successfully")
            except Exception as e:
                self._log.warn(f"Failed to sign parameters: {e}")
                signature_package = {'signed': False, 'error': str(e)}
        
        # Add signature package to metrics for transmission
        # Note: Flower only accepts scalar values in metrics, so we use a special key
        if signature_package.get('signed'):
            # Store signature as JSON string (Flower accepts strings)
            import json
            metrics['_signature_package'] = json.dumps(signature_package)
        
        # Store metrics globally for retrieval after training
        _last_training_metrics = metrics

        self._log.section(f"ROUND {current_round} COMPLETE")
        self._log.step(f"Best accuracy: {metrics['accuracy']:.2%}")
        self._log.step(f"Final train loss: {metrics['train_loss']:.4f}")
        self._log.step(f"Final val loss: {metrics['val_loss']:.4f}")
        self._log.info("Sending updated parameters to server...")
        _set_stage(f"round_{current_round}_complete")

        return updated_parameters, num_samples, metrics
    
    def _train_with_dp(
        self,
        train_loader,
        criterion,
        optimizer,
        scheduler,
        num_epochs: int
    ) -> Dict:
        """
        Train model with Differential Privacy using Opacus.
        
        Args:
            train_loader: DP-enabled data loader
            criterion: Loss function
            optimizer: DP-enabled optimizer
            scheduler: Learning rate scheduler
            num_epochs: Number of epochs
        
        Returns:
            Training history dict
        """
        history = {
            'train_loss': [],
            'val_loss': [],
            'val_acc': [],
            'best_val_acc': 0.0
        }
        
        for epoch in range(num_epochs):
            # Training phase
            self.model.train()
            epoch_loss = 0.0
            num_batches = 0
            
            # Use BatchMemoryManager for efficient DP training
            with BatchMemoryManager(
                data_loader=train_loader,
                max_physical_batch_size=32,  # Adjust based on GPU memory
                optimizer=optimizer
            ) as memory_safe_loader:
                for batch_idx, (data, target) in enumerate(memory_safe_loader):
                    data, target = data.to(self.device), target.to(self.device)
                    
                    optimizer.zero_grad()
                    output = self.model(data)
                    loss = criterion(output, target)
                    loss.backward()
                    optimizer.step()
                    
                    epoch_loss += loss.item()
                    num_batches += 1
            
            avg_train_loss = epoch_loss / num_batches if num_batches > 0 else 0.0
            history['train_loss'].append(avg_train_loss)
            
            # Validation phase
            self.model.eval()
            val_loss = 0.0
            correct = 0
            total = 0
            
            with torch.no_grad():
                for data, target in self.val_loader:
                    data, target = data.to(self.device), target.to(self.device)
                    output = self.model(data)
                    loss = criterion(output, target)
                    
                    val_loss += loss.item()
                    pred = output.argmax(dim=1, keepdim=True)
                    correct += pred.eq(target.view_as(pred)).sum().item()
                    total += target.size(0)
            
            avg_val_loss = val_loss / len(self.val_loader)
            val_acc = correct / total if total > 0 else 0.0
            
            history['val_loss'].append(avg_val_loss)
            history['val_acc'].append(val_acc)
            
            if val_acc > history['best_val_acc']:
                history['best_val_acc'] = val_acc
            
            # Get current epsilon
            epsilon = self.privacy_engine.get_epsilon(delta=self.dp_target_delta)
            
            self._log.info(f"Epoch {epoch+1}/{num_epochs} - "
                  f"Loss: {avg_train_loss:.4f}, Val Loss: {avg_val_loss:.4f}, "
                  f"Val Acc: {val_acc:.2%}, ε: {epsilon:.2f}")
            
            # Step scheduler
            if scheduler:
                scheduler.step()
        
        return history
    
    def evaluate(
        self,
        parameters: List[np.ndarray],
        config: Dict
    ) -> Tuple[float, int, Dict]:
        """
        Evaluate model locally.

        Uses test_loader (test/ folder) when available (UI path),
        falls back to val_loader (experiment/CSV path).

        Args:
            parameters: Model parameters to evaluate
            config: Evaluation configuration

        Returns:
            - Loss
            - Number of evaluation samples
            - Metrics dict
        """
        eval_loader = self.test_loader if self.test_loader is not None else self.val_loader
        eval_split = "test" if self.test_loader is not None else "val"
        self._log.info(f"Evaluating model on {eval_split} set...")

        # Set parameters
        self.set_parameters(parameters)

        # Evaluate
        self.model.eval()
        criterion = torch.nn.CrossEntropyLoss()

        total_loss = 0.0
        y_true, y_pred, y_probs = [], [], []

        with torch.no_grad():
            for inputs, labels in eval_loader:
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
        avg_loss = total_loss / len(eval_loader.dataset)
        num_samples = len(eval_loader.dataset)

        metrics_full = compute_metrics(y_true, y_pred, y_probs)

        # Filter only scalar metrics for Flower (no lists/arrays)
        metrics = {
            'accuracy': float(metrics_full.get('accuracy', 0)),
            'f1': float(metrics_full.get('f1', 0)),
            'precision': float(metrics_full.get('precision', 0)),
            'recall': float(metrics_full.get('recall', 0)),
            'auc': float(metrics_full.get('auc', 0) or 0),
            'specificity': float(metrics_full.get('specificity', 0)),
            'sensitivity': float(metrics_full.get('sensitivity', metrics_full.get('recall', 0))),
        }

        self._log.info(f"Evaluation results ({eval_split}):")
        self._log.step(f"Loss: {avg_loss:.4f}")
        self._log.step(f"Accuracy: {metrics.get('accuracy', 0):.4f}")
        self._log.step(f"F1: {metrics.get('f1', 0):.4f}")

        return avg_loss, num_samples, metrics


def get_last_training_metrics():
    """
    Get metrics from the last training round.
    
    Returns:
        Dict with training metrics or None if no training has occurred
    """
    global _last_training_metrics
    return _last_training_metrics


def start_flower_client(
    server_address: str,
    node_id: str,
    model_name: str,
    num_classes: int,
    dataset_path: str,
    device: str = "cpu",
    batch_size: int = 32,
    session_id: str = None,
    enable_ssl: bool = True,
    certificates_path: str = "/certificates",
    # Differential Privacy parameters
    enable_dp: bool = False,
    dp_target_epsilon: float = 1.0,
    dp_target_delta: float = 1e-5,
    dp_noise_multiplier: float = 1.0,
    dp_max_grad_norm: float = 1.0,
    dp_max_epochs: int = 10,
    # Split-uri fixe (NOU)
    splits_dir: str = None,
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
        session_id: FL session identifier (for model saving)        enable_ssl: Enable mTLS for secure communication
        certificates_path: Path to SSL certificates
        enable_dp: Enable Differential Privacy
        dp_target_epsilon: Target epsilon for DP
        dp_target_delta: Target delta for DP
        dp_noise_multiplier: Noise multiplier for DP
        dp_max_grad_norm: Maximum gradient norm for clipping
        dp_max_epochs: Maximum epochs for privacy accounting
    """
    log = get_logger(node_id)
    log.section(f"FED-MED-FL FLOWER CLIENT - {node_id}")
    log.step(f"Server: {server_address}")
    log.step(f"Model: {model_name}")
    log.step(f"Dataset: {dataset_path}")
    log.step(f"Device: {device}")
    log.step(f"SSL/TLS: {'Enabled (mTLS)' if enable_ssl else 'Disabled'}")
    log.step(f"Differential Privacy: {'Enabled' if enable_dp else 'Disabled'}")
    if enable_dp:
        log.step(f"Target ε: {dp_target_epsilon}")
        log.step(f"Target δ: {dp_target_delta}")
    
    # Create client
    client = FedMedClient(
        node_id=node_id,
        model_name=model_name,
        num_classes=num_classes,
        dataset_path=dataset_path,
        device=device,
        batch_size=batch_size,
        enable_signing=enable_ssl,  # Use same flag as SSL for now
        certificates_path=certificates_path,
        # DP parameters
        enable_dp=enable_dp,
        dp_target_epsilon=dp_target_epsilon,
        dp_target_delta=dp_target_delta,
        dp_noise_multiplier=dp_noise_multiplier,
        dp_max_grad_norm=dp_max_grad_norm,
        dp_max_epochs=dp_max_epochs,
        # Split-uri fixe (NOU)
        splits_dir=splits_dir,
    )
    
    # Configure SSL/TLS if enabled
    root_certificates = None
    if enable_ssl:
        from pathlib import Path
        cert_path = Path(certificates_path) / "nodes" / node_id
        
        # Check if certificates exist
        client_cert = cert_path / "client-cert.pem"
        client_key = cert_path / "client-key.pem"
        ca_cert = cert_path / "ca-cert.pem"
        
        if client_cert.exists() and client_key.exists() and ca_cert.exists():
            log.info("Configuring mTLS...")
            log.step(f"Client cert: {client_cert}")
            log.step(f"Client key: {client_key}")
            log.step(f"CA cert: {ca_cert}")
            root_certificates = ca_cert.read_bytes()
            log.ok("mTLS configured successfully")
        else:
            log.warn(f"SSL certificates not found at {cert_path}")
            log.warn("Falling back to insecure connection")
            enable_ssl = False

    log.info(f"Connecting to Flower server at {server_address}...")

    try:
        if enable_ssl and root_certificates:
            fl.client.start_numpy_client(
                server_address=server_address,
                client=client,
                root_certificates=root_certificates,
            )
        else:
            fl.client.start_numpy_client(
                server_address=server_address,
                client=client,
            )

        log.ok("Disconnected from server")

        if session_id:
            from node_core import save_model
            model_id = f"{model_name}_{session_id}_flower"
            model_dir = Path("/storage/models/candidate")
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = model_dir / f"{model_id}.pt"

            log.info(f"Saving trained model to {model_path}...")

            global _last_training_metrics
            metrics = _last_training_metrics

            metadata = {
                'session_id': session_id,
                'model_name': model_name,
                'training_type': 'federated',
                'node_id': node_id,
                'metrics': metrics
            }

            save_model(client.model, str(model_path), metadata)
            log.ok("Model saved successfully")
        else:
            log.warn("session_id not provided — trained model will NOT be saved to disk")

    except KeyboardInterrupt:
        log.info("Interrupted by user")
    except Exception as e:
        log.fail(f"Error: {e}")
        raise


def main():
    """Main entry point."""
    # Get configuration from environment
    server_address = os.getenv("FLOWER_SERVER", "central:8080")
    node_id = os.getenv("NODE_ID", "node1")
    model_name = os.getenv("MODEL_NAME", "resnet18")
    num_classes = int(os.getenv("NUM_CLASSES", "2"))
    dataset_path = os.getenv("DATASET_PATH")
    device = os.getenv("DEVICE", "cpu")
    batch_size = int(os.getenv("BATCH_SIZE", "32"))
    enable_ssl = os.getenv("ENABLE_SSL", "true").lower() == "true"
    certificates_path = os.getenv("CERTIFICATES_PATH", "/certificates")
    
    # Differential Privacy configuration
    enable_dp = os.getenv("ENABLE_DP", "false").lower() == "true"
    dp_target_epsilon = float(os.getenv("DP_TARGET_EPSILON", "1.0"))
    dp_target_delta = float(os.getenv("DP_TARGET_DELTA", "1e-5"))
    dp_noise_multiplier = float(os.getenv("DP_NOISE_MULTIPLIER", "1.0"))
    dp_max_grad_norm = float(os.getenv("DP_MAX_GRAD_NORM", "1.0"))
    dp_max_epochs = int(os.getenv("DP_MAX_EPOCHS", "10"))
    
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
        enable_ssl=enable_ssl,
        certificates_path=certificates_path,
        # DP parameters
        enable_dp=enable_dp,
        dp_target_epsilon=dp_target_epsilon,
        dp_target_delta=dp_target_delta,
        dp_noise_multiplier=dp_noise_multiplier,
        dp_max_grad_norm=dp_max_grad_norm,
        dp_max_epochs=dp_max_epochs,
    )


if __name__ == "__main__":
    main()

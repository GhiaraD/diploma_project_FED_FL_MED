"""
Configurație pytest pentru testele Fed-Med-FL.

Stub-urile pentru dependențe externe (flwr, node_core) sunt instalate
aici, înainte de orice import de modul de test, garantând ordinea corectă
indiferent de ordinea de colectare a fișierelor de test.
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock
import torch

_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# sys.path — toate serviciile accesibile ca pachete Python
# ---------------------------------------------------------------------------

sys.path.insert(0, str(_ROOT / "shared" / "python" / "node_core"))
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT / "services" / "central"))
sys.path.insert(0, str(_ROOT / "services" / "node" / "worker"))


# ---------------------------------------------------------------------------
# Stub pentru flwr — nu e instalat în venv-ul de test
# ---------------------------------------------------------------------------

def _install_flwr_stub():
    if "flwr" in sys.modules:
        return

    flwr = types.ModuleType("flwr")
    flwr_client = types.ModuleType("flwr.client")
    flwr_common = types.ModuleType("flwr.common")

    class _NumPyClient:
        pass

    flwr_client.NumPyClient = _NumPyClient
    flwr_client.start_numpy_client = MagicMock()
    flwr.client = flwr_client
    flwr.common = flwr_common

    sys.modules["flwr"] = flwr
    sys.modules["flwr.client"] = flwr_client
    sys.modules["flwr.common"] = flwr_common


# ---------------------------------------------------------------------------
# Stub pentru node_core — versiunea completă folosită de flower_client
# Testele care au nevoie de comportament specific pot patch-ui individual.
# ---------------------------------------------------------------------------

def _make_tiny_model():
    return torch.nn.Sequential(
        torch.nn.Linear(4, 4),
        torch.nn.Linear(4, 2),
    )


def _install_node_core_stub():
    if "node_core" in sys.modules:
        return

    node_core = types.ModuleType("node_core")
    node_core.get_model = MagicMock(return_value=_make_tiny_model())
    node_core.load_dataset = MagicMock()
    node_core.create_dataloaders = MagicMock(return_value=(MagicMock(), MagicMock()))
    node_core.train_model = MagicMock(return_value={
        "train_loss": [0.5], "val_loss": [0.4],
        "best_val_acc": 0.85, "epochs_trained": 1,
    })
    node_core.get_optimizer = MagicMock(return_value=MagicMock())
    node_core.get_scheduler = MagicMock(return_value=MagicMock())
    node_core.compute_metrics = MagicMock(return_value={
        "accuracy": 0.85, "f1": 0.83, "precision": 0.84,
        "recall": 0.82, "auc": 0.90, "sensitivity": 0.82,
        "specificity": 0.88, "pr_auc": 0.89,
    })
    mock_signer = MagicMock()
    mock_signer.is_ready.return_value = False
    node_core.create_payload_signer = MagicMock(return_value=mock_signer)
    node_core.sign_model_parameters = MagicMock(return_value=([], {"signed": False}))
    node_core.get_logger = MagicMock(return_value=MagicMock())
    node_core.get_val_transforms = MagicMock(return_value=None)
    node_core.save_model = MagicMock()
    node_core.configure_fastapi_ssl = MagicMock(return_value=None)
    node_core.get_uvicorn_config = MagicMock(return_value={})

    sys.modules["node_core"] = node_core


_install_flwr_stub()
_install_node_core_stub()

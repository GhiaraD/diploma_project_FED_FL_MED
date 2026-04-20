"""
Unit tests for Flower Strategy (FedMedStrategy)
"""
import pytest
import torch
import torch.nn as nn
import tempfile
import shutil
from pathlib import Path

from node_core import FedMedStrategy, create_fedmed_strategy, get_model


class SimpleNet(nn.Module):
    """Simple model for testing."""
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(10, 2)
    
    def forward(self, x):
        return self.fc(x)


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_strategy_initialization(temp_storage):
    """Test FedMedStrategy initialization."""
    strategy = FedMedStrategy(
        model_name="resnet18",
        num_classes=2,
        storage_path=temp_storage,
        save_models=True
    )
    
    assert strategy.model_name == "resnet18"
    assert strategy.num_classes == 2
    assert strategy.save_models == True
    assert strategy.current_round == 0
    assert len(strategy.round_history) == 0
    
    # Check that model is initialized
    assert strategy.model is not None
    assert isinstance(strategy.model, nn.Module)


def test_create_fedmed_strategy(temp_storage):
    """Test create_fedmed_strategy helper function."""
    strategy = create_fedmed_strategy(
        model_name="resnet18",
        num_classes=2,
        storage_path=temp_storage,
        min_clients=2
    )
    
    assert isinstance(strategy, FedMedStrategy)
    assert strategy.model_name == "resnet18"


def test_initialize_parameters(temp_storage):
    """Test initialize_parameters method."""
    strategy = FedMedStrategy(
        model_name="resnet18",
        num_classes=2,
        storage_path=temp_storage,
        save_models=False  # Don't save for this test
    )
    
    # Initialize parameters
    parameters = strategy.initialize_parameters(client_manager=None)
    
    # Check that parameters are returned
    assert parameters is not None
    
    # Check that initial model is saved if save_models=True
    strategy_with_save = FedMedStrategy(
        model_name="resnet18",
        num_classes=2,
        storage_path=temp_storage,
        save_models=True
    )
    
    parameters = strategy_with_save.initialize_parameters(client_manager=None)
    
    # Check that model file exists
    model_path = Path(temp_storage) / "models" / "global_R-0.pt"
    assert model_path.exists()


def test_round_history_tracking(temp_storage):
    """Test that round history is tracked correctly."""
    strategy = FedMedStrategy(
        model_name="resnet18",
        num_classes=2,
        storage_path=temp_storage,
        save_models=False
    )
    
    # Initially empty
    assert len(strategy.get_round_history()) == 0
    
    # Simulate adding round history (normally done by aggregate_fit)
    strategy.round_history.append({
        'round': 1,
        'num_clients': 3,
        'metrics': {'accuracy': 0.85}
    })
    
    history = strategy.get_round_history()
    assert len(history) == 1
    assert history[0]['round'] == 1
    assert history[0]['num_clients'] == 3


def test_get_current_model_path(temp_storage):
    """Test get_current_model_path method."""
    strategy = FedMedStrategy(
        model_name="resnet18",
        num_classes=2,
        storage_path=temp_storage,
        save_models=True
    )
    
    # Initially no model (round 0)
    assert strategy.get_current_model_path() is None
    
    # After initializing
    strategy.initialize_parameters(client_manager=None)
    
    # Still None because current_round is 0
    assert strategy.get_current_model_path() is None
    
    # Simulate round 1
    strategy.current_round = 1
    
    # Create dummy model file
    model_path = Path(temp_storage) / "models" / "global_R-1.pt"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({}, model_path)
    
    # Now should return path
    result = strategy.get_current_model_path()
    assert result is not None
    assert "global_R-1.pt" in result


def test_save_global_model(temp_storage):
    """Test _save_global_model method."""
    strategy = FedMedStrategy(
        model_name="resnet18",
        num_classes=2,
        storage_path=temp_storage,
        save_models=True
    )
    
    # Get model parameters
    parameters = [val.cpu().numpy() for val in strategy.model.state_dict().values()]
    
    # Save model
    strategy._save_global_model(parameters, round_num=1)
    
    # Check that file exists
    model_path = Path(temp_storage) / "models" / "global_R-1.pt"
    assert model_path.exists()
    
    # Load and verify
    checkpoint = torch.load(model_path)
    assert 'model_state_dict' in checkpoint
    assert 'metadata' in checkpoint
    assert checkpoint['metadata']['round'] == 1
    assert checkpoint['metadata']['model_name'] == "resnet18"


def test_strategy_with_different_models(temp_storage):
    """Test strategy with different model architectures."""
    models = ["resnet18", "densenet121", "efficientnet_b0"]
    
    for model_name in models:
        strategy = FedMedStrategy(
            model_name=model_name,
            num_classes=2,
            storage_path=temp_storage,
            save_models=False
        )
        
        assert strategy.model_name == model_name
        assert strategy.model is not None


def test_strategy_storage_directories(temp_storage):
    """Test that storage directories are created."""
    strategy = FedMedStrategy(
        model_name="resnet18",
        num_classes=2,
        storage_path=temp_storage,
        save_models=True
    )
    
    # Check that models directory exists
    models_dir = Path(temp_storage) / "models"
    assert models_dir.exists()
    assert models_dir.is_dir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

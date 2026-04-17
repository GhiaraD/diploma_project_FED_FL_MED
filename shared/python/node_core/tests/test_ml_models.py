"""
Unit tests for ml_models module.
"""
import pytest
import torch
from node_core import get_model, get_final_conv_layer, save_model, load_model


def test_get_model_resnet18():
    """Test ResNet18 model creation."""
    model = get_model('resnet18', num_classes=2, pretrained=False)
    assert model is not None
    
    # Test output shape
    x = torch.randn(1, 3, 224, 224)
    output = model(x)
    assert output.shape == (1, 2)


def test_get_model_densenet121():
    """Test DenseNet121 model creation."""
    model = get_model('densenet121', num_classes=2, pretrained=False)
    assert model is not None
    
    x = torch.randn(1, 3, 224, 224)
    output = model(x)
    assert output.shape == (1, 2)


def test_get_model_efficientnet():
    """Test EfficientNet-B0 model creation."""
    model = get_model('efficientnet_b0', num_classes=2, pretrained=False)
    assert model is not None
    
    x = torch.randn(1, 3, 224, 224)
    output = model(x)
    assert output.shape == (1, 2)


def test_get_model_invalid():
    """Test invalid model name raises error."""
    with pytest.raises(ValueError):
        get_model('invalid_model')


def test_get_final_conv_layer():
    """Test getting final conv layer for Grad-CAM."""
    model = get_model('resnet18', pretrained=False)
    layer = get_final_conv_layer(model, 'resnet18')
    assert layer is not None


def test_save_and_load_model(tmp_path):
    """Test model saving and loading."""
    # Create and save model
    model = get_model('resnet18', num_classes=2, pretrained=False)
    save_path = tmp_path / "test_model.pt"
    
    metadata = {'test': 'value', 'accuracy': 0.95}
    save_model(model, str(save_path), metadata)
    
    # Load model
    loaded_model, loaded_metadata = load_model('resnet18', str(save_path))
    
    assert loaded_model is not None
    assert loaded_metadata['test'] == 'value'
    assert loaded_metadata['accuracy'] == 0.95
    
    # Test that loaded model works
    x = torch.randn(1, 3, 224, 224)
    output = loaded_model(x)
    assert output.shape == (1, 2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

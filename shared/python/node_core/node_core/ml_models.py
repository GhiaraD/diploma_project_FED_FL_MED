"""
ML Models Module - Model architecture definitions and loading utilities.
"""
import torch
import torch.nn as nn
from torchvision import models
from torchvision.models import (
    resnet18, densenet121, efficientnet_b0,
    ResNet18_Weights, DenseNet121_Weights, EfficientNet_B0_Weights
)


def get_model(model_name: str, num_classes: int = 2, pretrained: bool = True) -> nn.Module:
    """
    Load a pretrained model and modify the final layer for binary classification.
    
    Args:
        model_name: One of 'resnet18', 'densenet121', 'efficientnet_b0'
        num_classes: Number of output classes (default: 2 for NORMAL/PNEUMONIA)
        pretrained: Whether to use pretrained ImageNet weights
        
    Returns:
        Modified PyTorch model ready for training
        
    Raises:
        ValueError: If model_name is not supported
    """
    model_name = model_name.lower()
    
    if model_name == "resnet18":
        weights = ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        model = resnet18(weights=weights)
        # Modify final fully connected layer
        in_features = model.fc.in_features
        model.fc = nn.Linear(in_features, num_classes)
        
    elif model_name == "densenet121":
        weights = DenseNet121_Weights.IMAGENET1K_V1 if pretrained else None
        model = densenet121(weights=weights)
        # Modify classifier layer
        in_features = model.classifier.in_features
        model.classifier = nn.Linear(in_features, num_classes)
        
    elif model_name == "efficientnet_b0":
        weights = EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
        model = efficientnet_b0(weights=weights)
        # Modify classifier layer
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, num_classes)
        
    else:
        raise ValueError(
            f"Unsupported model: {model_name}. "
            f"Choose from: 'resnet18', 'densenet121', 'efficientnet_b0'"
        )
    
    return model


def get_final_conv_layer(model: nn.Module, model_name: str) -> nn.Module:
    """
    Get the final convolutional layer for Grad-CAM visualization.
    
    Args:
        model: PyTorch model
        model_name: Model architecture name
        
    Returns:
        Final convolutional layer module
        
    Raises:
        ValueError: If model_name is not supported
    """
    model_name = model_name.lower()
    
    if model_name == "resnet18":
        return model.layer4[1].conv2
    elif model_name == "densenet121":
        return model.features[-1]
    elif model_name == "efficientnet_b0":
        return model.features[-1]
    else:
        raise ValueError(f"Unsupported model for Grad-CAM: {model_name}")


def save_model(model: nn.Module, path: str, metadata: dict = None):
    """
    Save model state dict and optional metadata.
    
    Args:
        model: PyTorch model to save
        path: File path to save to (e.g., 'model.pt')
        metadata: Optional dict with training info (round_id, metrics, etc.)
    """
    save_dict = {
        'state_dict': model.state_dict(),
    }
    if metadata:
        save_dict['metadata'] = metadata
    
    torch.save(save_dict, path)


def load_model(model_name: str, path: str, device: str = 'cpu') -> tuple:
    """
    Load a saved model from disk.
    
    Args:
        model_name: Model architecture name
        path: Path to saved model file
        device: Device to load model to ('cpu' or 'cuda')
        
    Returns:
        Tuple of (model, metadata_dict)
    """
    checkpoint = torch.load(path, map_location=device)
    
    # Handle both old format (just state_dict) and new format (dict with metadata)
    if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
        metadata = checkpoint.get('metadata', {})
    else:
        state_dict = checkpoint
        metadata = {}
    
    model = get_model(model_name, pretrained=False)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    
    return model, metadata


def count_parameters(model: nn.Module) -> int:
    """
    Count total trainable parameters in model.
    
    Args:
        model: PyTorch model
        
    Returns:
        Number of trainable parameters
    """
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

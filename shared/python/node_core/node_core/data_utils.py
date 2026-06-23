"""
Data Utilities Module - Dataset loading, transformations, and preprocessing.
"""
import os
from typing import Tuple, Optional
import torch
from torch.utils.data import DataLoader, Dataset, Subset, ConcatDataset
from torchvision import transforms
from torchvision.datasets import ImageFolder
from sklearn.model_selection import StratifiedKFold
import numpy as np


# Standard ImageNet normalization values
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def get_train_transforms(image_size: int = 224) -> transforms.Compose:
    """
    Get training data augmentation transforms.
    
    Args:
        image_size: Target image size (default: 224 for ImageNet models)
        
    Returns:
        Composed transforms for training
    """
    return transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=10),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])


def get_val_transforms(image_size: int = 224) -> transforms.Compose:
    """
    Get validation/test transforms (no augmentation).
    
    Args:
        image_size: Target image size
        
    Returns:
        Composed transforms for validation/testing
    """
    return transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])


def load_dataset(
    data_dir: str,
    split: str = 'train',
    image_size: int = 224
) -> ImageFolder:
    """
    Load chest X-ray dataset from directory.
    
    Expected structure:
        data_dir/
            train/
                NORMAL/
                PNEUMONIA/
            val/
                NORMAL/
                PNEUMONIA/
            test/
                NORMAL/
                PNEUMONIA/
    
    Args:
        data_dir: Root directory containing train/val/test folders
        split: One of 'train', 'val', 'test'
        image_size: Target image size
        
    Returns:
        ImageFolder dataset with appropriate transforms
    """
    split_dir = os.path.join(data_dir, split)
    
    if not os.path.exists(split_dir):
        raise ValueError(f"Directory not found: {split_dir}")
    
    # Use augmentation for training, standard transforms for val/test
    if split == 'train':
        transform = get_train_transforms(image_size)
    else:
        transform = get_val_transforms(image_size)
    
    dataset = ImageFolder(root=split_dir, transform=transform)
    
    return dataset


def create_stratified_folds(
    dataset: Dataset,
    n_splits: int = 5,
    random_state: int = 42
) -> list:
    """
    Create stratified K-fold splits for cross-validation.
    
    Args:
        dataset: PyTorch dataset (must have .targets attribute)
        n_splits: Number of folds
        random_state: Random seed for reproducibility
        
    Returns:
        List of (train_indices, val_indices) tuples
    """
    # Extract labels from dataset
    if hasattr(dataset, 'targets'):
        labels = np.array(dataset.targets)
    elif hasattr(dataset, 'labels'):
        labels = np.array(dataset.labels)
    else:
        raise ValueError("Dataset must have 'targets' or 'labels' attribute")
    
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    
    folds = []
    for train_idx, val_idx in skf.split(np.zeros(len(labels)), labels):
        folds.append((train_idx.tolist(), val_idx.tolist()))
    
    return folds


def create_dataloaders(
    train_dataset: Dataset,
    val_dataset: Dataset,
    batch_size: int = 32,
    num_workers: int = 4
) -> Tuple[DataLoader, DataLoader]:
    """
    Create train and validation DataLoaders.
    
    Args:
        train_dataset: Training dataset
        val_dataset: Validation dataset
        batch_size: Batch size for both loaders
        num_workers: Number of worker processes for data loading
        
    Returns:
        Tuple of (train_loader, val_loader)
    """
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True
    )
    
    return train_loader, val_loader


def get_class_distribution(dataset: Dataset) -> dict:
    """
    Get class distribution statistics from dataset.
    
    Args:
        dataset: PyTorch dataset
        
    Returns:
        Dict with class counts and percentages
    """
    if hasattr(dataset, 'targets'):
        labels = np.array(dataset.targets)
    elif hasattr(dataset, 'labels'):
        labels = np.array(dataset.labels)
    else:
        raise ValueError("Dataset must have 'targets' or 'labels' attribute")
    
    unique, counts = np.unique(labels, return_counts=True)
    total = len(labels)
    
    distribution = {
        'total_samples': total,
        'classes': {}
    }
    
    for cls, count in zip(unique, counts):
        distribution['classes'][int(cls)] = {
            'count': int(count),
            'percentage': float(count / total * 100)
        }
    
    return distribution


def denormalize_image(tensor: torch.Tensor) -> torch.Tensor:
    """
    Denormalize image tensor for visualization.
    
    Args:
        tensor: Normalized image tensor (C, H, W)
        
    Returns:
        Denormalized tensor in [0, 1] range
    """
    mean = torch.tensor(IMAGENET_MEAN).view(3, 1, 1)
    std = torch.tensor(IMAGENET_STD).view(3, 1, 1)
    
    denorm = tensor * std + mean
    denorm = torch.clamp(denorm, 0, 1)
    
    return denorm

"""
ML Inference Module - Model inference and Grad-CAM visualization.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from PIL import Image
from typing import Tuple, List, Dict
import cv2


def predict_single_image(
    model: nn.Module,
    image_tensor: torch.Tensor,
    device: str = 'cpu'
) -> Tuple[int, float, np.ndarray]:
    """
    Run inference on a single image.
    
    Args:
        model: Trained PyTorch model
        image_tensor: Preprocessed image tensor (C, H, W)
        device: Device to run inference on
        
    Returns:
        Tuple of (predicted_class, confidence, probabilities)
    """
    model.eval()
    
    with torch.no_grad():
        # Add batch dimension
        input_batch = image_tensor.unsqueeze(0).to(device)
        
        # Forward pass
        outputs = model(input_batch)
        
        # Get probabilities
        probs = torch.softmax(outputs, dim=1)
        probs_np = probs.cpu().numpy()[0]
        
        # Get prediction
        pred_class = torch.argmax(probs, dim=1).item()
        confidence = probs[0, pred_class].item()
    
    return pred_class, confidence, probs_np


def predict_batch(
    model: nn.Module,
    image_tensors: torch.Tensor,
    device: str = 'cpu'
) -> Tuple[List[int], List[float], np.ndarray]:
    """
    Run inference on a batch of images.
    
    Args:
        model: Trained PyTorch model
        image_tensors: Batch of preprocessed images (B, C, H, W)
        device: Device to run inference on
        
    Returns:
        Tuple of (predicted_classes, confidences, all_probabilities)
    """
    model.eval()
    
    with torch.no_grad():
        inputs = image_tensors.to(device)
        outputs = model(inputs)
        
        probs = torch.softmax(outputs, dim=1)
        pred_classes = torch.argmax(probs, dim=1)
        
        # Get confidence for each prediction
        confidences = []
        for i, pred_cls in enumerate(pred_classes):
            confidences.append(probs[i, pred_cls].item())
        
        pred_classes = pred_classes.cpu().numpy().tolist()
        probs_np = probs.cpu().numpy()
    
    return pred_classes, confidences, probs_np


class GradCAM:
    """
    Grad-CAM: Visual Explanations from Deep Networks via Gradient-based Localization.
    
    Paper: https://arxiv.org/abs/1610.02391
    """
    
    def __init__(self, model: nn.Module, target_layer: nn.Module):
        """
        Args:
            model: Trained PyTorch model
            target_layer: Target convolutional layer for Grad-CAM
        """
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None
        
        # Register hooks
        self.forward_hook = target_layer.register_forward_hook(self._forward_hook)
        self.backward_hook = target_layer.register_full_backward_hook(self._backward_hook)
    
    def _forward_hook(self, module, input, output):
        """Save activations during forward pass."""
        self.activations = output.detach()
    
    def _backward_hook(self, module, grad_input, grad_output):
        """Save gradients during backward pass."""
        self.gradients = grad_output[0].detach()
    
    def generate(
        self,
        input_tensor: torch.Tensor,
        target_class: int = None,
        device: str = 'cpu'
    ) -> Tuple[np.ndarray, int]:
        """
        Generate Grad-CAM heatmap for input image.
        
        Args:
            input_tensor: Preprocessed image tensor (C, H, W)
            target_class: Target class for visualization (if None, uses predicted class)
            device: Device to run on
            
        Returns:
            Tuple of (heatmap, predicted_class)
        """
        self.model.eval()
        
        # Forward pass
        input_batch = input_tensor.unsqueeze(0).to(device)
        input_batch.requires_grad = True
        
        output = self.model(input_batch)
        
        # Get predicted class if not specified
        if target_class is None:
            target_class = output.argmax(dim=1).item()
        
        # Backward pass for target class
        self.model.zero_grad()
        class_score = output[0, target_class]
        class_score.backward()
        
        # Get gradients and activations
        gradients = self.gradients  # (B, C, H, W)
        activations = self.activations  # (B, C, H, W)
        
        # Global average pooling on gradients
        weights = gradients.mean(dim=(2, 3), keepdim=True)  # (B, C, 1, 1)
        
        # Weighted combination of activation maps
        cam = (weights * activations).sum(dim=1).squeeze()  # (H, W)
        
        # Apply ReLU to focus on positive contributions
        cam = F.relu(cam)
        
        # Normalize to [0, 1]
        cam = cam.cpu().numpy()
        cam = cam - cam.min()
        cam = cam / (cam.max() + 1e-8)
        
        return cam, target_class
    
    def generate_and_resize(
        self,
        input_tensor: torch.Tensor,
        target_size: Tuple[int, int],
        target_class: int = None,
        device: str = 'cpu'
    ) -> Tuple[np.ndarray, int]:
        """
        Generate Grad-CAM and resize to target size.
        
        Args:
            input_tensor: Preprocessed image tensor (C, H, W)
            target_size: (height, width) to resize heatmap to
            target_class: Target class for visualization
            device: Device to run on
            
        Returns:
            Tuple of (resized_heatmap, predicted_class)
        """
        cam, pred_class = self.generate(input_tensor, target_class, device)
        
        # Resize to target size
        cam_resized = cv2.resize(cam, (target_size[1], target_size[0]))
        
        return cam_resized, pred_class
    
    def __del__(self):
        """Remove hooks when object is destroyed."""
        self.forward_hook.remove()
        self.backward_hook.remove()


def apply_colormap_on_image(
    image: np.ndarray,
    heatmap: np.ndarray,
    alpha: float = 0.4,
    colormap: int = cv2.COLORMAP_JET
) -> np.ndarray:
    """
    Apply heatmap overlay on image.
    
    Args:
        image: Original image (H, W, 3) in [0, 1] range
        heatmap: Grad-CAM heatmap (H, W) in [0, 1] range
        alpha: Transparency of heatmap overlay
        colormap: OpenCV colormap to use
        
    Returns:
        Overlayed image (H, W, 3) in [0, 1] range
    """
    # Convert heatmap to uint8
    heatmap_uint8 = np.uint8(255 * heatmap)
    
    # Apply colormap
    heatmap_colored = cv2.applyColorMap(heatmap_uint8, colormap)
    heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
    heatmap_colored = heatmap_colored.astype(np.float32) / 255.0
    
    # Ensure image is in correct format
    if image.max() > 1.0:
        image = image / 255.0
    
    # Blend
    overlay = heatmap_colored * alpha + image * (1 - alpha)
    overlay = np.clip(overlay, 0, 1)
    
    return overlay


def save_gradcam_overlay(
    image: np.ndarray,
    heatmap: np.ndarray,
    output_path: str,
    alpha: float = 0.4
):
    """
    Save Grad-CAM overlay to file.
    
    Args:
        image: Original image (H, W, 3)
        heatmap: Grad-CAM heatmap (H, W)
        output_path: Path to save overlay image
        alpha: Transparency of heatmap
    """
    overlay = apply_colormap_on_image(image, heatmap, alpha)
    
    # Convert to uint8 for saving
    overlay_uint8 = np.uint8(255 * overlay)
    
    # Save using PIL
    Image.fromarray(overlay_uint8).save(output_path)


def batch_inference_with_gradcam(
    model: nn.Module,
    images: List[torch.Tensor],
    target_layer: nn.Module,
    device: str = 'cpu',
    target_class: int = None
) -> List[Dict]:
    """
    Run inference with Grad-CAM on multiple images.
    
    Args:
        model: Trained model
        images: List of preprocessed image tensors
        target_layer: Target layer for Grad-CAM
        device: Device to run on
        target_class: Optional target class for all images
        
    Returns:
        List of dicts with predictions and heatmaps
    """
    gradcam = GradCAM(model, target_layer)
    results = []
    
    for img_tensor in images:
        # Prediction
        pred_class, confidence, probs = predict_single_image(model, img_tensor, device)
        
        # Grad-CAM
        target = target_class if target_class is not None else pred_class
        heatmap, _ = gradcam.generate(img_tensor, target, device)
        
        results.append({
            'predicted_class': pred_class,
            'confidence': confidence,
            'probabilities': probs.tolist(),
            'heatmap': heatmap,
            'target_class': target
        })
    
    return results

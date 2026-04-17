"""
Example: Running inference with Grad-CAM visualization.

This demonstrates how to use the inference and Grad-CAM modules.
"""
import os
import sys
import torch
from PIL import Image
import matplotlib.pyplot as plt

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from node_core import (
    load_model,
    get_final_conv_layer,
    predict_single_image,
    GradCAM,
    get_val_transforms,
    apply_colormap_on_image,
    denormalize_image
)


def main():
    # Configuration
    MODEL_PATH = "resnet18_trained.pt"
    MODEL_NAME = "resnet18"
    IMAGE_PATH = os.path.expanduser("~/data/chest_xray/test/PNEUMONIA/person1_virus_6.jpeg")
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    
    CLASS_NAMES = ['NORMAL', 'PNEUMONIA']
    
    print(f"Using device: {DEVICE}")
    print(f"Loading model from: {MODEL_PATH}")
    print(f"Processing image: {IMAGE_PATH}")
    print("=" * 60)
    
    # Load model
    print("\n🔧 Loading model...")
    model, metadata = load_model(MODEL_NAME, MODEL_PATH, device=DEVICE)
    print(f"Model metadata: {metadata}")
    
    # Load and preprocess image
    print("\n📷 Loading image...")
    image = Image.open(IMAGE_PATH).convert('RGB')
    transform = get_val_transforms(image_size=224)
    img_tensor = transform(image)
    
    # Run inference
    print("\n🔮 Running inference...")
    pred_class, confidence, probs = predict_single_image(model, img_tensor, DEVICE)
    
    print(f"\nPrediction: {CLASS_NAMES[pred_class]}")
    print(f"Confidence: {confidence:.2%}")
    print(f"Probabilities: NORMAL={probs[0]:.4f}, PNEUMONIA={probs[1]:.4f}")
    
    # Generate Grad-CAM
    print("\n🎨 Generating Grad-CAM...")
    target_layer = get_final_conv_layer(model, MODEL_NAME)
    gradcam = GradCAM(model, target_layer)
    
    heatmap, _ = gradcam.generate_and_resize(
        img_tensor,
        target_size=(image.size[1], image.size[0]),
        device=DEVICE
    )
    
    # Visualize
    print("\n📊 Creating visualization...")
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    # Original image
    axes[0].imshow(image)
    axes[0].set_title("Original X-Ray")
    axes[0].axis('off')
    
    # Heatmap
    axes[1].imshow(heatmap, cmap='jet')
    axes[1].set_title("Grad-CAM Heatmap")
    axes[1].axis('off')
    
    # Overlay
    import numpy as np
    image_np = np.array(image).astype(np.float32) / 255.0
    overlay = apply_colormap_on_image(image_np, heatmap, alpha=0.4)
    axes[2].imshow(overlay)
    axes[2].set_title(f"Overlay - {CLASS_NAMES[pred_class]} ({confidence:.1%})")
    axes[2].axis('off')
    
    plt.tight_layout()
    
    # Save
    output_path = "gradcam_result.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n💾 Visualization saved to: {output_path}")
    
    plt.show()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Create minimal test dataset for FL workflow testing.

Creates synthetic chest X-ray images (black/white patterns) for quick testing.
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont
import zipfile
import random

def create_synthetic_xray(width=224, height=224, label="NORMAL", index=0):
    """Create a synthetic X-ray image with patterns."""
    # Create grayscale image
    img = Image.new('L', (width, height), color=128)
    draw = ImageDraw.Draw(img)
    
    if label == "NORMAL":
        # Normal: lighter, more uniform
        for _ in range(50):
            x = random.randint(0, width)
            y = random.randint(0, height)
            r = random.randint(10, 30)
            brightness = random.randint(150, 200)
            draw.ellipse([x-r, y-r, x+r, y+r], fill=brightness)
    else:
        # Pneumonia: darker patches (infiltrates)
        for _ in range(80):
            x = random.randint(0, width)
            y = random.randint(0, height)
            r = random.randint(15, 40)
            brightness = random.randint(60, 120)
            draw.ellipse([x-r, y-r, x+r, y+r], fill=brightness)
    
    # Add some noise
    pixels = img.load()
    for _ in range(1000):
        x = random.randint(0, width-1)
        y = random.randint(0, height-1)
        noise = random.randint(-20, 20)
        pixels[x, y] = max(0, min(255, pixels[x, y] + noise))
    
    return img


def create_dataset_zip(output_path, num_normal=50, num_pneumonia=50):
    """Create a ZIP file with synthetic dataset."""
    temp_dir = "/tmp/test_dataset"
    os.makedirs(f"{temp_dir}/NORMAL", exist_ok=True)
    os.makedirs(f"{temp_dir}/PNEUMONIA", exist_ok=True)
    
    print(f"Creating {num_normal} NORMAL images...")
    for i in range(num_normal):
        img = create_synthetic_xray(label="NORMAL", index=i)
        img.save(f"{temp_dir}/NORMAL/normal_{i:04d}.jpg", quality=85)
    
    print(f"Creating {num_pneumonia} PNEUMONIA images...")
    for i in range(num_pneumonia):
        img = create_synthetic_xray(label="PNEUMONIA", index=i)
        img.save(f"{temp_dir}/PNEUMONIA/pneumonia_{i:04d}.jpg", quality=85)
    
    print(f"Creating ZIP: {output_path}")
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    print(f"✓ Dataset created: {output_path}")
    print(f"  - {num_normal} NORMAL images")
    print(f"  - {num_pneumonia} PNEUMONIA images")
    print(f"  - Total: {num_normal + num_pneumonia} images")


if __name__ == "__main__":
    # Create 3 different datasets for 3 nodes
    datasets = [
        ("test_dataset_node1.zip", 40, 60),  # Node1: more pneumonia
        ("test_dataset_node2.zip", 50, 50),  # Node2: balanced
        ("test_dataset_node3.zip", 60, 40),  # Node3: more normal
    ]
    
    for filename, num_normal, num_pneumonia in datasets:
        create_dataset_zip(filename, num_normal, num_pneumonia)
        print()
    
    print("✓ All test datasets created!")
    print("\nUsage:")
    print("  Upload test_dataset_node1.zip to Node1 via UI")
    print("  Upload test_dataset_node2.zip to Node2 via UI")
    print("  Upload test_dataset_node3.zip to Node3 via UI")

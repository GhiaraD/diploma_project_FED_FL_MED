#!/usr/bin/env python3
"""
Split TRAIN dataset across 3 nodes for Federated Learning.
Each node gets ~33% of train data.
"""

import os
import shutil
from pathlib import Path
import random

def split_train_dataset(source_train, output_base, num_nodes=3, seed=42):
    """Split train dataset across nodes."""
    random.seed(seed)
    
    source_train = Path(source_train)
    output_base = Path(output_base)
    
    print("=" * 70)
    print("Federated Learning Dataset Split - TRAIN ONLY")
    print("=" * 70)
    print(f"Source: {source_train}")
    print(f"Output: {output_base}")
    print(f"Nodes: {num_nodes}")
    print(f"Seed: {seed}")
    print()
    
    # Process each class
    for class_name in ['NORMAL', 'PNEUMONIA']:
        class_path = source_train / class_name
        
        if not class_path.exists():
            print(f"⚠️  {class_name}/ not found, skipping...")
            continue
        
        # Get all image files
        image_files = sorted([f for f in os.listdir(class_path) 
                             if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        
        total_images = len(image_files)
        print(f"▶ {class_name}: {total_images} images")
        
        # Shuffle for random distribution
        random.shuffle(image_files)
        
        # Calculate split sizes
        chunk_size = total_images // num_nodes
        
        # Split and copy to each node
        for node_idx in range(1, num_nodes + 1):
            start_idx = (node_idx - 1) * chunk_size
            # Last node gets remaining images
            end_idx = start_idx + chunk_size if node_idx < num_nodes else total_images
            
            node_files = image_files[start_idx:end_idx]
            
            # Create node directory
            node_dir = output_base / f"node{node_idx}" / "train" / class_name
            node_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy files
            print(f"  → node{node_idx}: copying {len(node_files)} images...", end=" ", flush=True)
            for img_file in node_files:
                src = class_path / img_file
                dst = node_dir / img_file
                shutil.copy2(src, dst)
            print("✓")
        
        print()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    
    total_all_nodes = 0
    for node_idx in range(1, num_nodes + 1):
        node_path = output_base / f"node{node_idx}" / "train"
        
        normal_count = len(list((node_path / 'NORMAL').glob('*'))) if (node_path / 'NORMAL').exists() else 0
        pneumonia_count = len(list((node_path / 'PNEUMONIA').glob('*'))) if (node_path / 'PNEUMONIA').exists() else 0
        total = normal_count + pneumonia_count
        total_all_nodes += total
        
        normal_pct = (normal_count / total * 100) if total > 0 else 0
        pneumonia_pct = (pneumonia_count / total * 100) if total > 0 else 0
        
        print(f"Node {node_idx}: {node_path}")
        print(f"  Total: {total:4d} images")
        print(f"  NORMAL:    {normal_count:4d} ({normal_pct:.1f}%)")
        print(f"  PNEUMONIA: {pneumonia_count:4d} ({pneumonia_pct:.1f}%)")
        print()
    
    print(f"Total across all nodes: {total_all_nodes} images")
    print()
    print("✓ Dataset split complete!")
    print()

if __name__ == '__main__':
    source = "/home/student/disertatie/dataset/chest_xray/train"
    output = "/home/student/disertatie/diploma_project_FED_FL_MED/fl_datasets"
    
    split_train_dataset(source, output, num_nodes=3, seed=42)

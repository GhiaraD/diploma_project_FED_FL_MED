#!/usr/bin/env python3
"""
Split dataset for Federated Learning across 3 nodes.
Each node gets a portion of train/val/test splits.

Usage:
    python3 scripts/split_dataset_for_fl.py /path/to/dataset --output ./fl_datasets
"""

import os
import shutil
import argparse
from pathlib import Path
import random

def split_files(files, num_nodes=3):
    """Split files into num_nodes parts."""
    random.shuffle(files)
    chunk_size = len(files) // num_nodes
    
    splits = []
    for i in range(num_nodes):
        start = i * chunk_size
        end = start + chunk_size if i < num_nodes - 1 else len(files)
        splits.append(files[start:end])
    
    return splits

def create_node_datasets(dataset_path, output_path, num_nodes=3, seed=42):
    """
    Create FL datasets for each node.
    
    Args:
        dataset_path: Path to original dataset with train/val/test/NORMAL/PNEUMONIA
        output_path: Output directory for node datasets
        num_nodes: Number of nodes (default: 3)
        seed: Random seed for reproducibility
    """
    random.seed(seed)
    
    dataset_path = Path(dataset_path)
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Federated Learning Dataset Split")
    print("=" * 60)
    print(f"Source: {dataset_path}")
    print(f"Output: {output_path}")
    print(f"Nodes: {num_nodes}")
    print(f"Seed: {seed}")
    print()
    
    # Process each split (train/val/test)
    for split in ['train', 'val', 'test']:
        split_path = dataset_path / split
        if not split_path.exists():
            print(f"⚠️  {split}/ not found, skipping...")
            continue
        
        print(f"▶ Processing {split}/")
        
        # Process each class (NORMAL/PNEUMONIA)
        for class_name in ['NORMAL', 'PNEUMONIA']:
            class_path = split_path / class_name
            if not class_path.exists():
                print(f"  ⚠️  {class_name}/ not found, skipping...")
                continue
            
            # Get all image files
            image_files = [f for f in os.listdir(class_path) 
                          if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            
            print(f"  {class_name}: {len(image_files)} images")
            
            # Split files across nodes
            node_splits = split_files(image_files, num_nodes)
            
            # Copy files to each node
            for node_idx, node_files in enumerate(node_splits, 1):
                node_dir = output_path / f"node{node_idx}" / split / class_name
                node_dir.mkdir(parents=True, exist_ok=True)
                
                for img_file in node_files:
                    src = class_path / img_file
                    dst = node_dir / img_file
                    shutil.copy2(src, dst)
                
                print(f"    → node{node_idx}: {len(node_files)} images")
        
        print()
    
    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    for node_idx in range(1, num_nodes + 1):
        node_path = output_path / f"node{node_idx}"
        print(f"\nNode {node_idx}: {node_path}")
        
        for split in ['train', 'val', 'test']:
            split_path = node_path / split
            if not split_path.exists():
                continue
            
            normal_count = len(list((split_path / 'NORMAL').glob('*'))) if (split_path / 'NORMAL').exists() else 0
            pneumonia_count = len(list((split_path / 'PNEUMONIA').glob('*'))) if (split_path / 'PNEUMONIA').exists() else 0
            total = normal_count + pneumonia_count
            
            print(f"  {split:5s}: {total:4d} images ({normal_count} NORMAL, {pneumonia_count} PNEUMONIA)")
    
    print()
    print("✓ Dataset split complete!")
    print()
    print("Next steps:")
    print("  1. Create ZIPs for each node:")
    for node_idx in range(1, num_nodes + 1):
        print(f"     cd {output_path}/node{node_idx} && zip -r ../node{node_idx}_data.zip train/ val/ test/")
    print()
    print("  2. Upload to nodes via UI or API")
    print()

def main():
    parser = argparse.ArgumentParser(
        description='Split dataset for Federated Learning across multiple nodes'
    )
    parser.add_argument(
        'dataset_path',
        type=str,
        help='Path to dataset with train/val/test/NORMAL/PNEUMONIA structure'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='./fl_datasets',
        help='Output directory for node datasets (default: ./fl_datasets)'
    )
    parser.add_argument(
        '--nodes',
        type=int,
        default=3,
        help='Number of nodes (default: 3)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )
    
    args = parser.parse_args()
    
    create_node_datasets(
        args.dataset_path,
        args.output,
        args.nodes,
        args.seed
    )

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Create ZIP files for each node dataset."""

import zipfile
from pathlib import Path

def create_zip(source_dir, output_zip):
    """Create ZIP file from directory."""
    source_dir = Path(source_dir)
    output_zip = Path(output_zip)
    
    print(f"Creating {output_zip.name}...", end=" ", flush=True)
    
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(source_dir.parent)
                zipf.write(file_path, arcname)
    
    size_mb = output_zip.stat().st_size / (1024 * 1024)
    print(f"✓ ({size_mb:.1f} MB)")

if __name__ == '__main__':
    base_dir = Path("/home/student/disertatie/diploma_project_FED_FL_MED/fl_datasets")
    
    print("=" * 60)
    print("Creating ZIP files for nodes")
    print("=" * 60)
    print()
    
    for node_idx in range(1, 4):
        node_dir = base_dir / f"node{node_idx}"
        zip_file = base_dir / f"node{node_idx}_train.zip"
        
        if node_dir.exists():
            create_zip(node_dir, zip_file)
    
    print()
    print("✓ All ZIP files created!")
    print()
    print("ZIP files location:")
    for node_idx in range(1, 4):
        zip_file = base_dir / f"node{node_idx}_train.zip"
        if zip_file.exists():
            print(f"  {zip_file}")
    print()

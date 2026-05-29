"""
Split each of train/val/test into 4 random parts.

Output structure:
  central_dataset_split/
    node_1/
      train/NORMAL/, train/PNEUMONIA/
      val/NORMAL/,   val/PNEUMONIA/
      test/NORMAL/,  test/PNEUMONIA/
    node_2/ ...
    node_3/ ...
    node_4/ ...
"""

import os
import random
import shutil

SRC = "central_dataset/chest_xray"
DST = "central_dataset_split"
SPLITS = ["train", "val", "test"]
CLASSES = ["NORMAL", "PNEUMONIA"]
N_PARTS = 4
SEED = 42


def split_files(files: list, n: int) -> list[list]:
    """Divide a list into n roughly equal random parts."""
    random.shuffle(files)
    return [files[i::n] for i in range(n)]


def main():
    random.seed(SEED)

    for split in SPLITS:
        for cls in CLASSES:
            src_dir = os.path.join(SRC, split, cls)
            files = sorted(os.listdir(src_dir))
            parts = split_files(files, N_PARTS)

            for node_idx, part in enumerate(parts, start=1):
                dst_dir = os.path.join(DST, f"node_{node_idx}", split, cls)
                os.makedirs(dst_dir, exist_ok=True)
                for fname in part:
                    shutil.copy2(
                        os.path.join(src_dir, fname),
                        os.path.join(dst_dir, fname),
                    )

            print(
                f"{split}/{cls}: {len(files)} files → "
                + ", ".join(f"node_{i+1}: {len(parts[i])}" for i in range(N_PARTS))
            )


if __name__ == "__main__":
    main()

import hashlib
import torch
from pathlib import Path

def sha256_file(path: str | Path) -> str:
    """Compute SHA256 hash of a file."""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_model_hash(model) -> str:
    """
    Compute SHA256 hash of model state dict.
    
    Args:
        model: PyTorch model (nn.Module) or state dict (OrderedDict)
        
    Returns:
        SHA256 hash string
    """
    import io
    buffer = io.BytesIO()
    
    # Handle both nn.Module and state_dict
    if isinstance(model, dict):
        # Already a state dict
        torch.save(model, buffer)
    else:
        # PyTorch model
        torch.save(model.state_dict(), buffer)
    
    buffer.seek(0)
    return hashlib.sha256(buffer.read()).hexdigest()
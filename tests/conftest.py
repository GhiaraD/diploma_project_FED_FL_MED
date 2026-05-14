"""
Configurație pytest pentru testele Fed-Med-FL.

Furnizează fixture-uri comune și configurație globală.
"""
import sys
from pathlib import Path

# Asigură că node_core și scripts sunt în path pentru toate testele
sys.path.insert(0, str(Path(__file__).parent.parent / "shared" / "python" / "node_core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

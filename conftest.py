"""Make the project root importable so tests can do `from src.data_loader import ...`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

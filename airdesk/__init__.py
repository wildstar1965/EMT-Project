"""AirDesk: model evidence stays separate from visual state."""
import os
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".cache" / "matplotlib"))
__version__ = "0.1.0"

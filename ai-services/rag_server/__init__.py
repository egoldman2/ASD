"""Shared local Retrieval-Augmented Generation service."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from .config import RAGSettings, get_settings

__all__ = ["RAGSettings", "get_settings"]
__version__ = "0.1.0"

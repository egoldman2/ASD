"""Test path setup for the shared MCP service package."""

from pathlib import Path
import sys


AI_SERVICES_ROOT = Path(__file__).resolve().parents[2]
if str(AI_SERVICES_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_ROOT))

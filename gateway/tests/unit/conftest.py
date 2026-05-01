"""Unit test configuration — adds gateway/ to sys.path for app imports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

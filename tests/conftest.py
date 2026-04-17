"""Add project root to sys.path so tests can `from lib.kroki_util import ...`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

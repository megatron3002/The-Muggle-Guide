"""Shared test configuration and fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `api_service.app.main` resolves
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

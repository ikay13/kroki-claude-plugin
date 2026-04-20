"""Tests for lib.kroki_session.* modules."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from lib.kroki_session import common
from lib.kroki_session.common import (
    GitState,
    ProjectFolderNotFoundError,
)


class TestCommon:
    """Shared utility behaviors — common.py"""


class TestStart:
    """mode=start behaviors — start.py"""


class TestEnd:
    """mode=end behaviors — end.py"""


class TestSnapshot:
    """milestone snapshot behaviors — snapshot.py"""

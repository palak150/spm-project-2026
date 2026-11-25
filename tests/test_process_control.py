import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "build" / "process_control"


def test_engine_exists():
    assert ENGINE.exists(), "Run `make` before running tests."


def test_invalid_command_returns_error():
    result = subprocess.run([str(ENGINE), "unknown", "123"], capture_output=True, text=True)
    assert result.returncode != 0

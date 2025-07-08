#!/usr/bin/env python3
"""
Wrapper script that ensures tiered_notifier.py runs with the correct uv environment
"""

import sys
import subprocess
from pathlib import Path

# Get the directory where this script is located
script_dir = Path(__file__).parent.absolute()

# Run the actual notifier script with uv from its project directory
cmd = [
    "uv",
    "run",
    "--project",
    str(script_dir),
    "python",
    str(script_dir / "tiered_notifier.py"),
]

try:
    result = subprocess.run(cmd, stdin=sys.stdin, capture_output=False, check=False)
    sys.exit(result.returncode)
except Exception as e:
    print(f"Error running tiered notifier: {e}", file=sys.stderr)
    sys.exit(1)

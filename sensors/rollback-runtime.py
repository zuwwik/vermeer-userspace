#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Restore sensor configuration from the installer backup, then reboot manually."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

backup = Path(sys.argv[1])
if os.geteuid():
    raise SystemExit("Run as root")
for entry in reversed(json.loads((backup / "restore.json").read_text())):
    path = Path(entry["path"])
    if path.exists() or path.is_symlink():
        path.unlink()
    if entry["existed"]:
        path.parent.mkdir(parents=True, exist_ok=True)
        if "symlink" in entry:
            path.symlink_to(entry["symlink"])
        else:
            shutil.copy2(backup / entry["copy"], path)
os.sync()
subprocess.run(["systemctl", "daemon-reload"], check=True)
subprocess.run(["udevadm", "control", "--reload-rules"], check=True)
print("Configuration restored. Reboot to load the original firmware/runtime.")

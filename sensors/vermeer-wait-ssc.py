#!/usr/bin/python3 -B
# SPDX-License-Identifier: MIT
"""Wait for the actual SSC QMI server before desktop sensor discovery."""
import subprocess
import sys
import time

deadline = time.monotonic() + 45
while time.monotonic() < deadline:
    try:
        result = subprocess.run(["/usr/bin/qrtr-lookup"], capture_output=True, timeout=2)
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= 5 and fields[:2] == [b"400", b"1"]:
                print("SSC QMI service is ready")
                sys.exit(0)
    except subprocess.TimeoutExpired:
        pass
    time.sleep(0.2)
print("SSC QMI service did not appear", file=sys.stderr)
sys.exit(1)

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a local-only sensor bundle from the phone's collected stock files."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


def extract(archive, destination):
    with tarfile.open(archive) as file:
        file.extractall(destination, filter="data")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    src, dst = args.capture, args.destination
    dst.mkdir(parents=True, exist_ok=False)
    work = dst / ".work"
    work.mkdir()
    extract(src / "vermeer-runtime.tar.gz", work)
    shutil.move(work / "usr/local/lib/vermeer-sensors", dst / "runtime")
    extract(src / "android/adsp-slot-a-libraries.tar", work / "libraries")
    shutil.move(work / "libraries/adsp", dst / "dsp")
    extract(src / "android/stock-registry.tar", work / "state")
    shutil.move(work / "state/registry", dst / "factory-state")
    extract(src / "android/stock-odm-sensor-configs.tar", dst / "profile/odm/etc/sensors")
    sensors = dst / "profile/sensors"
    sensors.mkdir(parents=True)
    # The stock vendor directory has only the CHRE config, also present in ODM.
    (sensors / "config").mkdir()
    shutil.copy2(dst / "profile/odm/etc/sensors/config/chre_dynamic_sensors.json", sensors / "config")
    # File format confirmed from this phone's /vendor/etc/sensors/sns_reg_config.
    shutil.copy2(src / "sns_reg.conf", sensors / "sns_reg.conf")
    shutil.copytree(src / "adsp-slot-a", dst / "firmware")
    for name in ("install-runtime.py", "vermeer-adsp-firmware.py", "rollback-runtime.py", "vermeer-wait-ssc.py"):
        shutil.copy2(Path(__file__).parent / name, dst / name)
    shutil.rmtree(work)
    files = {str(path.relative_to(dst)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in dst.rglob("*") if path.is_file()}
    (dst / "files.json").write_text(json.dumps(files, indent=2, sort_keys=True))
    print("Prepared", len(files), "files in", dst)


if __name__ == "__main__":
    main()

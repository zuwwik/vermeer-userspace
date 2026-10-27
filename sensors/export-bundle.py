#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export a private reinstall bundle from an already configured Vermeer phone."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--installed', type=Path,
                        default=Path('/usr/local/lib/vermeer-sensors/20261027-slot-a'))
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run as root on the configured phone')
    source = args.installed.resolve()
    state = Path('/var/lib/hexagonrpcd/vermeer-slot-a')
    for name in ('firmware/manifest.json', 'profile/dsp/adsp', 'profile/odm/etc/sensors',
                 'profile/sensors/sns_reg.conf'):
        if not (source / name).exists():
            parser.error('Incomplete installed sensor profile: ' + name)
    if not state.is_dir():
        parser.error('The private Linux sensor registry is missing')
    destination = args.destination.resolve()
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in ('bin/hexagonrpcd', 'lib/libhexagonrpc.so.0.5', 'libexec/iio-sensor-proxy'):
        path = destination / 'runtime' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, path)
    for src, dst in [(source / 'firmware', destination / 'firmware'),
                     (source / 'profile/dsp/adsp', destination / 'dsp'),
                     (source / 'profile/odm', destination / 'profile/odm'),
                     (state, destination / 'factory-state')]:
        shutil.copytree(src, dst)
    sensors = destination / 'profile/sensors'
    sensors.mkdir(parents=True)
    shutil.copy2(source / 'profile/sensors/sns_reg.conf', sensors / 'sns_reg.conf')
    shutil.copytree(source / 'profile/sensors/config', sensors / 'config')
    here = Path(__file__).resolve().parent
    for name in ('install-runtime.py', 'rollback-runtime.py', 'vermeer-adsp-firmware.py', 'vermeer-wait-ssc.py'):
        shutil.copy2(here / name, destination / name)
    manifest = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in destination.rglob('*') if p.is_file()}
    (destination / 'files.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print('Private bundle:', destination)
    print('Keep the device registry and calibration outside public repositories.')


if __name__ == '__main__':
    main()

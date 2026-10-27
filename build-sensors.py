#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the native sensor daemons into a staging directory."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=Path('downloads'))
    parser.add_argument('--build', type=Path, default=Path('build-sensors'))
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    source, build = args.sources.resolve(), args.build.resolve()
    for name in ('hexagonrpc', 'iio-sensor-proxy'):
        if not (source / name / 'meson.build').exists():
            parser.error('Run fetch-sources.py first')
    stage = build / 'stage'
    for name, options in (
        ('hexagonrpc', ['-Dhexagonrpcd_verbose=false']),
        ('iio-sensor-proxy', ['-Dssc-support=enabled', '-Dtests=false', '-Dgtk_doc=false']),
    ):
        directory = build / name
        subprocess.run(['meson', 'setup', str(directory), str(source / name),
                        '--prefix=/usr/local/lib/vermeer-sensors', '--libdir=lib',
                        '--buildtype=release', *options], check=True)
        subprocess.run(['ninja', '-C', str(directory), '-j', str(args.jobs)], check=True)
        env = os.environ.copy()
        env['DESTDIR'] = str(stage)
        subprocess.run(['meson', 'install', '-C', str(directory)], env=env, check=True)
    runtime = build / 'runtime'
    for name in ('bin/hexagonrpcd', 'lib/libhexagonrpc.so.0.5', 'libexec/iio-sensor-proxy'):
        path = runtime / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stage / 'usr/local/lib/vermeer-sensors' / name, path)
    print('Staged sensor runtime:', runtime)


if __name__ == '__main__':
    main()

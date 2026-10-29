#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the real proxy wrapper with reentrant polling and device removal."""
import argparse
from pathlib import Path
import shlex
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path, help='Patched iio-sensor-proxy src directory')
args = parser.parse_args()
flags = shlex.split(subprocess.check_output(
    ['pkg-config', '--cflags', '--libs', 'gio-2.0', 'gudev-1.0'], text=True))
with tempfile.TemporaryDirectory(prefix='vermeer-ssc-polling-') as directory:
    binary = Path(directory) / 'test'
    subprocess.run(['cc', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I', str(args.source.resolve()),
                    str(Path(__file__).with_suffix('.c')), '-o', str(binary),
                    *flags], check=True)
    subprocess.run([str(binary)], check=True)

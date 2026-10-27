#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the native patched ModemManager without installing it."""
import argparse
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('downloads/ModemManager'))
    parser.add_argument('--build', type=Path, default=Path('build-modem'))
    parser.add_argument('--jobs', type=int, default=2)
    args = parser.parse_args()
    source, build = args.source.resolve(), args.build.resolve()
    subprocess.run(['meson', 'setup', str(build), str(source), '--prefix=/usr', '--libdir=lib',
                    '--buildtype=release', '--auto-features=disabled', '-Dwerror=false',
                    '-Dplugin_qcom_soc=enabled', '-Dplugin_generic=enabled',
                    '-Dbuiltin_plugins=true', '-Dintrospection=false', '-Dman=false',
                    '-Dgtk_doc=false', '-Dexamples=false', '-Dtests=false',
                    '-Dbash_completion=false'], check=True)
    subprocess.run(['ninja', '-C', str(build), '-j', str(args.jobs), 'src/ModemManager'], check=True)
    print('Built daemon:', build / 'src/ModemManager')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fetch pinned upstream sources and apply the matching Vermeer patches."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('names', nargs='*', help='Source names from sources.lock; default: all')
    parser.add_argument('--directory', type=Path, default=Path('downloads'))
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    sources = json.loads((here / 'sources.lock').read_text())
    names = args.names or list(sources)
    if any(n not in sources for n in names):
        parser.error('Unknown source name')
    args.directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        entry = sources[name]
        target = args.directory.resolve() / name
        if target.exists():
            parser.error('Destination already exists: ' + str(target))
        subprocess.run(['git', 'init', str(target)], check=True)
        subprocess.run(['git', '-C', str(target), 'remote', 'add', 'origin', entry['url']], check=True)
        subprocess.run(['git', '-C', str(target), 'fetch', '--depth=1', 'origin', entry['revision']], check=True)
        subprocess.run(['git', '-C', str(target), 'checkout', '--detach', 'FETCH_HEAD'], check=True)
        actual = subprocess.check_output(['git', '-C', str(target), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != entry['revision']:
            raise SystemExit('Unexpected source revision: ' + name)
        if entry.get('patch'):
            subprocess.run(['git', '-C', str(target), 'apply', '--check', str(here / entry['patch'])], check=True)
            subprocess.run(['git', '-C', str(target), 'apply', str(here / entry['patch'])], check=True)
        print(name, actual)


if __name__ == '__main__':
    main()

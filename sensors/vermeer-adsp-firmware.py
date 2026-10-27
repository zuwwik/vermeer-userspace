#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Select a complete ADSP snapshot while retaining all other firmware paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile

ALLOWED = re.compile(r"(?:adsp(?:_dtb)?\.(?:mdt|b[0-9]{2})|adsp(?:r|s|ua)\.jsn)\Z")


def verify(source):
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest.get("schema") != 1 or manifest.get("scope") != "adsp-only":
        raise ValueError("unsupported firmware manifest")
    names = manifest["files"]
    if not {"adsp.mdt", "adsp_dtb.mdt"} <= names.keys():
        raise ValueError("both ADSP images are required")
    for name, expected in names.items():
        if not ALLOWED.fullmatch(name):
            raise ValueError("file outside ADSP scope: " + name)
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("missing firmware file: " + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("firmware checksum mismatch: " + name)
    for image in ("adsp", "adsp_dtb"):
        data = (source / (image + ".mdt")).read_bytes()
        if len(data) < 52 or data[:6] != b"\x7fELF\x01\x01":
            raise ValueError("expected a little-endian ELF32 MDT: " + image)
        phoff = struct.unpack_from("<I", data, 28)[0]
        phsize, count = struct.unpack_from("<HH", data, 42)
        if phsize != 32 or phoff + phsize * count > len(data):
            raise ValueError("invalid program headers: " + image)
        for index in range(count):
            kind, offset, _, _, size, _, flags, _ = struct.unpack_from("<8I", data, phoff + 32 * index)
            # Qualcomm hash segments are embedded in MDT metadata, not loaded.
            if kind != 1 or not size or (flags >> 24 & 7) == 2 or offset + size <= len(data):
                continue
            segment = f"{image}.b{index:02d}"
            if segment not in names or (source / segment).stat().st_size != size:
                raise ValueError("missing or truncated load segment: " + segment)
    return manifest


def select(source, parameter, output):
    source = source.resolve()
    manifest = verify(source)
    current = parameter.read_text().strip()
    if Path(current) == output:
        selected = json.loads((output / ".manifest.json").read_text())
        if selected == manifest:
            return output
        raise ValueError("a different firmware snapshot is already selected")
    base = Path(current)
    if not current or not base.is_absolute() or not base.is_dir():
        raise ValueError("existing firmware directory is unavailable")
    if output.exists():
        raise ValueError("output directory already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".vermeer-firmware-", dir=output.parent))
    try:
        # Retain the existing modem, Bluetooth, GPU and board subdirectories.
        for path in base.iterdir():
            (staging / path.name).symlink_to(path.absolute(), target_is_directory=path.is_dir())
        overrides = {name: source / name for name in manifest["files"]}
        overrides.update({"adsp.mbn": source / "adsp.mdt", "adsp_dtb.mbn": source / "adsp_dtb.mdt"})
        for name, target in overrides.items():
            path = staging / name
            if path.is_symlink() or path.exists():
                path.unlink()
            path.symlink_to(target)
        (staging / ".base-path").write_text(str(base) + "\n")
        (staging / ".manifest.json").write_text(json.dumps(manifest, sort_keys=True))
        for path in (staging / ".base-path", staging / ".manifest.json"):
            with path.open("rb") as file:
                os.fsync(file.fileno())
        fd = os.open(staging, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        staging.rename(output)
        # Publish only after the entire directory has been assembled.
        parameter.write_text(str(output))
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("/usr/local/lib/firmware/vermeer-adsp-slot-a"))
    parser.add_argument("--parameter", type=Path, default=Path("/sys/module/firmware_class/parameters/path"))
    parser.add_argument("--output", type=Path, default=Path("/run/vermeer-firmware"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        print("Verified ADSP snapshot:", len(verify(args.source)["files"]), "files")
    else:
        print("Selected ADSP snapshot:", select(args.source, args.parameter, args.output))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Vermeer ADSP override not selected:", error, file=sys.stderr)
        sys.exit(1)

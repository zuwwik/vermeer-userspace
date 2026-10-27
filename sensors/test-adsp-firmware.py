#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise firmware selection and rejection without touching real sysfs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile

spec = importlib.util.spec_from_file_location("firmware", Path(__file__).with_name("vermeer-adsp-firmware.py"))
firmware = importlib.util.module_from_spec(spec)
spec.loader.exec_module(firmware)


def snapshot(path):
    path.mkdir()
    header = bytearray(84)
    header[:6] = b"\x7fELF\x01\x01"
    struct.pack_into("<I", header, 28, 52)
    struct.pack_into("<HH", header, 42, 32, 1)
    struct.pack_into("<8I", header, 52, 1, 4096, 0, 0, 4, 4, 0, 4096)
    for image in ("adsp", "adsp_dtb"):
        (path / (image + ".mdt")).write_bytes(header)
        (path / (image + ".b00")).write_bytes(b"test")
    manifest = {"schema": 1, "scope": "adsp-only", "files": {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir()}}
    (path / "manifest.json").write_text(json.dumps(manifest))


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source, base, parameter, output = [root / n for n in ("source", "base", "path", "selected")]
    snapshot(source)
    base.mkdir()
    for name in ("modem.mdt", "bt.bin", "adsp.mbn"):
        (base / name).write_text("original " + name)
    parameter.write_text(str(base))
    # Invalid snapshots must leave the original selection and output untouched.
    segment = source / "adsp.b00"
    segment.write_bytes(b"bad")
    try:
        firmware.select(source, parameter, output)
        raise AssertionError("accepted corruption")
    except ValueError:
        pass
    assert parameter.read_text() == str(base) and not output.exists()
    segment.write_bytes(b"test")
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["files"]["modem.mdt"] = "0" * 64
    (source / "manifest.json").write_text(json.dumps(manifest))
    try:
        firmware.select(source, parameter, output)
        raise AssertionError("accepted a modem override")
    except ValueError:
        pass
    assert parameter.read_text() == str(base) and not output.exists()
    del manifest["files"]["modem.mdt"]
    (source / "manifest.json").write_text(json.dumps(manifest))
    firmware.select(source, parameter, output)
    assert parameter.read_text() == str(output)
    assert (output / "adsp.mbn").resolve() == source / "adsp.mdt"
    assert (output / "modem.mdt").read_text() == "original modem.mdt"
    assert (output / "bt.bin").read_text() == "original bt.bin"
    assert (base / "adsp.mbn").read_text() == "original adsp.mbn"
    assert firmware.select(source, parameter, output) == output
print("PASS: checksums, complete MDT segments, ADSP-only scope, atomic selection, original firmware retention, idempotence")

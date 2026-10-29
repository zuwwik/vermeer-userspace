#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install a prepared Vermeer sensor bundle; activation requires a reboot."""
import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import time


def rpc_service(target, domain):
    """Use a full unit: systemd drop-ins cannot remove Conflicts/Before."""
    device = "dev-fastrpc\\x2dadsp.device"
    extra = " -s" if domain == "sensorspd" else ""
    after = " hexagonrpcd-adsp-rootpd.service" if domain == "sensorspd" else ""
    return ("[Unit]\nDescription=Vermeer ADSP FastRPC " + domain + "\n"
            "ConditionPathExists=/dev/fastrpc-adsp\n"
            "After=msm-firmware-loader.service " + device + after + "\n"
            "BindsTo=" + device + "\n\n[Service]\nUser=fastrpc\nGroup=fastrpc\n"
            "Environment=LD_LIBRARY_PATH=" + str(target / "lib") + "\n"
            "ExecStart=" + str(target / "bin/hexagonrpcd") +
            " -f /dev/fastrpc-adsp -d adsp" + extra + " -R " + str(target / "profile") +
            "\nRestart=no\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    manifest = json.loads((bundle / "files.json").read_text())
    for name, digest in manifest.items():
        path = bundle / name
        if not path.is_relative_to(bundle) or path.is_symlink():
            raise ValueError("invalid bundle path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("bundle checksum mismatch: " + name)
    if os.geteuid() != 0:
        raise SystemExit("Run as root on the Linux phone")
    compatible = Path("/proc/device-tree/compatible").read_bytes().split(b"\0")
    if b"xiaomi,vermeer" not in compatible:
        raise SystemExit("This bundle is only for Xiaomi Vermeer")
    base = Path("/usr/share/qcom/sm8550/Xiaomi/vermeer")
    if not (base / "dsp/adsp/libsns_remote_proc_state_skel.so").is_file():
        raise SystemExit("Existing Vermeer vendor DSP libraries are required")
    uid, gid = pwd.getpwnam("fastrpc").pw_uid, grp.getgrnam("fastrpc").gr_gid
    version = "20261027-slot-a"
    target = Path("/usr/local/lib/vermeer-sensors") / version
    if target.exists():
        raise SystemExit("Version already installed; inspect it before reinstalling")
    backup = Path("/var/lib/vermeer-sensor-backups") / time.strftime("%Y%m%d-%H%M%S")
    backup.mkdir(parents=True)
    saved = []

    def write_config(name, contents, mode=0o644):
        path = Path(name)
        record = {"path": name, "existed": path.exists() or path.is_symlink()}
        if record["existed"]:
            old = backup / str(len(saved))
            if path.is_symlink():
                record["symlink"] = os.readlink(path)
            else:
                shutil.copy2(path, old)
                record["copy"] = old.name
        saved.append(record)
        (backup / "restore.json").write_text(json.dumps(saved, indent=2))
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".vermeer-new")
        temp.write_text(contents)
        temp.chmod(mode)
        temp.replace(path)

    shutil.copytree(bundle / "runtime", target)
    profile = target / "profile"
    shutil.copytree(bundle / "profile", profile)
    # Regular files are required: the confined DSP filesystem rejects symlinks.
    dsp = profile / "dsp/adsp"
    dsp.mkdir(parents=True)
    for path in (base / "dsp/adsp").iterdir():
        shutil.copy2(path, dsp / path.name)
    for path in (bundle / "dsp").iterdir():
        dst = dsp / path.name
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        shutil.copy2(path, dst)
    state = Path("/var/lib/hexagonrpcd/vermeer-slot-a")
    if not state.exists():
        shutil.copytree(bundle / "factory-state", state)
        for path in [state, *state.rglob("*")]:
            os.chown(path, uid, gid, follow_symlinks=False)
    (profile / "sensors/state").symlink_to(state)
    for path in (base / "socinfo").iterdir():
        (profile / "socinfo").mkdir(exist_ok=True)
        shutil.copy2(path, profile / "socinfo" / path.name)
    shutil.copytree(bundle / "firmware", target / "firmware")
    # Install the selector before the unit references it. No live ADSP restart.
    write_config("/usr/local/libexec/vermeer-adsp-firmware",
                 (bundle / "vermeer-adsp-firmware.py").read_text(), 0o755)
    write_config("/usr/local/libexec/vermeer-wait-ssc",
                 (bundle / "vermeer-wait-ssc.py").read_text(), 0o755)
    write_config("/etc/systemd/system/iio-sensor-proxy.service.d/vermeer.conf",
                 "[Unit]\nWants=hexagonrpcd-adsp-rootpd.service hexagonrpcd-adsp-sensorspd.service\n"
                 "After=hexagonrpcd-adsp-sensorspd.service\n\n[Service]\n"
                 "ExecStartPre=/usr/local/libexec/vermeer-wait-ssc\nTimeoutStartSec=60\n"
                 "Restart=on-failure\nRestartSec=2\n"
                 "ExecStart=\nExecStart=" + str(target / "libexec/iio-sensor-proxy") + "\n")
    write_config("/etc/systemd/system/msm-firmware-loader.service.d/vermeer-adsp.conf",
                 "[Service]\nExecStartPost=-/usr/local/libexec/vermeer-adsp-firmware --source "
                 + str(target / "firmware") + "\n")
    for domain in ("rootpd", "sensorspd"):
        write_config("/etc/systemd/system/hexagonrpcd-adsp-" + domain + ".service",
                     rpc_service(target, domain))
        write_config("/etc/systemd/system/hexagonrpcd-adsp-" + domain + ".service.d/vermeer.conf",
                     "# Configured in the full Vermeer service unit.\n")
        # Device events start these units; avoid racing a boot-time ConditionPathExists.
        link = Path("/etc/systemd/system/multi-user.target.wants/hexagonrpcd-adsp-" + domain + ".service")
        if link.is_symlink():
            saved.append({"path": str(link), "existed": True, "symlink": os.readlink(link)})
            link.unlink()
    (backup / "restore.json").write_text(json.dumps(saved, indent=2))
    write_config("/etc/udev/rules.d/99-vermeer-sensors.rules", '''# Native SSC providers on the Vermeer ADSP only.
ACTION!="remove", SUBSYSTEM=="misc", KERNEL=="fastrpc-adsp", ENV{IIO_SENSOR_PROXY_TYPE}="ssc-accel ssc-light ssc-compass ssc-proximity", ENV{ACCEL_MOUNT_MATRIX}="-1, 0, 0; 0, -1, 0; 0, 0, 1", ENV{SSC_LIGHT_SENSOR_TYPE}="ambient_light_back", TAG+="systemd", ENV{SYSTEMD_WANTS}+="hexagonrpcd-adsp-rootpd.service hexagonrpcd-adsp-sensorspd.service"
''')
    # Persist every ELF and configuration before it can be used on the next boot.
    os.sync()
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["udevadm", "control", "--reload-rules"], check=True)
    print("Installed:", target)
    print("Rollback metadata:", backup)
    print("Reboot to test the matched ADSP firmware. No DSP domain was restarted live.")


if __name__ == "__main__":
    main()

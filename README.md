# Vermeer system integration

Systemd/musl integration for Poco F6 Pro / Redmi K70. Use with
[vermeer-mainline](https://github.com/zuwwik/vermeer-mainline),
[vermeer-audio](https://github.com/zuwwik/vermeer-audio) and
[vermeer-camera](https://github.com/zuwwik/vermeer-camera).

`sources.lock` pins upstream sources. `fetch-sources.py` checks them out and
applies the maintained patches into fresh directories.
The prebuilt aarch64 musl daemons are the deployed versions, with checksums in
`SHA256SUMS`; device calibration, persist contents and network credentials are
not included.

## Sensors

The native stack is hexagonrpc 0.5, libssc 0.4.4 and iio-sensor-proxy 3.9.
The patches add the required confined DSP filesystem, private writable registry,
bounded startup retry, initial desktop sensor claims and SSC error recovery.
The desktop uses the rear ALS and an accelerometer matrix of
`-1,0,0;0,-1,0;0,0,1`. Accelerometer, gyro, compass/magnetometer, light and
proximity work. Front under-display ALS compensation is not implemented;
Android lists no barometer or Hall sensor on this unit.

```sh
python3 fetch-sources.py
python3 build-sensors.py
```

Build natively on the aarch64 phone with Meson, Ninja, C compiler, pkg-config,
GLib, libqmi, libqrtr-glib, protobuf-c, libgudev, udev/systemd development files
and the distribution's libssc 0.4.4 development package. The command stages the
hexagonrpc and sensor-proxy runtime; it does not restart a DSP domain.

The sensor installer also needs the matched ADSP firmware, DSP libraries,
ODM configuration and the owner's factory registry. Keep those local under
ignored `vendor/`. The already prepared phone can export a private installation
bundle with `python3 sensors/export-bundle.py OUTPUT_DIRECTORY`. The output is
not a public repository input and must not be committed.

On a new rootfs, install its stock Vermeer DSP support under
`/usr/share/qcom/sm8550/Xiaomi/vermeer/`, create the distribution's `fastrpc`
account/group, and install the normal hexagonrpc and iio-sensor-proxy units.
Then run, as root:

```sh
python3 /path/to/private-bundle/install-runtime.py /path/to/private-bundle
```

The installer verifies hashes, backs up configuration, keeps Android persist
read-only and installs a separate writable Linux registry. It selects the
complete matched ADSP set after the firmware loader and before udev. Reboot
normally to activate it. Roll back with the bundle's `rollback-runtime.py` and
the printed backup directory. Do not unload/restart the live DSP stack.

The installer writes complete Vermeer hexagonrpcd service units so both
listeners remain running across system sleep. Systemd drop-ins cannot remove
the packaged units' `Conflicts=suspend.target` dependency. Device dependencies
still stop the listeners when their FastRPC device disappears.

## Modem

The ModemManager 1.25.95 patch fixes primary-slot selection and a netlink
transaction lifetime bug. Build with `python3 build-modem.py`, or stage the
matching prebuilt daemon. `modem/90-vermeer.conf` selects it at
`/usr/local/libexec/vermeer-modem/ModemManager`. On Nura, mask the vendor
`quick-suspend-resume.conf` drop-in with an `/etc/systemd/system/` symlink to
`/dev/null`, so it cannot replace this ExecStart.
The daemon requires the matching packaged libmm-glib 1.25.95 and its usual
libqmi/libqrtr-glib, GLib, libgudev and polkit dependencies.

Enable `rmtfs`, `tqftpserv`, `ModemManager` and `NetworkManager` with their
distribution-provided systemd units. Install the NetworkManager WWAN plugin.
Create an APN profile for the SIM/carrier through NetworkManager; no private
APN profile or SIM PIN is shipped. Physical SIM switching, simultaneous SMS
reception on both SIMs and GPS fixes have not been validated.
`modem/calls-daemon.service` is an optional GNOME Calls user-unit replacement
for KDE; call audio itself is supplied by the separate audio repository.

## Haptics

```sh
make -C haptics
make -C haptics DESTDIR="$PWD/stage" install
```

The input driver is part of the kernel. The CLI supports ordinary force
feedback, six stock custom waves and primitive composition. The udev rule
identifies the device for feedbackd. Stock effect data retain vendor terms;
source licenses are specified per file. Generic feedbackd strength and custom
waveform strength are separate settings.

## Boot integration

`rootfs/` contains the deployed firmware loader and USB serial console files,
the Plymouth serial-console fix and the KIO FUSE tmpfiles override.
The firmware loader reads the `_b` modem/Bluetooth partitions read-only; ADSP
is selected separately by the sensor integration. Install the loader and unit
before booting a new rootfs, and enable `msm-firmware-loader.service` and
`vermeer-usb-serial.service`. Install Python 3 for the ADSP selector.
The tmpfiles override leaves `/run/user` cleanup to logind. No replacement
network profiles, passwords, SSH keys or user-session state are supplied.

Kernel module installation must match the kernel release and be followed by
`depmod`. Normal audio services are PipeWire, pipewire-pulse and WirePlumber in
the desktop session. No service here performs automatic flashing or rebooting.

The intermittent ADSP charger-firmware exceptions and occasional SoundWire
clock-stop timeouts remain under investigation; these sources do not establish
that all system stability or GPS problems are solved.

## Idle power integration

The desktop torch toggle and measured current settings are in `power/`.
For the serial-only USB gadget, install `rootfs/unudhcpd-usb0.conf` at
`/etc/systemd/system/unudhcpd@usb0.service.d/interface.conf`, reload systemd
and restart `unudhcpd@usb0.service`. It skips DHCP when no usb0 network
interface exists, avoiding the previous retry/log loop. If a USB Ethernet
interface is subsequently configured, start that DHCP service normally.

## Native Vulkan graphics

On Alpine/Nura, install `mesa-vulkan-freedreno` alongside the matching Mesa
packages to provide Turnip for Adreno 740. `vulkan-loader` alone provides no
hardware driver. Keep the package version aligned with the installed Mesa.

Verify as the desktop user with `vulkaninfo --summary` and `fastfetch`.
Mesa 26.2.5 on Vermeer reports Turnip Adreno 740 / Vulkan 1.4; a 120-frame
Wayland vkcube check passed. With no Vulkan driver, fastfetch may fall through
to an unrelated Rusticl/libclc error instead of displaying the GPU.

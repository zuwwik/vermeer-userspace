#!/usr/bin/env python3
"""Test actual proxy polling callbacks when SSC fails without a GError.

This is the failure at ssc_accelerometer_set_polling+0xf4 in the phone's
2026-10-27 ADSP-recovery coredumps. No phone hardware is touched.
"""
import argparse
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


def extract(source, name):
    match = re.search(r"static void\s+" + name + r"\s*\(", source)
    start = match.start()
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    flags = shlex.split(subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "gobject-2.0"], text=True))
    with tempfile.TemporaryDirectory(prefix="vermeer-ssc-recovery-") as temp:
        for kind in ("accel", "light", "compass", "proximity"):
            long_name = "accelerometer" if kind == "accel" else kind
            function = f"ssc_{long_name}_set_polling"
            source = (args.source / f"drv-ssc-{kind}.c").read_text()
            code = r'''
#include <glib-object.h>
typedef struct { GObject *sensor; gulong measurement_id; } DrvData;
typedef struct { void *priv; } SensorDevice;
static unsigned int attempts;
static void measurement_cb(void) {}
static gboolean failed(GObject *sensor, gpointer cancel, GError **error)
{
    (void)sensor; (void)cancel;
    attempts++;
    *error = NULL;
    return FALSE;
}
'''
            code += f"#define ssc_sensor_{long_name}_open_sync failed\n"
            code += f"#define ssc_sensor_{long_name}_close_sync failed\n"
            code += extract(source, function)
            code += r'''
int main(int argc, char **argv)
{
    g_test_init(&argc, &argv, NULL);
    g_signal_new("measurement", G_TYPE_OBJECT, G_SIGNAL_RUN_LAST,
                 0, NULL, NULL, NULL, G_TYPE_NONE, 0);
    DrvData data = {.sensor = g_object_new(G_TYPE_OBJECT, NULL)};
    SensorDevice device = {.priv = &data};
    for (unsigned int i = 0; i < 3; i++) {
        g_test_expect_message(NULL, G_LOG_LEVEL_WARNING, "Opening SSC * sensor failed:*");
        POLLING_CALLBACK(&device, TRUE);
        g_test_assert_expected_messages();
        g_assert_cmpuint(data.measurement_id, ==, 0);
        g_assert_cmpuint(attempts, ==, i + 1);
        POLLING_CALLBACK(&device, FALSE);
    }
    g_object_unref(data.sensor);
    return 0;
}
'''.replace("POLLING_CALLBACK", function)
            cfile, binary = Path(temp) / f"{kind}.c", Path(temp) / kind
            cfile.write_text(code)
            subprocess.run(["cc", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                            "-fsanitize=address,undefined", str(cfile), "-o", str(binary),
                            *flags], check=True)
            subprocess.run([str(binary)], check=True)
    print("PASS: all four SSC polling drivers survive empty errors and retry failed opens")


if __name__ == "__main__":
    main()

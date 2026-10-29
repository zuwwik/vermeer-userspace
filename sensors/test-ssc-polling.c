/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Exercise the real drivers.h with reentrant backend calls. */
#include "drivers.h"
#include <assert.h>
static int depth, calls, closed, mode;
static gboolean actual;
static void fake_close(SensorDevice *device) {
    assert(!depth); assert(!actual); closed++; g_free(device);
}
static void fake_poll(SensorDevice *device, gboolean state) {
    assert(++depth == 1); calls++;
    if (mode == 1 && state) {
        mode = 0;
        driver_set_polling(device, FALSE);
        driver_set_polling(device, TRUE);
        driver_set_polling(device, FALSE);
    } else if (mode == 2 && !state) {
        mode = 0; driver_set_polling(device, TRUE);
    } else if (mode == 3 && state) {
        mode = 0; driver_close(device);
        driver_set_polling(device, TRUE); /* removal wins over a late claim */
    } else if (mode == 4 && !state) {
        mode = 0; driver_close(device); /* reentrant removal during close */
    }
    actual = state; depth--;
}
static SensorDriver drv = {.set_polling=fake_poll, .close=fake_close};
int main(void) {
    SensorDevice *device=g_new0(SensorDevice,1); device->drv=&drv;
    mode=1;driver_set_polling(device,TRUE);assert(calls==2 && !actual);
    mode=2;driver_set_polling(device,FALSE);assert(calls==4 && actual);
    mode=3;driver_set_polling(device,TRUE);assert(closed==1 && calls==6);
    device=g_new0(SensorDevice,1); device->drv=&drv;
    mode=4;driver_close(device);assert(closed==2 && calls==7);
    drv.set_polling=NULL;device=g_new0(SensorDevice,1);device->drv=&drv;
    driver_close(device);assert(closed==3);
    g_print("PASS: reentrant claims, releases, device removal and close; no nested backend calls or use-after-free\n");
}

#!/bin/bash
# SPDX-License-Identifier: MIT
LED_DIR="/sys/class/leds/white:flash-0"
BRIGHTNESS_FILE="$LED_DIR/brightness"
MAX_FILE="$LED_DIR/max_brightness"

CURRENT=$(cat "$BRIGHTNESS_FILE")

if [ "$CURRENT" -eq 0 ]; then
    MAX=$(cat "$MAX_FILE")
    printf '%s\n' "$((MAX * 40 / 100))" > "$BRIGHTNESS_FILE"
else
    echo 0 > "$BRIGHTNESS_FILE"
fi


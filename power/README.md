# Torch current

The Vermeer LED driver maps brightness 255 to the board's 500 mA torch limit.
The desktop toggle uses 40% (102, 200 mA); a second invocation turns it off.
Flash-strobe and hardware limits are unchanged. Install `toggle-flash.sh` in
`~/.local/bin/` and bind it to the existing desktop shortcut. It requires write
access to the LED brightness attribute, as in the prepared phone's udev setup.

Controlled measurements on this phone found approximately 0.70 W additional
battery power at 200 mA versus 2.06 W at 500 mA. Total consumption depends on
the display and other active components; Android torch current was not measured.

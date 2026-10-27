# SPDX-License-Identifier: MIT
CC ?= cc
CFLAGS ?= -O2 -g

.PHONY: all install clean
all: vermeer-haptics

vermeer-haptics: vermeer-haptics.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -Wall -Wextra -Werror $< $(LDFLAGS) -o $@

install: all
	install -Dm755 vermeer-haptics $(DESTDIR)/usr/local/bin/vermeer-haptics
	install -Dm644 72-vermeer-haptics.rules $(DESTDIR)/etc/udev/rules.d/72-vermeer-haptics.rules
	install -d $(DESTDIR)/usr/local/share/vermeer-haptics
	install -m644 vibrator/effect_*.bin $(DESTDIR)/usr/local/share/vermeer-haptics/

clean:
	rm -f vermeer-haptics

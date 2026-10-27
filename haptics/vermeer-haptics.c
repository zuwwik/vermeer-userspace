// SPDX-License-Identifier: MIT
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#ifndef WAVE_DIRECTORY
#define WAVE_DIRECTORY "/usr/local/share/vermeer-haptics"
#endif
#define SAMPLE_RATE 24000
#define SAMPLE_RATE_CODE 10
#define STOCK_VMAX_MV 8500
#define MAX_SAMPLES (48 * 1024)

static volatile sig_atomic_t interrupted;
static const char *effect_names[] = {
	"click", "double-click", "tick", "thud", "pop", "heavy-click"
};

static void signal_stop(int signal)
{
	(void)signal;
	interrupted = 1;
}

static int number(const char *text, int maximum)
{
	char *end;
	long value;
	errno = 0;
	value = strtol(text, &end, 10);
	if (errno || !*text || *end || value < 0 || value > maximum) {
		fprintf(stderr, "Invalid number: %s\n", text);
		exit(2);
	}
	return value;
}

static void wait_ms(unsigned duration)
{
	struct timespec remaining = { duration / 1000, (duration % 1000) * 1000000L };
	while (!interrupted && nanosleep(&remaining, &remaining) && errno == EINTR)
		;
}

static int event(int fd, unsigned code, int value)
{
	struct input_event input = { .type = EV_FF, .code = code, .value = value };
	return write(fd, &input, sizeof(input)) == sizeof(input) ? 0 : -1;
}

static int play(int fd, struct ff_effect *effect, unsigned duration, int dry)
{
	if (dry) {
		printf("type=0x%x duration=%ums", effect->type, duration);
		if (effect->type == FF_PERIODIC && effect->u.periodic.waveform == FF_CUSTOM)
			printf(" samples=%u rate=%uHz vmax=%dmV", effect->u.periodic.custom_len - 2,
			       SAMPLE_RATE, effect->u.periodic.custom_data[1]);
		puts("");
		return 0;
	}
	if (ioctl(fd, EVIOCSFF, effect) < 0) {
		perror("Upload effect");
		return 1;
	}
	if (event(fd, effect->id, 1) < 0) {
		perror("Start effect");
		ioctl(fd, EVIOCRMFF, effect->id);
		return 1;
	}
	wait_ms(duration + 2);
	event(fd, effect->id, 0);
	if (ioctl(fd, EVIOCRMFF, effect->id) < 0) {
		perror("Erase effect");
		return 1;
	}
	return 0;
}

static int waveform(int fd, unsigned id, int primitive, unsigned strength, int dry)
{
	char filename[256];
	FILE *file;
	int16_t *data;
	long size;
	int ret;
	struct ff_effect effect = { .type = FF_PERIODIC, .id = -1 };

	if (primitive && !id) {
		if (!dry)
			wait_ms(19);
		return 0;
	}
	snprintf(filename, sizeof(filename), WAVE_DIRECTORY "/%seffect_%u.bin",
		 primitive ? "primitive_" : "", id);
	file = fopen(filename, "rb");
	if (!file) {
		/* Stock HAL uses the click waveform when an OEM file is absent. */
		file = fopen(WAVE_DIRECTORY "/effect_0.bin", "rb");
		if (!file) {
			perror("Stock waveform");
			return 1;
		}
	}
	if (fseek(file, 0, SEEK_END) || (size = ftell(file)) < 1 || size > MAX_SAMPLES ||
	    fseek(file, 0, SEEK_SET)) {
		fprintf(stderr, "Invalid waveform length\n");
		fclose(file);
		return 1;
	}
	data = calloc((size_t)size + 2, sizeof(*data));
	if (!data) {
		fclose(file);
		return 1;
	}
	data[0] = SAMPLE_RATE_CODE;
	data[1] = STOCK_VMAX_MV * strength / 100;
	for (long i = 0; i < size; i++) {
		int sample = fgetc(file);
		if (sample == EOF) {
			fprintf(stderr, "Truncated waveform\n");
			free(data);
			fclose(file);
			return 1;
		}
		data[i + 2] = (int8_t)sample;
	}
	fclose(file);
	/* A zero vmax means device default in the kernel ABI. Make zero silent. */
	if (!strength) {
		for (long i = 0; i < size; i++)
			data[i + 2] = 0;
	}
	effect.u.periodic.waveform = FF_CUSTOM;
	effect.u.periodic.magnitude = 0x7fff;
	effect.u.periodic.custom_len = size + 2;
	effect.u.periodic.custom_data = data;
	unsigned duration = ((unsigned)size * 1000 + SAMPLE_RATE - 1) / SAMPLE_RATE;
	ret = play(fd, &effect, duration, dry);
	free(data);
	return ret;
}

int main(int argc, char **argv)
{
	const char *device = "/dev/input/vermeer-haptics";
	int dry = 0, fd = -1, ret = 0;
	unsigned strength = 50;

	if (argc > 1 && !strcmp(argv[1], "--dry-run")) {
		dry = 1;
		argc--;
		argv++;
	}
	if (argc < 2 || !strcmp(argv[1], "--help")) {
		puts("vermeer-haptics [--dry-run] effect ID[0..21] [strength 0..100]\n"
		     "vermeer-haptics [--dry-run] primitive ID[0..8] [strength 0..100]\n"
		     "vermeer-haptics [--dry-run] rumble|constant|sine [milliseconds] [strength]\n"
		     "vermeer-haptics [--dry-run] compose primitive:strength:delay_ms ...\n"
		     "vermeer-haptics --list\nDefault test strength: 50 percent.");
		return argc < 2 ? 2 : 0;
	}
	if (!strcmp(argv[1], "--list")) {
		for (unsigned i = 0; i < sizeof(effect_names) / sizeof(*effect_names); i++)
			printf("effect %u: %s\n", i, effect_names[i]);
		puts("effect 6..21: stock fallback to click when no dedicated file exists\n"
		     "primitive 0: NOOP; 1..8: stock file or click fallback\n"
		     "compose: up to 256 primitives, each delay 0..1000ms");
		return 0;
	}
	if (!dry) {
		char name[128] = { 0 };
		fd = open(device, O_RDWR | O_CLOEXEC);
		if (fd < 0) {
			perror(device);
			return 1;
		}
		if (ioctl(fd, EVIOCGNAME(sizeof(name)), name) < 0 ||
		    strcmp(name, "qcom-pm8550b-haptics")) {
			fprintf(stderr, "Unexpected input device\n");
			close(fd);
			return 1;
		}
	}
	signal(SIGINT, signal_stop);
	signal(SIGTERM, signal_stop);
	if (!strcmp(argv[1], "effect") || !strcmp(argv[1], "primitive")) {
		int primitive = !strcmp(argv[1], "primitive");
		if (argc < 3 || argc > 4)
			ret = 2;
		else {
			unsigned id = number(argv[2], primitive ? 8 : 21);
			if (argc == 4)
				strength = number(argv[3], 100);
			ret = waveform(fd, id, primitive, strength, dry);
		}
	} else if (!strcmp(argv[1], "compose")) {
		if (argc < 3 || argc > 258)
			ret = 2;
		for (int i = 2; i < argc && !ret && !interrupted; i++) {
			char *part = strdup(argv[i]), *p = part, *id, *scale, *delay;
			if (!part) {
				ret = 1;
				break;
			}
			id = strtok_r(p, ":", &p);
			scale = strtok_r(NULL, ":", &p);
			delay = strtok_r(NULL, ":", &p);
			if (!id || !scale || !delay || strtok_r(NULL, ":", &p))
				ret = 2;
			else {
				unsigned wait = number(delay, 1000);
				if (!dry)
					wait_ms(wait);
				if (!interrupted)
					ret = waveform(fd, number(id, 8), 1, number(scale, 100), dry);
			}
			free(part);
		}
	} else if (!strcmp(argv[1], "rumble") || !strcmp(argv[1], "constant") || !strcmp(argv[1], "sine")) {
		struct ff_effect effect = { .type = FF_RUMBLE, .id = -1 };
		unsigned duration = argc > 2 ? number(argv[2], 65535) : 100;
		if (argc > 4 || !duration)
			ret = 2;
		else {
			if (argc > 3)
				strength = number(argv[3], 100);
			effect.replay.length = duration;
			effect.u.rumble.strong_magnitude = 65535 * strength / 100;
			if (!strcmp(argv[1], "constant")) {
				effect.type = FF_CONSTANT;
				effect.u.constant.level = 32767 * strength / 100;
			} else if (!strcmp(argv[1], "sine")) {
				effect.type = FF_PERIODIC;
				effect.u.periodic.waveform = FF_SINE;
				effect.u.periodic.magnitude = 32767 * strength / 100;
				effect.u.periodic.period = 6;
			}
			ret = play(fd, &effect, duration, dry);
		}
	} else {
		fprintf(stderr, "Unknown command: %s\n", argv[1]);
		ret = 2;
	}
	if (fd >= 0)
		close(fd);
	return ret;
}

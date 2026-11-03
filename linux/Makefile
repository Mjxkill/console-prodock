JOBS ?= 4
BOARD ?= prodock
BUILD_ARGS ?=
export CONSOLE_BOARD := $(BOARD)
export JOBS
all prepare rootfs kernel opensbi package test:
	python3 build.py $@ $(BUILD_ARGS)
sd-boot:
	$(MAKE) -B -C ../fw_console MAIN=../linux/boot/sd_boot.c BUILD=build/linux_sd_boot LD=$(abspath ../games/orbital/src/orbital.ld) EXTRA_SRCS="sd.c sd_ae350.c fatfs/ff.c fatfs/diskio.c ../linux/boot/image.c" CFLAGS_EXTRA="-I$(CURDIR)/boot -I$(abspath ../fw_console)"
.PHONY: all prepare rootfs kernel opensbi package test sd-boot

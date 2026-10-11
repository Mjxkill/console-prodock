JOBS ?= 4
BUILD := $(CURDIR)/../build/uboot
SRC := $(BUILD)/src
OUT := $(BUILD)/out
TC := $(abspath ../build/riscv32-ilp32d--musl--stable-2025.08-1/bin/riscv32-buildroot-linux-musl-)
SOURCE_DATE_EPOCH := 1791417600
export SOURCE_DATE_EPOCH
all: prepare
	$(MAKE) -C $(SRC) O=$(OUT) CROSS_COMPILE=$(TC) prodock_console_defconfig
	python3 ../tests/test_uboot_config.py
	$(MAKE) -C $(SRC) O=$(OUT) CROSS_COMPILE=$(TC) -j$(JOBS)
prepare:
	python3 prepare.py /tmp/la16-u-boot-2025.10.tar.bz2 $(SRC)
.PHONY: all prepare

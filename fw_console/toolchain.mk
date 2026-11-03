# AE350 bare-metal builds with GNU/xPack tools, without a sibling repository.
# AE350_SDK is the SDK's library/ directory. CROSS_COMPILE is a complete tool
# prefix (on PATH, or absolute); TC remains a backwards-compatible alias.
AE350_SDK ?= $(HOME)/ae350/sdk/RiscV_AE350_SOC_V1.3/library
CROSS_COMPILE ?= riscv-none-elf-
TC ?= $(CROSS_COMPILE)
CC = $(TC)gcc
OBJCOPY = $(TC)objcopy
SIZE = $(TC)size
NM = $(TC)nm
PYTHON ?= python3

# A25: RV32 IMAFDC, double-precision floating point ABI, original build flags.
ARCH = -march=rv32imafdc -mabi=ilp32d -mcmodel=medany
BSP_SRCS = $(wildcard $(AE350_SDK)/bsp/ae350/*.c) $(wildcard $(AE350_SDK)/bsp/lib/*.c) $(wildcard $(AE350_SDK)/demo/stubs/*.c)
BSP_ASM = $(AE350_SDK)/bsp/ae350/start.S
INCS = -I$(AE350_SDK)/bsp/ae350 -I$(AE350_SDK)/bsp/config -I$(AE350_SDK)/bsp/driver/include -I$(AE350_SDK)/bsp/lib -I$(AE350_SDK)/demo/stubs
# DDR starts at address zero: keep intentional volatile accesses to address 0.
# Otherwise GCC can replace them with an ebreak (historical TESTS_V3 E1).
CFLAGS = $(ARCH) $(INCS) -include $(FW_DIR)support/andes_compat.h -O2 -g -fno-delete-null-pointer-checks -fno-isolate-erroneous-paths-dereference -ffunction-sections -fdata-sections -Wall -Wno-unused
CFLAGS += $(CFLAGS_EXTRA)
LDFLAGS = $(ARCH) -nostartfiles -Wl,--gc-sections $(FW_DIR)support/gnu_symbols.ld -Wl,-Map,$(BUILD)/$(APP).map

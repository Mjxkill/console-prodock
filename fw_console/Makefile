# Keep build support in this repository; SDK/toolchain are explicit external inputs.
FW_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
include $(FW_DIR)toolchain.mk
APP   = console_test
BUILD = build
MAIN ?= main.c
LD    = $(FW_DIR)itcm.ld
# Additional application sources, for example SD and FatFs.
EXTRA_SRCS ?=
SRCS  = $(MAIN) gpu.c gpu_v1.c gpu_raster_commands.c $(EXTRA_SRCS) $(filter-out $(AE350_SDK)/bsp/lib/read.c,$(BSP_SRCS))
# The native SD adapter links the same SPI engine as Linux and U-Boot.
ifneq ($(filter %sd_ae350.c sd_ae350.c,$(EXTRA_SRCS)),)
SRCS += ../linux/drivers/prodock-spi-pio.c
endif
OBJS  = $(patsubst %.c,$(BUILD)/%.o,$(notdir $(SRCS))) $(BUILD)/start.o
# Common GPU diagnostics reuse scene helpers from the application directories.
GAME_INCLUDE_DIRS = $(wildcard ../games/*/src) ../games/common/astrilla
CFLAGS += -Os -DCFG_XIP -I$(FW_DIR) $(addprefix -I,$(GAME_INCLUDE_DIRS))
vpath %.c $(sort $(dir $(SRCS)))   # Restrict lookup to sources; do not reuse objects from another build.
ITCM_FILES = $(addprefix $(BUILD)/itcm/itcm,0 1 2 3)
.PHONY: all clean check-config print-nm
all: $(BUILD)/$(APP).bin $(ITCM_FILES)
	$(SIZE) $(BUILD)/$(APP).elf
print-nm:
	@printf '%s\n' '$(NM)'
check-config:
	@test -f "$(AE350_SDK)/bsp/ae350/start.S" || { echo 'Set AE350_SDK to the AE350 SDK library directory (bsp/ae350/start.S is required).' >&2; exit 1; }
	@for tool in "$(CC)" "$(OBJCOPY)" "$(SIZE)"; do command -v "$$tool" >/dev/null || { echo "Tool not found: $$tool. Set CROSS_COMPILE (or TC) to the compiler prefix." >&2; exit 1; }; done
$(OBJS): | check-config
$(BUILD)/%.o: %.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(OBJS): $(FW_DIR)support/andes_compat.h $(FW_DIR)toolchain.mk
$(BUILD)/gpu.o: gpu.h gpu_v1.h
$(BUILD)/gpu_raster_commands.o: gpu.h
$(BUILD)/gpu_v1.o: gpu.h gpu_v1.h
$(BUILD)/gpu_geometry.o: gpu_geometry.h gpu_v1.h gpu.h
$(BUILD)/luma_main.o: ../games/luma/src/luma_scene.h ../games/luma/src/luma_fx_scene.h ../games/luma/src/luma_assets.h gpu.h gpu_v1.h
$(BUILD)/orbital_main.o: ../games/orbital/src/orbital_scene.h ../games/orbital/src/orbital_assets.h gpu.h gpu_v1.h
$(BUILD)/astra_main.o: ../games/astra/src/astra_scene.h ../games/astra/src/astra_assets.h gpu.h gpu_v1.h
$(BUILD)/astrilla_main.o: ../games/common/astrilla/astrilla_geometry.h gpu_geometry.h ../games/common/astrilla/astrilla_hud.h ../games/common/astrilla/astrilla_hud_font.h ../games/common/astrilla/astrilla_scene.h ../games/common/astrilla/astrilla_assets.h ../games/common/astrilla/astrilla_meshes.h ../games/common/astrilla/astrilla_3d.h ../games/common/astrilla/astrilla_flight.h gpu.h gpu_v1.h
$(BUILD)/world3d_main.o: ../games/world3d/src/world3d_scene.h ../games/common/astrilla/astrilla_geometry.h gpu_geometry.h ../games/common/astrilla/astrilla_hud.h ../games/common/astrilla/astrilla_hud_font.h ../games/common/astrilla/astrilla_scene.h ../games/common/astrilla/astrilla_assets.h ../games/common/astrilla/astrilla_meshes.h ../games/common/astrilla/astrilla_3d.h ../games/common/astrilla/astrilla_flight.h gpu.h gpu_v1.h
$(BUILD)/sd.o $(BUILD)/sd_ae350.o $(BUILD)/sd_test_main.o $(BUILD)/diskio.o $(BUILD)/usb_disk_main.o: sd.h
$(BUILD)/sd_ae350.o $(BUILD)/prodock-spi-pio.o: ../linux/drivers/prodock-spi-pio.h
$(BUILD)/usb_msc.o $(BUILD)/usb_disk_main.o: usb_msc.h
$(BUILD)/ff.o $(BUILD)/diskio.o $(BUILD)/sd_test_main.o: fatfs/ff.h fatfs/ffconf.h fatfs/diskio.h fatfs/integer.h
$(BUILD)/gpu_diag.o: gpu_v1.h gpu_v1_scene.h gpu_v1_demo.h gpu_v1_expected.h
$(BUILD)/gpu_diag.o: gpu_raster_scene.h gpu_raster_reference.h gpu_raster_demo.h gpu_rgb_overlay_scene.h
$(BUILD)/gpu_diag.o: gpu.h gpu_demo.h gpu_palette.h gpu_layers_demo.h gpu_sprites_demo.h gpu_3d_scene.h gpu_3d_demo.h ../games/racer/src/racer_scene.h ../games/racer/src/racer_demo.h gpu_tiles_scene.h gpu_tiles_demo.h gpu_affine_scene.h gpu_affine_demo.h $(BUILD)/gpu_font.h
$(BUILD)/gpu_font.h: ../tang/rtl/video/font8x16.hex ../tools/gen_gpu_font.py | $(BUILD)
	python3 ../tools/gen_gpu_font.py $< $@
$(BUILD)/start.o: $(BSP_ASM) | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/$(APP).elf: $(OBJS) $(LD) $(FW_DIR)support/gnu_symbols.ld
	$(CC) $(LDFLAGS) -T $(LD) $(OBJS) -o $@ -Wl,-Map=$(BUILD)/$(APP).map
$(BUILD)/$(APP).bin: $(BUILD)/$(APP).elf
	$(OBJCOPY) -O binary $< $@
# ITCM_INIT_PATH uses four byte lanes: itcm0 through itcm3.
$(ITCM_FILES) &: $(BUILD)/$(APP).bin $(FW_DIR)support/itcm_init.py
	$(PYTHON) $(FW_DIR)support/itcm_init.py $< $(BUILD)/itcm
$(BUILD):
	mkdir -p $@
clean:
	rm -rf $(BUILD)

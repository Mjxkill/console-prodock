include /home/michael/logic_analyser_wifi/ae350/toolchain.mk
APP   = console_test
BUILD = build
MAIN ?= main.c
LD    = /home/michael/console/fw_console/itcm.ld
# EXTRA_SRCS : sources propres à une application téléchargée (par exemple la carte SD et FatFs).
EXTRA_SRCS ?=
SRCS  = $(MAIN) gpu.c gpu_v1.c $(EXTRA_SRCS) $(filter-out $(AE350_SDK)/bsp/lib/read.c,$(BSP_SRCS))
OBJS  = $(patsubst %.c,$(BUILD)/%.o,$(notdir $(SRCS))) $(BUILD)/start.o
CFLAGS += -Os -DCFG_XIP   # Le BSP copie les données initialisées de l'ITCM vers l'ILM.
vpath %.c $(sort $(dir $(SRCS)))   # seulement les .c : sinon make trouve les .o d'un autre dossier build
all: $(BUILD)/$(APP).bin $(BUILD)/itcm/itcm0
	$(SIZE) $(BUILD)/$(APP).elf
$(BUILD)/%.o: %.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/gpu.o: gpu.h gpu_v1.h
$(BUILD)/gpu_v1.o: gpu.h gpu_v1.h
$(BUILD)/luma_main.o: luma_scene.h luma_fx_scene.h luma_assets.h gpu.h gpu_v1.h
$(BUILD)/orbital_main.o: orbital_scene.h orbital_assets.h gpu.h gpu_v1.h
$(BUILD)/sd.o $(BUILD)/sd_ae350.o $(BUILD)/sd_test_main.o $(BUILD)/diskio.o $(BUILD)/usb_disk_main.o: sd.h
$(BUILD)/usb_msc.o $(BUILD)/usb_disk_main.o: usb_msc.h
$(BUILD)/ff.o $(BUILD)/diskio.o $(BUILD)/sd_test_main.o: fatfs/ff.h fatfs/ffconf.h fatfs/diskio.h fatfs/integer.h
$(BUILD)/gpu_diag.o: gpu_v1.h gpu_v1_scene.h gpu_v1_demo.h gpu_v1_expected.h
$(BUILD)/gpu_diag.o: gpu_raster_scene.h gpu_raster_reference.h gpu_raster_demo.h gpu_rgb_overlay_scene.h
$(BUILD)/gpu_diag.o: gpu.h gpu_demo.h gpu_palette.h gpu_layers_demo.h gpu_sprites_demo.h gpu_3d_scene.h gpu_3d_demo.h racer_scene.h racer_demo.h gpu_tiles_scene.h gpu_tiles_demo.h gpu_affine_scene.h gpu_affine_demo.h $(BUILD)/gpu_font.h
$(BUILD)/gpu_font.h: ../tang/rtl/video/font8x16.hex ../tools/gen_gpu_font.py | $(BUILD)
	python3 ../tools/gen_gpu_font.py $< $@
$(BUILD)/start.o: $(BSP_ASM) | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/$(APP).elf: $(OBJS) $(LD)
	$(CC) $(LDFLAGS) -T $(LD) $(OBJS) -o $@ -Wl,-Map=$(BUILD)/$(APP).map
$(BUILD)/$(APP).bin: $(BUILD)/$(APP).elf
	$(OBJCOPY) -O binary $< $@
# image ITCM pour le bitstream (ITCM_INIT_PATH) : 4 fichiers itcm0..3 (comme v5_draw)
$(BUILD)/itcm/itcm0: $(BUILD)/$(APP).bin
	mkdir -p $(BUILD)/itcm
	python3 /home/michael/logic_analyser_wifi/ae350/tools/itcm_init.py $< $(BUILD)/itcm
$(BUILD):
	mkdir -p $@
clean:
	rm -rf $(BUILD)

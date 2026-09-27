include /home/michael/logic_analyser_wifi/ae350/toolchain.mk
APP   = console_test
BUILD = build
MAIN ?= main.c
LD    = /home/michael/console/fw_console/itcm.ld
SRCS  = $(MAIN) gpu.c $(filter-out $(AE350_SDK)/bsp/lib/read.c,$(BSP_SRCS))
OBJS  = $(patsubst %.c,$(BUILD)/%.o,$(notdir $(SRCS))) $(BUILD)/start.o
CFLAGS += -DCFG_XIP   # Le BSP copie les données initialisées de l'ITCM vers l'ILM.
vpath %.c $(sort $(dir $(SRCS)))   # seulement les .c : sinon make trouve les .o d'un autre dossier build
all: $(BUILD)/$(APP).bin $(BUILD)/itcm/itcm0
	$(SIZE) $(BUILD)/$(APP).elf
$(BUILD)/%.o: %.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/gpu.o: gpu.h
$(BUILD)/gpu_diag.o: gpu.h gpu_demo.h $(BUILD)/gpu_font.h
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

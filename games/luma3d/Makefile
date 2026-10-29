CC ?= cc
RISCV_CC ?= ../../linux/build/userbin/riscv32-prodock-linux-gcc
CPPFLAGS = -Iinclude -Iworld -I../../fw_console -I../../linux/drivers
CFLAGS = -std=c11 -O2 -Wall -Wextra -Werror -Wno-misleading-indentation -ffp-contract=off -ffunction-sections -fdata-sections
WORLD_DATA ?= world/data.c
SOURCES = src/main.c src/game.c src/world.c src/render.c $(WORLD_DATA) ../../fw_console/gpu_v1.c ../../fw_console/gpu_geometry.c
HEADERS = include/luma3d_game.h include/luma3d_render.h world/generated.h ../../linux/drivers/prodock-uapi.h ../../linux/drivers/prodock-validate.h
.PHONY: all riscv test
all: build/luma3d-host
riscv: build/luma3d-riscv
build/luma3d-host: $(SOURCES) $(HEADERS)
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) $(SOURCES) -Wl,--gc-sections -lm -o $@
build/luma3d-riscv: $(SOURCES) $(HEADERS)
	mkdir -p build
	$(RISCV_CC) $(CPPFLAGS) $(CFLAGS) -static $(SOURCES) -Wl,--gc-sections -lm -o $@
build/test-game: src/game.c tests/test_game.c include/luma3d_game.h
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/game.c tests/test_game.c -lm -o $@
test: build/test-game build/luma3d-host
	./build/test-game
	python3 tests/test_world_game.py
	./build/luma3d-host --host --frames 1 --capture build/arrival
	python3 tools/render_reference.py build/arrival

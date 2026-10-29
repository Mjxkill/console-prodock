CC ?= cc
RISCV_CC ?= ../../linux/build/userbin/riscv32-prodock-linux-gcc
CPPFLAGS = -Iinclude -Ibuild -Iaudio -I../../linux/drivers -I../../linux/userspace
CFLAGS = -O2 -std=c11 -Wall -Wextra -Werror -Wno-misleading-indentation
COMMON = src/game.c src/missions.c src/light.c src/save.c build/world.c
VIDEO = src/video.c src/main.c src/host_input.c audio/luma_audio.c
ASSET_INPUTS = $(wildcard content/world*.json content/campaign*.json content/*/*.json art/*.png art/atlas.json art/terrain.json audio/manifest.json)
.PHONY: all assets test clean preview riscv
all: build/luma
assets: build/assets.h
build/assets.h build/world.c build/music.h &: tools/build_assets.py $(ASSET_INPUTS)
	python3 tools/build_assets.py
build/luma: $(COMMON) $(VIDEO) include/luma.h include/stepper.h include/host_input.h include/video.h build/assets.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -DLUMA_HOST $(shell pkg-config --cflags sdl2) $(COMMON) $(VIDEO) -o $@ $(shell pkg-config --libs sdl2) -lm
riscv: build/luma-riscv
build/luma-riscv: $(COMMON) $(VIDEO) include/luma.h include/stepper.h include/host_input.h include/video.h build/assets.h
	$(RISCV_CC) $(CPPFLAGS) $(CFLAGS) -static $(COMMON) $(VIDEO) -lm -o $@
build/test-codec: $(COMMON) src/video.c tests/test_codec.c include/luma.h include/video.h build/assets.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -g -fsanitize=address,undefined $(COMMON) tests/test_codec.c -lm -llz4 -o $@
build/test-render: $(COMMON) src/video.c tests/test_render.c include/luma.h include/video.h build/assets.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(COMMON) src/video.c tests/test_render.c -lm -o $@
build/test-save: $(COMMON) build/assets.h tests/test_save.c include/luma.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -g -fsanitize=address,undefined $(COMMON) tests/test_save.c -lm -o $@
build/test-puzzles: $(COMMON) build/assets.h tests/test_puzzles.c include/luma.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -g -fsanitize=address,undefined $(COMMON) tests/test_puzzles.c -lm -o $@
build/test-game: $(COMMON) build/assets.h tests/test_game.c include/luma.h include/stepper.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -g -fsanitize=address,undefined $(COMMON) tests/test_game.c -lm -o $@
build/puzzle_witness.h: tools/build_witness.py content/campaign.json $(wildcard content/*/solutions.json)
	python3 tools/build_witness.py
build/play-dungeon: $(COMMON) build/assets.h tests/play_dungeon.c tests/play_input.h tests/play_dungeon.h build/puzzle_witness.h include/luma.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(COMMON) tests/play_dungeon.c -lm -o $@
build/play-campaign: $(COMMON) build/assets.h tests/play_campaign.c tests/play_input.h tests/play_dungeon.h build/puzzle_witness.h include/luma.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(COMMON) tests/play_campaign.c -lm -o $@
test: build/test-light build/test-text build/test-host-input build/test-codec build/test-render build/play-dungeon build/test-save build/test-puzzles build/test-game build/play-campaign build/luma
	ASAN_OPTIONS=detect_leaks=0 ./build/test-light
	python3 tests/test_light_contract.py
	./build/test-text
	SDL_VIDEODRIVER=dummy ./build/test-host-input
	ASAN_OPTIONS=detect_leaks=0 ./build/test-codec
	./build/test-render
	ASAN_OPTIONS=detect_leaks=0 ./build/test-save
	ASAN_OPTIONS=detect_leaks=0 ./build/test-puzzles
	ASAN_OPTIONS=detect_leaks=0 ./build/test-game
	./build/play-dungeon
	./build/play-campaign
	./build/luma --headless --no-save --frames 180 --demo --snapshot build/preview_800.ppm
	./build/luma --headless --no-save --720p --frames 60 --demo --snapshot build/preview_720p.ppm
preview: build/luma
	./build/luma
clean:
	@echo 'Build artifacts are kept for review. Remove only this game build/ manually if needed.'

# Experimental layer-scrolling backend; baseline build/ remains independently usable.
INDEX_CPPFLAGS = -Iinclude -Ibuild/indexed -Iaudio -I../../linux/drivers -I../../linux/userspace
INDEX_COMMON = src/game.c src/missions.c src/light.c src/save.c build/indexed/world.c
.PHONY: indexed indexed-riscv
indexed: build/indexed/luma
indexed-riscv: build/indexed/luma-riscv
build/indexed/assets.h build/indexed/world.c build/indexed/music.h &: tools/build_assets.py $(ASSET_INPUTS)
	python3 tools/build_assets.py --indexed
build/indexed/luma: $(INDEX_COMMON) $(VIDEO) include/luma.h include/stepper.h include/host_input.h include/video.h build/indexed/assets.h
	$(CC) $(INDEX_CPPFLAGS) $(CFLAGS) -DLUMA_HOST $(shell pkg-config --cflags sdl2) $(INDEX_COMMON) $(VIDEO) -o $@ $(shell pkg-config --libs sdl2) -lm
build/indexed/luma-riscv: $(INDEX_COMMON) $(VIDEO) include/luma.h include/stepper.h include/host_input.h include/video.h build/indexed/assets.h
	$(RISCV_CC) $(INDEX_CPPFLAGS) $(CFLAGS) -static $(INDEX_COMMON) $(VIDEO) -lm -o $@
build/indexed/test-render: $(INDEX_COMMON) src/video.c tests/test_render.c include/luma.h include/video.h build/indexed/assets.h
	$(CC) $(INDEX_CPPFLAGS) $(CFLAGS) -DLUMA_TEST_ASSETS='"build/indexed/luma.pak"' $(INDEX_COMMON) src/video.c tests/test_render.c -lm -o $@
build/indexed/test-indexed: $(INDEX_COMMON) src/video.c tests/test_indexed.c include/luma.h include/video.h build/indexed/assets.h
	$(CC) $(INDEX_CPPFLAGS) $(CFLAGS) $(INDEX_COMMON) src/video.c tests/test_indexed.c -lm -o $@
build/test-host-input: tests/test_host_input.c src/host_input.c include/host_input.h include/luma.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -DLUMA_HOST $(shell pkg-config --cflags sdl2) src/host_input.c tests/test_host_input.c -o $@ $(shell pkg-config --libs sdl2)
build/test-text: $(COMMON) src/video.c tests/test_text.c include/luma.h include/video.h build/assets.h
	$(CC) $(CPPFLAGS) $(CFLAGS) $(COMMON) tests/test_text.c -lm -o $@

.PHONY: test-indexed
test-indexed: build/indexed/test-indexed build/indexed/test-render build/indexed/luma
	./build/indexed/test-indexed
	./build/indexed/test-render
	python3 tests/reference_capture.py build/indexed/effects_480 build/indexed/effects_720
	python3 tests/reference_capture.py build/indexed/light_480 build/indexed/light_720

build/test-light: src/game.c src/missions.c src/light.c src/save.c tests/test_light.c include/luma.h
	$(CC) $(CPPFLAGS) $(CFLAGS) -g -fsanitize=address,undefined src/game.c src/missions.c src/light.c src/save.c tests/test_light.c -lm -o $@

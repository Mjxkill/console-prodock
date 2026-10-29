#ifndef L3_MINIGAMES_H
#define L3_MINIGAMES_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define L3_MINI_VERSION 1u
#define L3_MINI_STRIDE 20u
#define L3_MINI_CELLS 400u
#define L3_MINI_SAVE_BYTES 1008u
#define L3_MINI_MAX_DT_MS 250u

typedef enum L3MiniKind {
    L3_MINI_CIRCUIT, L3_MINI_BLOCKS, L3_MINI_SHAPES,
    L3_MINI_MERGE1024, L3_MINI_MAZE, L3_MINI_KIND_COUNT
} L3MiniKind;

typedef enum L3MiniStatus {
    L3_MINI_RUNNING, L3_MINI_WON, L3_MINI_LOST,
    L3_MINI_PLAYING = L3_MINI_RUNNING
} L3MiniStatus;

enum {
    L3_MINI_UP = 1u, L3_MINI_DOWN = 2u,
    L3_MINI_LEFT = 4u, L3_MINI_RIGHT = 8u,
    L3_MINI_ACT = 16u, L3_MINI_ROTATE = 32u, L3_MINI_BACK = 64u,
    L3_MINI_INPUT_MASK = 127u
};
enum {
    L3_MINI_EVENT_CHANGED = 1u, L3_MINI_EVENT_WON = 2u,
    L3_MINI_EVENT_LOST = 4u, L3_MINI_EVENT_EXIT = 8u,
    L3_MINI_EVENT_INVALID = 16u
};
typedef enum L3MiniCellKind {
    L3_MINI_CELL_EMPTY, L3_MINI_CELL_WALL, L3_MINI_CELL_WIRE,
    L3_MINI_CELL_BLOCK, L3_MINI_CELL_TARGET, L3_MINI_CELL_NUMBER,
    L3_MINI_CELL_PLAYER, L3_MINI_CELL_ENEMY, L3_MINI_CELL_PELLET,
    L3_MINI_CELL_POWER, L3_MINI_CELL_START, L3_MINI_CELL_FINISH
} L3MiniCellKind;
enum {
    L3_MINI_FLAG_CURSOR = 1u, L3_MINI_FLAG_ACTIVE = 2u,
    L3_MINI_FLAG_CONNECTED = 4u, L3_MINI_FLAG_GHOST = 8u
};

/* Opaque to callers: use view/encode/decode, never write these members.
 * Integer storage is naturally aligned, has no pointers or compiler unions.
 * sizeof is 992 on supported C ABIs, always <=4096. Not a wire format. */
typedef struct L3MiniState {
    uint32_t meta[16];
    uint32_t data[32];
    uint8_t board[L3_MINI_CELLS];
    uint8_t aux[L3_MINI_CELLS];
} L3MiniState;

typedef struct L3MiniCell {
    uint16_t value; /* wire N/E/S/W bits 1/2/4/8; number actual 2..1024 */
    uint8_t kind, color, flags, glyph; /* color is a logical index 0..15 */
} L3MiniCell;

typedef struct L3MiniView {
    L3MiniCell cells[L3_MINI_CELLS]; /* index y*L3_MINI_STRIDE+x */
    uint32_t kind, status, score, target, moves, elapsed_ms;
    uint16_t width, height;
    int16_t cursor_x, cursor_y; /* -1 if no cursor */
    uint16_t lives, progress;
    const char *title, *help, *objective; /* static French strings */
} L3MiniView;

/* Invalid arguments return 0 and leave destination intact. seed=0 is valid. */
int l3_mini_init(L3MiniState *state, L3MiniKind kind, uint32_t seed);
/* dt_ms is clamped to250. Internally fixed60Hz with saved fractional phase.
 * Fronts execute once immediately, even at dt=0. held never synthesizes fronts.
 * BACK has priority and returns EXIT with byte-identical state, no time spent.
 * Finished states stay frozen. Restart via init(kind,seed); resume by retaining
 * state. Integration must release/latch buttons before entering/restarting. */
uint32_t l3_mini_step(L3MiniState *state, uint32_t pressed,
                      uint32_t held, uint32_t dt_ms);
int l3_mini_view(const L3MiniState *state, L3MiniView *view);
int l3_mini_validate(const L3MiniState *state);
/* Fixed portable LE format, checksum and strict semantic validation.
 * Decode is transactional: dst unchanged on every failure, exact length only.
 * Encode returns byte count or0; NULL output returns required size if valid. */
size_t l3_mini_encode(const L3MiniState *state, void *output, size_t capacity);
int l3_mini_decode(L3MiniState *state, const void *input, size_t size);
/* Deterministic demo adviser; returns ordinary inputs, never changes state.
 * Calling step with these inputs obeys precisely the human game's rules.
 * Does not guarantee victory for arbitrary already-damaged positions. */
int l3_mini_demo_input(const L3MiniState *state, uint32_t *pressed,
                       uint32_t *held, uint32_t *dt_ms);

#ifdef __cplusplus
}
#endif
#endif

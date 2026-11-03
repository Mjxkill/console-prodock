# API Reference — Pro Dock GPU and Linux interfaces

This reference describes the interfaces that the published source snapshot
actually exposes, as reviewed on 3 November 2026. It is an inventory of
entrypoint groups, not a claim that every symbol or historical variant is
listed. The frozen executable referenced by the contract is the MAZE
candidate with SHA-256
`2e552dd1cc9b73756b68040b75c4c0a8f9c62c6584dbadd4fcb38e7933c4b985`;
the interfaces below do not by themselves qualify that build on hardware.

The source map is deliberately short:

| Area | Maintained declaration | Contract document |
|---|---|---|
| Legacy 2D, composition, tiles, sprites | [fw_console/gpu.h](../fw_console/gpu.h) | [ARCHI/GPU_G3_REGISTRES.md](../ARCHI/GPU_G3_REGISTRES.md), [ARCHI/GPU_G4_REGISTRES.md](../ARCHI/GPU_G4_REGISTRES.md) |
| V1 raster, textures, targets | [fw_console/gpu_v1.h](../fw_console/gpu_v1.h) | [ARCHI/GPU_V1.md](../ARCHI/GPU_V1.md) |
| Fixed-function geometry G3D1 | [fw_console/gpu_geometry.h](../fw_console/gpu_geometry.h) | [ARCHI/GPU_GEOMETRY.md](../ARCHI/GPU_GEOMETRY.md) |
| Linux ioctl/mmap ABI | [linux/drivers/prodock-uapi.h](../linux/drivers/prodock-uapi.h) | [linux/README.md](../linux/README.md) |
| Linux command/scene validation | [linux/drivers/prodock-validate.h](../linux/drivers/prodock-validate.h) | driver source below |
| A25 cache maintenance | [linux/drivers/prodock-cache.h](../linux/drivers/prodock-cache.h) | [ARCHI/GPU_V1.md](../ARCHI/GPU_V1.md) |
| Linux GPU provider | [linux/drivers/prodock-gpu.c](../linux/drivers/prodock-gpu.c) | [ARCHI/LINUX_AFFICHAGE_PARTAGE.md](../ARCHI/LINUX_AFFICHAGE_PARTAGE.md) |
| Shared AE350 SPI engine | [linux/drivers/prodock-spi.c](../linux/drivers/prodock-spi.c) | build and transfer notes in [SOFTWARE_DEVELOPMENT.md](SOFTWARE_DEVELOPMENT.md) |

The shared SPI engine is declared in `linux/drivers/prodock-spi-pio.h` and
implemented in `linux/drivers/prodock-spi-pio.c`. Its internal interface is
separate from the userspace GPU ABI. The exact MAZE sources and build recipe
are preserved in the [source release](../releases/luma3d-maze-20261103/README.md).

Header style is not uniform. The legacy and V1 public headers contain types,
constants and prototypes. `prodock-validate.h` and `prodock-cache.h` contain
`static inline` helpers; that is an observed property of this snapshot, not
a statement that it satisfies the project rule that developed headers expose
only declarations. The rule is a development requirement, not a claim about
all historical source.

## 1. Common units, packing and addresses

- Legacy pages are `GPU_PAGE_BYTES = 1048576` (1 MiB). `GPU_PAGE_ADDR(p)`
  is `0x00800000 + p * 1 MiB`. The page fields are four bits wide, so the
  page-indexed builders carry pages 0…15; the address macro itself does not
  clamp its argument.
- V1 uses byte addresses in the first GiB and requires all bases and pitches
  to be multiples of 32 bytes. Geometry limits its buffers to the first
  512 MiB. Under Linux the exposed accelerator window is narrower:
  `PRODOCK_GPU_BASE = 0x00800000`, `PRODOCK_GPU_BYTES = 0x05600000`
  (86 MiB), with `PRODOCK_RESERVED_BYTES = 0x05800000` (2 MiB reserved for
  the display manager on top of the 86 MiB).
- Pixels are little-endian. Indexed surfaces use one byte per pixel and a
  global 256-entry RGB666 palette. V1 colour targets are RGB565, two bytes
  per pixel, converted to the panel's RGB666. ARGB4444 is the texture format
  with alpha; it is not a compositor layer format.
- `XY(x, y)` packs `x` in the high 16 bits and `y` in the low 16 bits.
  Legacy rectangle and copy coordinates are signed 16-bit; V1 dimensions and
  counts are unsigned. G3D1 positions and matrix coefficients are signed
  Q16.16, while normals and light directions are Q1.15.
- The Pro Dock panel is 800 × 480 at a nominal 55.04 Hz. The reduced game
  mode renders 400 × 240 and is doubled by the hardware. Neo is a 1280 × 720
  HDMI profile; it is not hardware-qualified by the Pro Dock documents.

## 2. Legacy 2D command group (`gpu.h`)

`gpu_command` is exactly eight 32-bit words (32 bytes). The opcode is
`word[0][31:24]`; the destination page occupies bits 20…23 and the source
page bits 16…19 for page-indexed operations. `gpu_make_command()` builds one
word set, and `gpu_submit()` writes all eight words to the accelerator FIFO
and advances the software command counter. It returns nothing and does not
wait.

The legacy opcodes are 1…21: fill, horizontal/vertical/diagonal gradients,
line, circle, disk, copy, text, triangle, zoom, affine setup/draw, raster
state, texture, planes U/V/Z/Q, raster triangle and raster clear. Helpers
include `gpu_triangle()`, `gpu_text()`, `gpu_font_write()`,
`gpu_make_zoom()`, `gpu_make_affine_setup()`, `gpu_make_affine()`,
`gpu_make_raster_state()`, `gpu_make_texture()`, `gpu_make_plane()` and
`gpu_make_raster_clear()`.

Documented limits in the header are:

- Zoom and affine source crops are 1…128 pixels per axis; destination
  dimensions are 1…32767. Sampling uses Q16 fixed point and floor. The
  affine inverse transform has six signed Q16.16 coefficients.
- A triangle takes signed 16-bit coordinates. Filled triangles use pixel
  centres and the top-left rule; outlines use three accelerated lines.
- Legacy text scale is 1 or 2. The font address field is 12 bits (a 4 KiB
  window); `gpu_font_write()` writes the caller-supplied count.
- Requests rejected by `gpu_make_zoom()`/`gpu_make_affine()` (zero or oversized
  destination, crop outside 1…128) leave a zero length field so the GPU rejects
  the packet. `gpu_make_affine()` also checks its origin and source crop against
  the 800 × 480 page. Other semantic violations, such as zoom using the same
  source and destination page, are not checked by these builders and remain the
  caller's responsibility. A returned command is not proof of acceptance.

Capability probes are `gpu_affine_supported()`, `gpu_raster_supported()`,
`gpu_perspective_supported()` and `gpu_tiles_supported()`. They read
hardware capability bits; a true result describes the bitstream, not a
guarantee that a particular scene fits the line budget. `gpu_errors()` ORs
the legacy error counters; V1 rejection and G3D1 statistics have separate probes, `gpu_completed()` reads the 16-bit completion
count, and `gpu_wait()` polls that count against the number of submitted
commands. `gpu_wait()` has a bounded iteration count and returns 0 on
timeout or when `gpu_errors()` is non-zero.

## 3. Composition: layers, sprites and tiles (`gpu.h`)

A `gpu_layer` descriptor is eight 32-bit words. Up to 16 layers are described,
index 0 at the back and 15 at the front. Layers may be indexed surfaces or
tile-map layers. A `gpu_sprite` is four words; there are 64 native 2D sprite
descriptors. Sprite size is 1…32 pixels on each axis, images have a 32-byte
aligned base and a fixed 32-byte line pitch, index zero is transparent, and
priority 0…15 places a sprite above the layer of the same number and below
the next layer. A higher sprite table index wins a priority tie.

`gpu_make_tile_layer()` describes a map of `2^map_w_log2` by
`2^map_h_log2` 16-bit entries, with log2 in 4…12 (16…4096 tiles per axis).
Tile size is 8, 16 or 32 pixels. Tiles are read from an atlas of up to 8192
tiles, tile `i` starting at `atlas + i * size * size`. Map and atlas bases
must be 32-byte aligned and lie in the first GiB. An unsupported tile size is
encoded as code 3 so that the GPU counts and rejects the layer. The same
descriptor supports index-zero keying, X/Y wrapping and an enable bit.

`gpu_layers_submit()` waits for any previous display commit, uploads all 16
descriptors to the inactive bank, requests a vertical-blank swap and returns
after the request is written. It does not wait for the new swap to be applied. `gpu_scene_submit()` additionally writes the
64 sprite descriptors. `gpu_rgb565_scene_submit()` selects an RGB565 page as
the background. `gpu_display_wait()` waits until the display commit is no
longer busy; call it before reusing a bank or a displayed surface.

Two limits are often confused. Sixteen layers and 64 sprites are descriptor
capacities. They do not guarantee 16 full-frame layers plus 64 sprites at
every resolution and load. The available cycles per line depend on the board clock/timing profile;
inspect `PRODOCK_DISPLAY_GEOMETRY.line_budget` and the workload/underflow
counters for the configuration actually running. Indexed key transparency is separate from
the V1 raster alpha path described below. The 3D billboards used by games are
textured meshes in the G3D1 pipeline; they do not consume one of the 64
native 2D sprite slots.

## 4. V1 raster and surface group (`gpu_v1.h`)

V1 adds opcodes 22…30 and a portable context whose `emit` callback receives
each eight-word command. `gpu_v1_init()` binds the callback. The context does
not create a second producer and does not serialize access: the application
must keep one command producer and must not interleave GPU and CPU writes to
the same surface.

| Opcode | Builder | Main fields and limits |
|---|---|---|
| 22 TARGET | `gpu_v1_target()` | Colour and Z16 byte addresses; width 1…1024, height 1…512; pitches 32-byte aligned, at least `width * 2`, at most 65535; colour and depth ranges must be disjoint; both within the first GiB. Resets the scissor to the full target. |
| 23 SCISSOR | `gpu_v1_scissor()` | The C API takes x, y, width, height; the packet encodes exclusive right/bottom. Bounded by the target; an empty region is allowed. |
| 24 TEXTURE | `gpu_v1_texture()` | Base, width and height 1…512, pitch 32-byte aligned, format RGB565 or ARGB4444, U/V modes discard/repeat/clamp, LOD 0…9. Repeat mode requires a power-of-two axis. |
| 25 MATERIAL | `gpu_v1_material()` | Flags (texture, Z test, Z write, key zero, perspective, additive, Gouraud, fog), alpha 0…256, solid colour, per-channel gains 0…256, fog near/colour and a Q16 slope up to `0x1000000`. Perspective requires texture. |
| 26 PLANE | `gpu_v1_plane()` | Index 0…6 for U, V, Q, Z, R, G, B; signed 48-bit origin, signed 32-bit gradients. |
| 27 TRIANGLE | `gpu_v1_triangle()` | Three signed 16-bit screen vertices; UV are base-level texels; Z 0…65535; Q 0…`0xffffff`; gains 0…256. Zero-area triangles draw nothing. |
| 28 CLEAR | `gpu_v1_clear()` | Colour and/or depth mask, colour and depth values, signed position, width and height; respects the scissor. |
| 29 COPY | `gpu_v1_copy()` | RGB565 source to RGB565 destination; source region validated; overlap allowed only with identical base and pitch, with memmove semantics. |
| 30 INVALIDATE | `gpu_v1_invalidate()` | Invalidates texture-cache contents; does not clear counters. The current G3D1 cache is 1024 lines/32 KiB. |

The material flag values in the header are `GPU_V1_ADDITIVE = 32`,
`GPU_V1_GOURAUD = 64` and `GPU_V1_FOG = 128`; the first five flags are the
legacy texture/Z/key/perspective values. The effective alpha is
`(global_alpha * texel_alpha + 128) >> 8`; Gouraud replaces the uniform channel
gains with interpolated ones. Fog is a linear function of Z with the stated Q16 slope.

`gpu_v1_project()` maps signed Q16 normalised device coordinates into the
software viewport. `gpu_v1_viewport()` validates and records that mapping and
emits no command; the hardware scissor remains a separate command.
`gpu_v1_quad()` emits two triangles with vertices 0,1,2 and 0,2,3.

Textures and images use the same triangle pipeline. `gpu_v1_font()` expands a
4096-byte font into a 128 × 256 ARGB4444 atlas, organised as 16 columns of
8 × 16 glyphs; `gpu_v1_text()` then emits one textured quad per glyph. Text
scale is 1…16. `gpu_v1_image()`
and `gpu_v1_quad()` provide image, zoom and rotation without a second
rasteriser. `gpu_v1_asset_level()` validates a `.gtex` container and returns
the descriptor for one level; it does not copy the bytes to DDR.

A `.gtex` container begins with eight little-endian `u32` values: magic
`0x31545647`, ABI 1, format 0 or 1, level count 1…10, base width and height
1…512, total byte size, and a zero reserved word. Four `u32` per level follow:
32-byte aligned offset, packed width/height, 32-byte aligned pitch and the
explicit LOD. The data offset is rounded up to 32 bytes. Mipmap levels are
precomputed; the shader does not derive derivatives or blend trilinearly.

`gpu_rgb565_surface_submit()` accepts exactly 800 × 480 or 400 × 240, with
the matching native or doubled presentation format. It validates the colour
base, pitch and range, then commits the scene. It waits at entry for the
previous commit but does not wait for the new one; use `gpu_display_wait()`
before reusing the surface.

## 5. Fixed-function geometry G3D1 (`gpu_geometry.h`)

G3D1 is an optional frontend on the same ordered V1 queue and fence. Its
opcodes are 31 (MATRIX), 32 (CAMERA), 33 (LIGHT) and 34 (DRAW); each command
is still eight 32-bit words. `gpu_geom_supported()` reads the signature
register and returns true only for `0x47334431`.

A vertex is 32 bytes: signed Q16.16 `x`, `y`, `z` followed by five reserved
words that must be zero. A face is 32 bytes with eight documented words and
8-bit vertex indices. One mesh has 1…256 vertices and 1…65535 faces. Its
vertex and face bases must be 32-byte aligned, and every referenced byte must
remain in physical DDR below 512 MiB. `gpu_geom_draw()` validates the mesh descriptor, counts, alignment, ranges,
cull flag and unsupported Gouraud state before emitting DRAW. It does not
inspect every face record on the CPU; the hardware validates mesh contents. A failed DRAW may already have written earlier faces, so its
partial result must not be presented.

`gpu_geom_camera` carries signed Q16.16 near, far and focal lengths plus a
16-bit viewport centre. The builder requires a current target of 1…1024 by
1…512; near at least 4096 (1/16), far greater than near, both focals in
65536…`0x10000000`, and the centre inside the target. It also bounds the
viewport slope: `floor((pixels << 32) / focal)` must not exceed `8 * 65536`
on any side. `gpu_geom_set_camera()` emits one CAMERA command and does not
change the V1 target or scissor.

`gpu_geom_transform` is a 3 × 4 array of signed Q16.16 values, row-major.
`gpu_geom_set_transform()` always emits three MATRIX commands, one for each
row. The command sink must report its own submission failures; the void emit
callback does not make this three-command sequence transactional. A light is three Q1.15 components in object space plus ambient and
diffuse gains in 0…256. Lighting is exact Lambert for rotations and uniform
scales; with non-uniform scaling the caller supplies corrected normals or
uses emissive/unlit material. Face-record flags are `GPU_GEOM_EMISSIVE = 1` and
`GPU_GEOM_TWO_SIDED = 2`; these are not the DRAW culling field. `gpu_geom_draw()` takes a cull-backfaces boolean.
Flat lighting is part of this ABI; a Gouraud material is rejected by
both `gpu_geom_draw()` and `gpu_geom_instance()`.

`gpu_geom_instance()` checks that a transform is supplied, validates the mesh
and light, and bounds the cull flag before it emits the transform, light and
DRAW sequence. `gpu_geom_fixed()`
returns 0 for NaN and for values outside `[-32768, 32767.998]`; otherwise it
truncates the scaled value to Q16.16. `gpu_geom_billboard_transform()` builds a
camera-facing 3 × 4 matrix from a Q16.16 centre and half sizes and Q1.15
sine/cosine; the caller then submits a shared unit quad through
`gpu_geom_instance()`.

`gpu_geom_read_stats()` returns seven 32-bit counters in the order errors,
vertices, triangles, culled, intersections, slivers and cycles. They wrap
modulo 2^32. The Linux UAPI samples them after the synchronous SUBMIT fence
and exposes the same seven values through `PRODOCK_GEOMETRY_INFO`; they are not
an atomic snapshot while a draw is running.

## 6. Linux UAPI (`prodock-uapi.h`)

The device ABI is 1. The GPU node is `/dev/prodock-gpu`; the independent
layout and telemetry node is `/dev/prodock-display`. The GPU window starts at
`0x00800000` and is 86 MiB long; the following 2 MiB are reserved for the
display manager and are not part of the application mapping. `PRODOCK_BATCH_MAX`
is 64.

The principal structures, with the sizes observed in the header, are:

| Structure | Size | Contents |
|---|---:|---|
| `prodock_info` | 48 bytes | ABI, base/bytes, width/height, caps, done, errors, underflows, frames, checksum, faulted |
| `prodock_batch` | 2056 bytes | count, zero reserved word, 64 commands of eight words |
| `prodock_scene` | 1568 bytes | base, stride, format, enables, three reserved words, 16 × 8 layer words, 64 × 4 sprite words |
| `prodock_palette` | 1024 bytes | 256 RGB666 entries |
| `prodock_font` | 4096 bytes | raw font bytes |
| `prodock_geometry_info` | 32 bytes | signature and the seven G3D1 counters |

The ioctl numbers are `PRODOCK_INFO`, `PRODOCK_SUBMIT`, `PRODOCK_PRESENT`,
`PRODOCK_PALETTE`, `PRODOCK_FONT` and `PRODOCK_GEOMETRY_INFO` on the GPU node;
`PRODOCK_LAYOUT`, `PRODOCK_DISPLAY_INFO`, `PRODOCK_DEBUG_TEXT` and
`PRODOCK_DISPLAY_GEOMETRY` are on the display node. The display ioctls are
independent of exclusive accelerator ownership, so a running game can change
split/game/terminal layout and read telemetry.

Opening the GPU node requires `CAP_SYS_RAWIO`. Only one open is allowed; a
second open gets `EBUSY`, and a faulted device gets `EIO`. The file release
restores the framebuffer and returns a game layout to split mode. The driver
is not a DRM/Mesa/OpenGL driver and does not implement per-process GPU
virtual address spaces. This is distinct from the CPU MMU used by Linux.

`PRODOCK_SUBMIT` requires a non-empty batch of at most 64 commands, a zero
reserved word and commands that pass the kernel validator. The whole batch is
validated before any FIFO word is written. Batches containing opcodes 31…34
require the G3D1 signature, otherwise they return `EOPNOTSUPP`; old kernels
return `ENOTTY` for the geometry-info ioctl. The driver synchronises the A25
caches before and after the transfer, waits for the completion count and
checks the error counters. A timeout or an error during the transfer marks the device faulted: the
driver never replays a command whose outcome is unknown.

`PRODOCK_PRESENT` accepts scene formats 1, 3 and 7; format 7 is the
half-resolution RGB565 path. The layer and sprite enable fields are 0 or 1.
The scene base and stride, and every enabled layer or sprite base, must be
32-byte aligned and inside the 86 MiB window. With scene format 1 the scene
stride must equal the display width; an enabled indexed layer needs a pitch at
least its layer width. If `layers_enabled` is zero
the driver clears the layer table before committing; composition remains
enabled because that selects the pipelined RGB reader on C37. Enabling any of
the reserved console layers 12…15, or a sprite with priority 12 or higher,
returns `EBUSY`. The driver waits for the previous commit, writes only the
descriptors that changed, then waits for the new commit and flips the
descriptor bank.

`PRODOCK_PALETTE` accepts 256 entries, requires entries 240…255 to be zero and
writes entries 0…239 as 18-bit RGB666. `PRODOCK_FONT` writes exactly 4096
bytes through the accelerator font port. A GPU mmap must be `MAP_SHARED`,
non-executable, and within the 86 MiB window; it is mapped noncached, but the
driver still performs explicit cache maintenance because `pgprot_noncached()`
alone is not sufficient on this A25.

Observed errno values are `EPERM` for a missing capability, `EBUSY` for a
second owner or a reserved display resource, `EIO` for a fault or a
pre-existing accelerator error, `EINVAL` for a malformed request, `ERANGE`
for an address/geometry range violation, `EFAULT` for a user-copy failure,
`EOPNOTSUPP` for a missing optional frontend and `ENOTTY` for an unknown
ioctl.

## 7. SPI engine interface

The shared SPI header is [`prodock-spi-pio.h`](../linux/drivers/prodock-spi-pio.h);
it declares an internal kernel/bare-metal interface, not a Linux UAPI. The
engine has one owner at a time, is 8-bit mode 0 full duplex, and leaves GPIO
chip selection to the platform adapter. `atcspi200_init()` validates the
controller clock and FIFO capacity while CS is inactive.
`atcspi200_set_speed()` is a setup-time operation; the Linux adapter invokes it
under the SPI core io_mutex with CS inactive.

`SPI_Master_send_receive()` exchanges chunks of at most 512 bytes and leaves
CS untouched between chunks; the caller owns its asserted/inactive state. A NULL TX buffer sends `0xff`; a NULL RX buffer still
drains the receive FIFO; a zero count performs no MMIO. Exact in-place TX/RX
is supported, other overlapping buffers are not. Success means all receive
data was consumed and the controller is no longer busy. On failure, partial
receive data is invalid; the Linux adapter preserves the original message
status, and
`atcspi200_recover()` must restore the controller before another exchange;
the adapter must deassert CS before recovery. The engine never changes GPIO
and never replays data.

## 8. Rules that apply across the interfaces

1. One producer owns the accelerator. The bare-metal V1 context does not
   serialise emitters, and the Linux node permits one open. Do not interleave
   CPU and GPU writes to a live surface.
2. CPU-written bytes must be published before a GPU read. The legacy path
   uses `gpu_publish_surface()`, which flushes the range and reads back the
   final byte; the V1 path requires the same publication followed by an
   ordered `gpu_v1_invalidate()` for texture memory. Binding a texture does
   not invalidate it. Under Linux, `PRODOCK_SUBMIT` performs the explicit SBI
   cache sync in both directions.
3. After GPU work, wait before reading a surface on the CPU. The legacy path
   uses `gpu_wait()` then a cache invalidate; the Linux path returns from
   `PRODOCK_SUBMIT` only after its synchronous fence and cache sync.
4. Commit and wait are separate. Layer and scene submission returns after the
   request is written; call `gpu_display_wait()` before reusing a displayed
   bank or buffer. `gpu_rgb565_surface_submit()` waits for the previous commit
   at entry but returns after requesting the new one. Linux PRESENT waits for
   both the previous and new commit. Neither makes the newly displayed buffer
   immediately available for CPU/GPU overwriting.
5. Builders report rejection by a zero return or an invalid packet marker;
   `gpu_submit()` is void and has no per-command acknowledgement. Check
   `gpu_errors()`/`gpu_wait()` or the Linux ioctl result rather than assuming
   that a submitted command succeeded.
6. Capacities are not guarantees: 16 layers, 64 sprites, 1…32 pixel sprites,
   tile sizes 8/16/32, a 1024 × 512 maximum V1 target, 512 × 512 textures,
   256 vertices and 65535 faces per mesh, and 64 commands per batch. The
   composition line budget can still be exceeded by a legal descriptor set.
7. The Pro Dock panel is 800 × 480 at a nominal 55.04 Hz. The 1280 × 720 Neo
   profile is a separate board target and is not hardware-qualified by the Pro
   Dock documents. No API here promises a frame rate or a visual result.

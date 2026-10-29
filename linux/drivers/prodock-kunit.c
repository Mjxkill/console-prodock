// SPDX-License-Identifier: GPL-2.0-or-later
#include <kunit/test.h>
#include "prodock-validate.h"
static void prodock_test_range(struct kunit *t)
{
    KUNIT_EXPECT_TRUE(t, prodock_range(PRODOCK_GPU_BASE, PRODOCK_GPU_BYTES));
    KUNIT_EXPECT_FALSE(t, prodock_range(PRODOCK_GPU_BASE - 1, 1));
    KUNIT_EXPECT_FALSE(t, prodock_range(PRODOCK_GPU_BASE + PRODOCK_GPU_BYTES, 1));
    KUNIT_EXPECT_FALSE(t, prodock_range(PRODOCK_GPU_BASE, 0x100000000ULL));
    KUNIT_EXPECT_FALSE(t, prodock_range(0xfffffff0U, 64));
}
static void prodock_test_commands(struct kunit *t)
{
    u32 c[8] = {22U << 24, 0x800000, 0xa00000, (800U << 16) | 480, (1600U << 16) | 1600};
    KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
    c[1] = 0x08000000; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[1] = c[2]; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[0] = 31U << 24; KUNIT_EXPECT_EQ(t, prodock_command(c), -EINVAL);
}
static void prodock_test_textures(struct kunit *t)
{
    u32 c[8] = {24U << 24, 0x2000000, (512U << 16) | 512, 1024};
    KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
    c[1] = 0x5fff000; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[1] = 0x2000000; c[3] = 1000; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[0] = 29U << 24; c[3] = 1024; KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
}
static void prodock_test_geometry_abi(struct kunit *t)
{
    KUNIT_EXPECT_EQ(t, PRODOCK_ABI, 1);
    KUNIT_EXPECT_EQ(t, sizeof(struct prodock_info), (size_t)48);
    KUNIT_EXPECT_EQ(t, sizeof(struct prodock_batch), (size_t)2056);
    KUNIT_EXPECT_EQ(t, sizeof(struct prodock_scene), (size_t)1568);
    KUNIT_EXPECT_EQ(t, sizeof(struct prodock_geometry_info), (size_t)32);
    KUNIT_EXPECT_EQ(t, sizeof(struct prodock_geom_vertex), (size_t)32);
    KUNIT_EXPECT_EQ(t, sizeof(struct prodock_geom_face), (size_t)32);
    KUNIT_EXPECT_EQ(t, _IOC_NR(PRODOCK_GEOMETRY_INFO), 5U);
}
static void prodock_test_geometry_matrix(struct kunit *t)
{
    u32 c[8] = {PRODOCK_GEOM_MATRIX << 24, 0, 0x80000000U, 0x7fffffffU};
    unsigned row, word;
    for (row = 0; row < 3; ++row) {
        c[1] = row; KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
    }
    c[1] = 3; KUNIT_EXPECT_EQ(t, prodock_command(c), -EINVAL); c[1] = 0;
    for (word = 6; word < 8; ++word) {
        c[word] = 1; KUNIT_EXPECT_EQ(t, prodock_command(c), -EINVAL); c[word] = 0;
    }
    c[0] |= 1; KUNIT_EXPECT_EQ(t, prodock_command(c), -EINVAL);
    c[0] = 35U << 24; KUNIT_EXPECT_EQ(t, prodock_command(c), -EINVAL);
}
static void prodock_test_geometry_camera(struct kunit *t)
{
    u32 c[8] = {PRODOCK_GEOM_CAMERA << 24, 4096, 1000U << 16,
        300U << 16, 300U << 16, (200U << 16) | 120, (400U << 16) | 240};
    KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
    c[1] = 4095; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE); c[1] = 4096;
    c[2] = 0x80000000U; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[2] = c[1]; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE); c[2]++;
    KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
    c[6] = (1025U << 16) | 240; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[6] = (400U << 16) | 513; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[6] = (400U << 16) | 240;
    c[5] = (401U << 16) | 120; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[5] = (200U << 16) | 120;
    c[3] = 65535; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[3] = 0x10000001U; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[3] = 0x10000000U; KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
    c[7] = 1; KUNIT_EXPECT_EQ(t, prodock_command(c), -EINVAL); c[7] = 0;
    /* The hardware truncates: 524288.5 is accepted, 524289 is rejected. */
    c[5] = 128U << 16; c[6] = (128U << 16) | 1; c[3] = 1048575;
    KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
    c[3]--; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
}
static void prodock_test_geometry_light(struct kunit *t)
{
    u32 c[8] = {PRODOCK_GEOM_LIGHT << 24, 0x8000ffffU, 0xffff, (256U << 16) | 256};
    unsigned word;
    KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
    c[2] |= 1U << 16; KUNIT_EXPECT_EQ(t, prodock_command(c), -EINVAL); c[2] = 0xffff;
    c[3] = 257; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[3] = 257U << 16; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE); c[3] = 0;
    for (word = 4; word < 8; ++word) {
        c[word] = 1; KUNIT_EXPECT_EQ(t, prodock_command(c), -EINVAL); c[word] = 0;
    }
}
static void prodock_test_geometry_draw(struct kunit *t)
{
    const u32 end = PRODOCK_GPU_BASE + PRODOCK_GPU_BYTES;
    u32 c[8] = {PRODOCK_GEOM_DRAW << 24, end - 256 * 32,
        end - 65535 * 32, (256U << 16) | 65535, 1};
    unsigned word;
    KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
    c[1] += 32; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE); c[1] -= 32;
    c[2] += 32; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE); c[2] -= 32;
    c[1] = PRODOCK_GPU_BASE - 32; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[1] = 0xffffffe0U; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[1] = PRODOCK_GPU_BASE + 1; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[1] = PRODOCK_GPU_BASE; c[3] = 1; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[3] = 257U << 16 | 1; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[3] = 1U << 16; KUNIT_EXPECT_EQ(t, prodock_command(c), -ERANGE);
    c[3] |= 1; KUNIT_EXPECT_EQ(t, prodock_command(c), 0);
    c[4] = 2; KUNIT_EXPECT_EQ(t, prodock_command(c), -EINVAL); c[4] = 0;
    for (word = 5; word < 8; ++word) {
        c[word] = 1; KUNIT_EXPECT_EQ(t, prodock_command(c), -EINVAL); c[word] = 0;
    }
}
static void prodock_test_scene(struct kunit *t)
{
    struct prodock_scene *s = kunit_kzalloc(t, sizeof(*s), GFP_KERNEL);
    KUNIT_ASSERT_NOT_NULL(t, s);
    s->base = 0x800000; s->stride = 1600; s->format = 3;
    KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), 0);
    s->base = 0x8000000; KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), -ERANGE);
    s->base = 0x800000; s->stride = 800; s->format = 7;
    KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), 0);
    s->stride = 65536; KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), -ERANGE);
}
static void prodock_test_layers(struct kunit *t)
{
    struct prodock_scene *s = kunit_kzalloc(t, sizeof(*s), GFP_KERNEL);
    KUNIT_ASSERT_NOT_NULL(t, s);
    s->base = 0x800000; s->stride = 800; s->format = 1; s->layers_enabled = 1;
    s->layers[0][0] = 0x1000000; s->layers[0][1] = 0x2000000;
    s->layers[0][5] = 0x44; s->layers[0][6] = 5;
    KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), 0);
    s->layers[0][5] = 0x106; /* ORBITAL: 64 columns, one row, 16x16 tiles. */
    KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), 0);
    s->layers[0][1] = 0x5ffffe0; KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), -ERANGE);
    s->layers[0][5] = 0x344; KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), -ERANGE);
}
static void prodock_test_sprites(struct kunit *t)
{
    struct prodock_scene *s = kunit_kzalloc(t, sizeof(*s), GFP_KERNEL);
    KUNIT_ASSERT_NOT_NULL(t, s);
    s->base = 0x800000; s->stride = 800; s->format = 1; s->sprites_enabled = 1;
    s->sprites[0][0] = 0x1000000; s->sprites[0][2] = (1 << 16) | (32 << 8) | 32;
    KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), 0);
    s->sprites[0][0] = 0xffffffe0U; KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), -ERANGE);
    s->sprites[0][0] = 0x1000000; s->sprites[0][2] |= 64;
    KUNIT_EXPECT_EQ(t, prodock_scene_valid(s), -ERANGE);
}
static struct kunit_case cases[] = {
    KUNIT_CASE(prodock_test_range), KUNIT_CASE(prodock_test_commands),
    KUNIT_CASE(prodock_test_textures), KUNIT_CASE(prodock_test_scene),
    KUNIT_CASE(prodock_test_geometry_abi), KUNIT_CASE(prodock_test_geometry_matrix),
    KUNIT_CASE(prodock_test_geometry_camera), KUNIT_CASE(prodock_test_geometry_light),
    KUNIT_CASE(prodock_test_geometry_draw),
    KUNIT_CASE(prodock_test_layers), KUNIT_CASE(prodock_test_sprites), {}
};
static struct kunit_suite suite = { .name = "prodock-gpu-bounds", .test_cases = cases };
kunit_test_suite(suite);
MODULE_LICENSE("GPL");

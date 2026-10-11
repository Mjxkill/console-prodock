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
    KUNIT_CASE(prodock_test_layers), KUNIT_CASE(prodock_test_sprites), {}
};
static struct kunit_suite suite = { .name = "prodock-gpu-bounds", .test_cases = cases };
kunit_test_suite(suite);
MODULE_LICENSE("GPL");

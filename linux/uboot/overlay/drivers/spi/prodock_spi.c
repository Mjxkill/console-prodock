// SPDX-License-Identifier: GPL-2.0-or-later
/* Same physical SPI/GPIO controller as Linux. No acquisition FPGA bridge. */
#include <dm.h>
#include <spi.h>
#include <time.h>
#include <asm/io.h>
#include <linux/delay.h>
#include <asm/unaligned.h>
struct prodock_spi { void __iomem *base, *gpio; };
static int wait_bits(struct prodock_spi *s, unsigned reg, u32 mask, bool set)
{
    ulong start = get_timer(0);
    for (unsigned n = 0; n < 1000000; ++n) {
        if (!!(readl(s->base + reg) & mask) == set) return 0;
        if (get_timer(start) >= 100) break;
    }
    return -ETIMEDOUT;
}
static int byte(struct prodock_spi *s, u8 out)
{
    int ret = wait_bits(s, 0x34, 1, false);
    if (ret) return ret;
    writel(7U << 8, s->base + 0x10);
    writel(6, s->base + 0x30);
    ret = wait_bits(s, 0x30, 6, false);
    if (ret) return ret;
    writel(0, s->base + 0x20); /* one byte each direction */
    writel(out, s->base + 0x2c); writel(0, s->base + 0x24);
    ret = wait_bits(s, 0x34, 1U << 14, false);
    if (ret) return ret;
    int in = readl(s->base + 0x2c) & 255;
    ret = wait_bits(s, 0x34, 1, false);
    return ret ? ret : in;
}
static int speed(struct udevice *bus, uint hz)
{
    struct prodock_spi *s = dev_get_priv(bus);
    if (!hz || hz < 156863) return -EINVAL;
    hz = min(hz, 20000000U);
    if (wait_bits(s, 0x34, 1, false)) return -ETIMEDOUT;
    writel((readl(s->base + 0x40) & ~255U) | (DIV_ROUND_UP(80000000U, 2 * hz) - 1), s->base + 0x40);
    return 0;
}
static int mode(struct udevice *bus, uint value) { return value == SPI_MODE_0 ? 0 : -EINVAL; }
static int claim(struct udevice *dev)
{
    struct prodock_spi *s = dev_get_priv(dev->parent);
    if (spi_chip_select(dev)) return -EINVAL;
    writel(1, s->gpio + 0x30);
    for (unsigned i = 0; i < 10; ++i) if (byte(s, 255) < 0) return -EIO;
    return 0;
}
static int release(struct udevice *dev)
{
    struct prodock_spi *s = dev_get_priv(dev->parent);
    writel(1, s->gpio + 0x30); return 0;
}
static int block(struct prodock_spi *s, const u8 *tx, u8 *rx, unsigned count)
{
    unsigned step = count >= 16 ? 4 : 1, sent = 0, got = 0;
    bool started = false;
    ulong start = get_timer(0);
    int ret = wait_bits(s, 0x34, 1, false);
    if (ret) return ret;
    writel(6, s->base + 0x30);
    ret = wait_bits(s, 0x30, 6, false);
    if (ret) return ret;
    writel((7U << 8) | (step == 4 ? BIT(7) : 0), s->base + 0x10);
    writel(((count - 1) << 12) | (count - 1), s->base + 0x20);
    for (unsigned budget = 0; sent < count || got < count; ++budget) {
        u32 status = readl(s->base + 0x34), word = ~0U;
        if (sent < count && !(status & BIT(23))) {
            if (tx) word = step == 4 ? get_unaligned_le32(tx + sent) : tx[sent];
            writel(word, s->base + 0x2c); sent += step;
        } else if (!started) { writel(0, s->base + 0x24); started = true; }
        if (sent == count && !started) { writel(0, s->base + 0x24); started = true; }
        if (started && got < count && !(status & BIT(14))) {
            word = readl(s->base + 0x2c);
            if (rx) {
                if (step == 4) put_unaligned_le32(word, rx + got);
                else rx[got] = word;
            }
            got += step;
        }
        if (budget == 1000000 || get_timer(start) >= 1000) return -ETIMEDOUT;
    }
    return wait_bits(s, 0x34, 1, false);
}
static int xfer(struct udevice *dev, unsigned bits, const void *out, void *in, unsigned long flags)
{
    struct prodock_spi *s = dev_get_priv(dev->parent);
    const u8 *tx = out; u8 *rx = in; int value;
    if (bits & 7) return -EINVAL;
    if (flags & SPI_XFER_BEGIN) writel(1, s->gpio + 0x2c);
    for (unsigned i = 0; i < bits / 8;) {
        unsigned n = min(512U, bits / 8 - i);
        if (n >= 16) n &= ~3U;
        value = block(s, tx ? tx + i : NULL, rx ? rx + i : NULL, n);
        if (value < 0) { release(dev); return value; }
        i += n;
    }
    if (flags & SPI_XFER_END) { release(dev); if (byte(s, 255) < 0) return -EIO; }
    return 0;
}
static int probe(struct udevice *dev)
{
    struct prodock_spi *s = dev_get_priv(dev);
    s->base = dev_read_addr_index_ptr(dev, 0); s->gpio = dev_read_addr_index_ptr(dev, 1);
    if (!s->base || !s->gpio) return -EINVAL;
    writel(1, s->gpio + 0x30); writel(readl(s->gpio + 0x28) | 1, s->gpio + 0x28);
    writel(7, s->base + 0x30);
    if (wait_bits(s, 0x30, 7, false)) return -ETIMEDOUT;
    writel(0, s->base + 0x38); writel(7U << 8, s->base + 0x10);
    return speed(dev, 400000);
}
static const struct dm_spi_ops ops = { .claim_bus = claim, .release_bus = release,
    .xfer = xfer, .set_speed = speed, .set_mode = mode };
static const struct udevice_id ids[] = {{ .compatible = "mjx,prodock-atcspi200" }, {}};
U_BOOT_DRIVER(prodock_spi) = { .name = "prodock_spi", .id = UCLASS_SPI,
    .of_match = ids, .probe = probe, .ops = &ops, .priv_auto = sizeof(struct prodock_spi) };

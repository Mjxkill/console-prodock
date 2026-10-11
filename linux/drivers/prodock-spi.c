// SPDX-License-Identifier: GPL-2.0-or-later
/* Pro Dock C37 ATCSPI200 + GPIO0 CS. Protocol belongs to upstream mmc_spi. */
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/property.h>
#include <linux/spi/spi.h>
#include <linux/unaligned.h>
struct prodock_spi { void __iomem *base, *gpio; u32 hz; };
#define S_CTRL 0x30
#define S_STATUS 0x34
static int idle(struct prodock_spi *s)
{
    u32 status;
    return readl_poll_timeout(s->base + S_STATUS, status, !(status & 1), 1, 100000);
}
static int reset_fifos(struct prodock_spi *s, u32 bits)
{
    u32 state;
    writel(bits, s->base + S_CTRL);
    return readl_poll_timeout(s->base + S_CTRL, state, !(state & bits), 1, 20000);
}
static void prodock_cs(struct spi_device *spi, bool inactive)
{
    struct prodock_spi *s = spi_controller_get_devdata(spi->controller);
    writel(1, s->gpio + (inactive ? 0x30 : 0x2c));
}
static void prodock_error(struct spi_controller *ctlr, struct spi_message *msg)
{
    struct prodock_spi *s = spi_controller_get_devdata(ctlr);
    writel(1, s->gpio + 0x30);
    reset_fifos(s, 7);
}
static int exchange(struct prodock_spi *s, const u8 *tx, u8 *rx, unsigned n)
{
    unsigned step = n >= 16 ? 4 : 1, sent = 0, got = 0;
    bool started = false;
    ktime_t until = ktime_add_ms(ktime_get(), 1000);
    int ret = idle(s);
    if (ret) return ret;
    ret = reset_fifos(s, 6);
    if (ret) return ret;
    writel((7 << 8) | (step == 4 ? BIT(7) : 0), s->base + 0x10);
    /* Full duplex even for RX-only: MOSI MUST be 0xff, never hardware zero. */
    writel(((n - 1) << 12) | (n - 1), s->base + 0x20);
    while (sent < n || got < n) {
        u32 status = readl(s->base + S_STATUS), word = ~0U;
        if (sent < n && !(status & BIT(23))) {
            if (tx) word = step == 4 ? get_unaligned_le32(tx + sent) : tx[sent];
            writel(word, s->base + 0x2c);
            sent += step;
        } else if (!started) {
            writel(0, s->base + 0x24); started = true;
        }
        if (sent == n && !started) { writel(0, s->base + 0x24); started = true; }
        if (started && got < n && !(status & BIT(14))) {
            word = readl(s->base + 0x2c);
            if (rx) {
                if (step == 4) put_unaligned_le32(word, rx + got);
                else rx[got] = word;
            }
            got += step;
        }
        if (ktime_after(ktime_get(), until)) return -ETIMEDOUT;
        cpu_relax();
    }
    return idle(s);
}
static int prodock_transfer(struct spi_controller *ctlr, struct spi_device *spi,
                            struct spi_transfer *xfer)
{
    struct prodock_spi *s = spi_controller_get_devdata(ctlr);
    const u8 *tx = xfer->tx_buf;
    u8 *rx = xfer->rx_buf;
    unsigned offset = 0, divider;
    int ret;
    if (!xfer->speed_hz || (xfer->bits_per_word && xfer->bits_per_word != 8)) return -EINVAL;
    divider = DIV_ROUND_UP_ULL(s->hz, 2ULL * xfer->speed_hz);
    if (!divider || divider > 255) return -ERANGE;
    ret = idle(s);
    if (ret) return ret;
    writel((readl(s->base + 0x40) & ~255U) | (divider - 1), s->base + 0x40);
    xfer->effective_speed_hz = s->hz / (2 * divider);
    while (offset < xfer->len) {
        unsigned n = min(512U, xfer->len - offset);
        if (n >= 16) n &= ~3U;
        ret = exchange(s, tx ? tx + offset : NULL, rx ? rx + offset : NULL, n);
        if (ret) return ret;
        offset += n;
        cond_resched();
    }
    return 0;
}
static int prodock_spi_probe(struct platform_device *pdev)
{
    struct spi_controller *ctlr = devm_spi_alloc_host(&pdev->dev, sizeof(struct prodock_spi));
    struct prodock_spi *s;
    int ret;
    if (!ctlr) return -ENOMEM;
    s = spi_controller_get_devdata(ctlr);
    s->base = devm_platform_ioremap_resource(pdev, 0);
    if (IS_ERR(s->base)) return PTR_ERR(s->base);
    s->gpio = devm_platform_ioremap_resource(pdev, 1);
    if (IS_ERR(s->gpio)) return PTR_ERR(s->gpio);
    if (device_property_read_u32(&pdev->dev, "clock-frequency", &s->hz) || s->hz != 80000000)
        return -EINVAL;
    writel(1, s->gpio + 0x30);
    writel(readl(s->gpio + 0x28) | 1, s->gpio + 0x28);
    ret = reset_fifos(s, 7);
    if (ret) return ret;
    writel(0, s->base + 0x38);
    writel(7 << 8, s->base + 0x10);
    ctlr->num_chipselect = 1;
    ctlr->dev.of_node = pdev->dev.of_node;
    ctlr->mode_bits = SPI_CS_HIGH;
    ctlr->bits_per_word_mask = SPI_BPW_MASK(8);
    ctlr->min_speed_hz = DIV_ROUND_UP(s->hz, 510);
    ctlr->max_speed_hz = 20000000;
    ctlr->set_cs = prodock_cs;
    ctlr->transfer_one = prodock_transfer;
    ctlr->handle_err = prodock_error;
    return devm_spi_register_controller(&pdev->dev, ctlr);
}
static const struct of_device_id prodock_spi_match[] = {
    { .compatible = "mjx,prodock-atcspi200" }, { }
};
static struct platform_driver prodock_spi_driver = {
    .probe = prodock_spi_probe,
    .driver = { .name = "prodock-spi", .of_match_table = prodock_spi_match,
                .suppress_bind_attrs = true },
};
builtin_platform_driver(prodock_spi_driver);
MODULE_LICENSE("GPL");

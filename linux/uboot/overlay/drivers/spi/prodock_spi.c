// SPDX-License-Identifier: GPL-2.0-or-later
/* U-Boot adapter. The shared engine owns SPI; this adapter owns GPIO0 CS.
 * SD initialization clocks belong to mmc_spi's CMD0 path, not claim_bus.
 */
#include <dm.h>
#include <spi.h>
#include <asm/io.h>
#include "prodock-spi-pio.h"

struct prodock_spi {
    struct atcspi200 engine;
    void __iomem *gpio;
};
enum { GPIO_DIRECTION = 0x28, GPIO_CLEAR = 0x2c, GPIO_SET = 0x30 };

static int release(struct udevice *dev)
{
    struct prodock_spi *s = dev_get_priv(dev->parent);

    writel(1, s->gpio + GPIO_SET);
    return 0;
}

static int recover_error(struct prodock_spi *s, int error)
{
    writel(1, s->gpio + GPIO_SET);
    /* The engine remains !ready if recovery fails. Preserve the first error. */
    atcspi200_recover(&s->engine);
    return error;
}

static int speed(struct udevice *bus, uint hz)
{
    struct prodock_spi *s = dev_get_priv(bus);
    int ret;

    if (hz > 20000000)
        hz = 20000000;
    ret = atcspi200_set_speed(&s->engine, hz);
    if (ret && !s->engine.ready)
        return recover_error(s, ret);
    return ret;
}

static int mode(struct udevice *bus, uint value)
{
    return value == SPI_MODE_0 ? 0 : -EINVAL;
}

static int claim(struct udevice *dev)
{
    struct prodock_spi *s = dev_get_priv(dev->parent);

    if (spi_chip_select(dev))
        return -EINVAL;
    if (!s->engine.ready)
        return -EIO;
    return release(dev);
}

static int xfer(struct udevice *dev, unsigned bits, const void *out, void *in,
                unsigned long flags)
{
    struct prodock_spi *s = dev_get_priv(dev->parent);
    int ret;

    if (bits & 7) {
        release(dev);
        return -EINVAL;
    }
    if (flags & SPI_XFER_BEGIN)
        writel(1, s->gpio + GPIO_CLEAR);
    ret = SPI_Master_send_receive(&s->engine, out, in, bits / 8);
    if (ret)
        return recover_error(s, ret);
    if (flags & SPI_XFER_END) {
        release(dev);
        /* Eight clocks with CS high let an SD card release its MISO output. */
        ret = SPI_Master_send_receive(&s->engine, NULL, NULL, 1);
        if (ret)
            return recover_error(s, ret);
    }
    return 0;
}

static int probe(struct udevice *dev)
{
    struct prodock_spi *s = dev_get_priv(dev);
    void *base = dev_read_addr_index_ptr(dev, 0);

    s->gpio = dev_read_addr_index_ptr(dev, 1);
    if (!base || !s->gpio)
        return -EINVAL;
    writel(1, s->gpio + GPIO_SET);
    writel(readl(s->gpio + GPIO_DIRECTION) | 1, s->gpio + GPIO_DIRECTION);
    return atcspi200_init(&s->engine, base, 80000000, 400000);
}

static const struct dm_spi_ops ops = {
    .claim_bus = claim, .release_bus = release, .xfer = xfer,
    .set_speed = speed, .set_mode = mode
};
static const struct udevice_id ids[] = {
    { .compatible = "mjx,prodock-atcspi200" }, { }
};
U_BOOT_DRIVER(prodock_spi) = {
    .name = "prodock_spi", .id = UCLASS_SPI, .of_match = ids,
    .probe = probe, .ops = &ops, .priv_auto = sizeof(struct prodock_spi)
};

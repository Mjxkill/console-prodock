// SPDX-License-Identifier: GPL-2.0-or-later
/* Linux SPI adapter for the shared AE350 engine. SD protocol belongs to mmc_spi.
 * GPIO0 holds CS across the message; the engine never changes chip selection.
 */
#include <linux/io.h>
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/property.h>
#include <linux/spi/spi.h>
#include "prodock-spi-pio.h"

struct prodock_spi {
    struct atcspi200 engine;
    void __iomem *gpio;
    unsigned int configured_hz;
    int setup_error;
};

enum { GPIO_DIRECTION = 0x28, GPIO_CLEAR = 0x2c, GPIO_SET = 0x30 };

static void prodock_cs(struct spi_device *spi, bool inactive)
{
    struct prodock_spi *s = spi_controller_get_devdata(spi->controller);

    /* SPI core has already converted CS polarity to the physical pin level. */
    writel(1, s->gpio + (inactive ? GPIO_SET : GPIO_CLEAR));
}

static void prodock_error(struct spi_controller *ctlr, struct spi_message *msg)
{
    struct prodock_spi *s = spi_controller_get_devdata(ctlr);
    int ret;

    writel(1, s->gpio + GPIO_SET);
    ret = atcspi200_recover(&s->engine);
    if (ret)
        dev_err(&ctlr->dev, "SPI recovery failed: %d\n", ret);
    /* Preserve msg->status: recovery must never turn a failed message into OK. */
}

static int prodock_setup(struct spi_device *spi)
{
    struct prodock_spi *s = spi_controller_get_devdata(spi->controller);

    /* mmc_spi sets the identification/operating clock through set_ios/setup.
     * It also calls setup just to release CS: keep that path free of MMIO.
     * The SPI core holds io_mutex, excluding an active transfer here.
     */
    if (s->configured_hz == spi->max_speed_hz && !s->setup_error)
        return 0;
    s->setup_error = atcspi200_set_speed(&s->engine, spi->max_speed_hz);
    if (!s->setup_error)
        s->configured_hz = spi->max_speed_hz;
    return s->setup_error;
}

static int prodock_transfer(struct spi_controller *ctlr, struct spi_device *spi,
                            struct spi_transfer *xfer)
{
    struct prodock_spi *s = spi_controller_get_devdata(ctlr);

    if (xfer->bits_per_word && xfer->bits_per_word != 8)
        return -EINVAL;
    if (s->setup_error)
        return s->setup_error;
    /* Dedicated SD bus: the setup clock remains fixed throughout exchanges.
     * Reused mmc_spi transfers can retain old speed metadata. They must not
     * restore the identification divider after the card is initialized.
     * Per-transfer clock overrides are not supported by this adapter.
     */
    xfer->effective_speed_hz = s->engine.actual_hz;
    return SPI_Master_send_receive(&s->engine, xfer->tx_buf, xfer->rx_buf,
                                   xfer->len);
}

static int prodock_spi_probe(struct platform_device *pdev)
{
    struct spi_controller *ctlr;
    struct prodock_spi *s;
    void __iomem *base;
    u32 clock_hz;
    int ret;

    ctlr = devm_spi_alloc_host(&pdev->dev, sizeof(*s));
    if (!ctlr)
        return -ENOMEM;
    s = spi_controller_get_devdata(ctlr);
    base = devm_platform_ioremap_resource(pdev, 0);
    if (IS_ERR(base))
        return PTR_ERR(base);
    s->gpio = devm_platform_ioremap_resource(pdev, 1);
    if (IS_ERR(s->gpio))
        return PTR_ERR(s->gpio);
    ret = device_property_read_u32(&pdev->dev, "clock-frequency", &clock_hz);
    if (ret || clock_hz != 80000000)
        return -EINVAL;

    writel(1, s->gpio + GPIO_SET);
    writel(readl(s->gpio + GPIO_DIRECTION) | 1, s->gpio + GPIO_DIRECTION);
    ret = atcspi200_init(&s->engine, (void __force *)base, clock_hz, 400000);
    if (ret)
        return ret;
    s->configured_hz = 400000;

    ctlr->num_chipselect = 1;
    ctlr->dev.of_node = pdev->dev.of_node;
    ctlr->mode_bits = SPI_CS_HIGH;
    ctlr->bits_per_word_mask = SPI_BPW_MASK(8);
    ctlr->min_speed_hz = DIV_ROUND_UP(clock_hz, 510);
    ctlr->max_speed_hz = 20000000;
    ctlr->setup = prodock_setup;
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

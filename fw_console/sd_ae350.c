// SD transport adapter: AE350 native SPI at 0xF0F00000, GPIO0 chip select.
// The common engine owns configuration/FIFOs. sd.c owns SD protocol/retries.
#include "ae350.h"
#include "sd.h"
#include "../linux/drivers/prodock-spi-pio.h"
#include <errno.h>
#include <stddef.h>

enum { APB_HZ = 80000000U, SD_SELECT = 1U, SD_DETECT = 2U };
static struct atcspi200 spi;
static int configured;
static int setup_error;

static int configure(unsigned hz)
{
    int ret;

    AE350_GPIO->DOUTSET = SD_SELECT;
    AE350_GPIO->CHANNELDIR |= SD_SELECT;
    ret = atcspi200_init(&spi, (void *)AE350_SPI, APB_HZ, hz);
    configured = !ret;
    return ret;
}

void sd_port_speed(unsigned hz)
{
    setup_error = 0;
    if (!configured) {
        setup_error = configure(hz);
        return;
    }
    if (!spi.ready) {
        AE350_GPIO->DOUTSET = SD_SELECT;
        setup_error = atcspi200_recover(&spi);
        if (setup_error)
            return;
    }
    setup_error = atcspi200_set_speed(&spi, hz);
}

void sd_port_select(int selected)
{
    /* Deselection is unconditional, including after setup/transport failure. */
    if (!selected)
        AE350_GPIO->DOUTSET = SD_SELECT;
    if (setup_error)
        return;
    if (!configured) {
        setup_error = configure(400000);
        if (setup_error)
            return;
    }
    if (selected)
        AE350_GPIO->DOUTCLEAR = SD_SELECT;
}

int sd_port_exchange(const uint8_t *tx, uint8_t *rx, unsigned count)
{
    int ret;

    if (setup_error)
        return setup_error;
    ret = SPI_Master_send_receive(&spi, tx, rx, count);
    if (ret && configured) {
        AE350_GPIO->DOUTSET = SD_SELECT;
        setup_error = atcspi200_recover(&spi);
        // Preserve transfer error even when recovery succeeds. sd.c decides retry.
    }
    return ret;
}

unsigned sd_port_ms(void)
{
    return atcspi200_milliseconds();
}

int sd_port_present(void)
{
    return (AE350_GPIO->DATAIN & SD_DETECT) == 0;
}

unsigned sd_ae350_detect_raw(void)
{
    return (AE350_GPIO->DATAIN & SD_DETECT) ? 1U : 0U;
}

unsigned sd_ae350_spi_id(void)
{
    return AE350_SPI->IDREV;
}

// SPDX-License-Identifier: GPL-2.0-or-later
/* AE350 ATCSPI200: one implementation linked by Linux, U-Boot and the ROM.
 * Registers: Gowin MUG1029-1.3E, chapter 10. No SD protocol here.
 * Four FIFO entries in flight: one RX byte proves a TX entry was consumed,
 * so its replacement needs no TXFULL polling.
 */
#include "prodock-spi-pio.h"

#if defined(PRODOCK_SPI_TEST)
#include <errno.h>
#elif defined(PRODOCK_SPI_UBOOT)
#include <time.h>
#include <asm/io.h>
#include <linux/errno.h>
#elif defined(__KERNEL__)
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/ktime.h>
#else
#include <errno.h>
#endif

enum {
    REG_FORMAT = 0x10, REG_LENGTH = 0x20, REG_COMMAND = 0x24,
    REG_DATA = 0x2c, REG_CONTROL = 0x30, REG_STATUS = 0x34,
    REG_INTERRUPT_ENABLE = 0x38, REG_TIMING = 0x40, REG_CONFIG = 0x7c,
    STATUS_BUSY = 1U, STATUS_RX_EMPTY = 1U << 14,
    STATUS_TX_EMPTY = 1U << 22, RESET_ALL = 7U,
    FORMAT_8BIT_MODE0 = 7U << 8, MAX_CHUNK = 512U,
    WAIT_CONTROL_MS = 100U, WAIT_RECEIVE_MS = 1000U
};

/* Only platform mechanics differ. Native MMIO, no indirect byte-loop calls.
 * Bare-metal fences order device accesses on the AE350 RISC-V CPU.
 */
static inline __attribute__((always_inline))
unsigned int read_register(struct atcspi200 *spi, unsigned int offset)
{
#if defined(PRODOCK_SPI_TEST)
    return atcspi200_test_read(spi->base, offset);
#elif defined(PRODOCK_SPI_UBOOT) || defined(__KERNEL__)
    return readl((void __iomem *)((unsigned char *)spi->base + offset));
#else
    unsigned int value;
    __asm__ volatile("fence iorw, iorw" ::: "memory");
    value = *(volatile unsigned int *)((unsigned char *)spi->base + offset);
    __asm__ volatile("fence iorw, iorw" ::: "memory");
    return value;
#endif
}

static inline __attribute__((always_inline))
void write_register(struct atcspi200 *spi, unsigned int offset, unsigned int value)
{
#if defined(PRODOCK_SPI_TEST)
    atcspi200_test_write(spi->base, offset, value);
#elif defined(PRODOCK_SPI_UBOOT) || defined(__KERNEL__)
    writel(value, (void __iomem *)((unsigned char *)spi->base + offset));
#else
    __asm__ volatile("fence iorw, iorw" ::: "memory");
    *(volatile unsigned int *)((unsigned char *)spi->base + offset) = value;
    __asm__ volatile("fence iorw, iorw" ::: "memory");
#endif
}

unsigned int atcspi200_milliseconds(void)
{
#if defined(PRODOCK_SPI_TEST)
    return atcspi200_test_milliseconds();
#elif defined(PRODOCK_SPI_UBOOT)
    return (unsigned int)get_timer(0);
#elif defined(__KERNEL__)
    return (unsigned int)ktime_to_ms(ktime_get());
#else
    unsigned int high, low, again;
    do {
        __asm__ volatile("rdcycleh %0" : "=r"(high));
        __asm__ volatile("rdcycle %0" : "=r"(low));
        __asm__ volatile("rdcycleh %0" : "=r"(again));
    } while (high != again);
    /* Both board profiles run the AE350 core at 800 MHz. */
    return (unsigned int)((((unsigned long long)high << 32) | low) / 800000ULL);
#endif
}

static int wait_clear(struct atcspi200 *spi, unsigned int reg, unsigned int mask)
{
    unsigned int start;

    if (!(read_register(spi, reg) & mask))
        return 0;
    start = atcspi200_milliseconds();
    while (read_register(spi, reg) & mask) {
        if (atcspi200_milliseconds() - start >= WAIT_CONTROL_MS)
            return -ETIMEDOUT;
    }
    return 0;
}

static int clock_divider(unsigned int clock_hz, unsigned int requested_hz,
                         unsigned int *divider)
{
    unsigned int denominator;

    if (!requested_hz || requested_hz > clock_hz / 2)
        return -EINVAL;
    denominator = 2 * requested_hz; /* Cannot overflow after the range check. */
    *divider = clock_hz / denominator;
    if (clock_hz % denominator)
        ++*divider;
    /* Register FF bypasses division: it is NOT divide by 512. */
    if (*divider > 255)
        return -ERANGE;
    return 0;
}

int atcspi200_recover(struct atcspi200 *spi)
{
    unsigned int empty = STATUS_RX_EMPTY | STATUS_TX_EMPTY;
    int ret;

    spi->ready = 0;
    if (!spi->clock_hz)
        return -EINVAL; /* Initialization has not validated this controller. */
    write_register(spi, REG_CONTROL, RESET_ALL);
    ret = wait_clear(spi, REG_CONTROL, RESET_ALL);
    if (ret)
        return ret;
    ret = wait_clear(spi, REG_STATUS, STATUS_BUSY);
    if (ret)
        return ret;
    /* Do not assume which configuration registers software reset preserves. */
    write_register(spi, REG_INTERRUPT_ENABLE, 0);
    write_register(spi, REG_FORMAT, FORMAT_8BIT_MODE0);
    write_register(spi, REG_TIMING, spi->timing);
    if ((read_register(spi, REG_STATUS) & empty) != empty)
        return -EIO;
    spi->ready = 1;
    return 0;
}

int atcspi200_init(struct atcspi200 *spi, void *base,
                  unsigned int clock_hz, unsigned int requested_hz)
{
    unsigned int config, divider;
    int ret;

    *spi = (struct atcspi200){0};
    if (!base || !clock_hz)
        return -EINVAL;
    ret = clock_divider(clock_hz, requested_hz, &divider);
    if (ret)
        return ret;
    spi->base = base;
    /* Check four-entry capacity once. Codes 1..6 = 4..128 words;
     * code 0 = two words, codes 7..15 reserved.
     */
    config = read_register(spi, REG_CONFIG);
    if ((config & 15) < 1 || (config & 15) > 6 ||
        ((config >> 4) & 15) < 1 || ((config >> 4) & 15) > 6)
        return -ENODEV;
    spi->clock_hz = clock_hz;
    spi->actual_hz = clock_hz / (2 * divider);
    spi->timing = (read_register(spi, REG_TIMING) & ~255U) | (divider - 1);
    return atcspi200_recover(spi);
}

int atcspi200_set_speed(struct atcspi200 *spi, unsigned int requested_hz)
{
    unsigned int divider, timing;
    int ret;

    if (!spi->ready)
        return -EIO;
    ret = clock_divider(spi->clock_hz, requested_hz, &divider);
    if (ret)
        return ret;
    timing = (spi->timing & ~255U) | (divider - 1);
    if (timing == spi->timing)
        return 0; /* Identical requested divider: no MMIO. */
    ret = wait_clear(spi, REG_STATUS, STATUS_BUSY);
    if (ret) {
        spi->ready = 0;
        return ret;
    }
    write_register(spi, REG_TIMING, timing);
    spi->timing = timing;
    spi->actual_hz = spi->clock_hz / (2 * divider);
    return 0;
}

static int exchange_chunk(struct atcspi200 *spi, const unsigned char *tx,
                          unsigned char *rx, unsigned int count)
{
    unsigned int sent = 0, received = 0;
    unsigned int prime = count < 4 ? count : 4;
    unsigned int start = atcspi200_milliseconds();

    write_register(spi, REG_LENGTH, ((count - 1) << 12) | (count - 1));
    while (sent < prime) {
        write_register(spi, REG_DATA, tx ? tx[sent] : 0xff);
        ++sent;
    }
    write_register(spi, REG_COMMAND, 0);

    while (received < count) {
        unsigned char value;

        while (read_register(spi, REG_STATUS) & STATUS_RX_EMPTY) {
            if (atcspi200_milliseconds() - start >= WAIT_RECEIVE_MS)
                return -ETIMEDOUT;
        }
        value = (unsigned char)read_register(spi, REG_DATA);
        if (rx)
            rx[received] = value;
        ++received;
        if (sent < count) {
            write_register(spi, REG_DATA, tx ? tx[sent] : 0xff);
            ++sent;
        }
    }
    /* Final RX and controller completion differ. Finish before CS/rate changes. */
    return wait_clear(spi, REG_STATUS, STATUS_BUSY);
}

int SPI_Master_send_receive(struct atcspi200 *spi, const unsigned char *tx,
                            unsigned char *rx, unsigned int count)
{
    if (!spi->ready)
        return -EIO;
    while (count) {
        unsigned int part = count < MAX_CHUNK ? count : MAX_CHUNK;
        int ret = exchange_chunk(spi, tx, rx, part);

        if (ret) {
            spi->ready = 0; /* No implicit reset/replay inside an active CS. */
            return ret;
        }
        if (tx)
            tx += part;
        if (rx)
            rx += part;
        count -= part;
    }
    return 0;
}

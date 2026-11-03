/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PRODOCK_SPI_PIO_H
#define PRODOCK_SPI_PIO_H

/* One owner at a time. GPIO chip selection belongs to the platform adapter.
 * Eight-bit, mode 0, full duplex. No implementation in this header.
 */
struct atcspi200 {
    void *base;
    unsigned int clock_hz;
    unsigned int actual_hz;
    unsigned int timing;
    int ready;
};

/* Configure once with CS inactive. Check capacity, reset, set format/clock. */
int atcspi200_init(struct atcspi200 *spi, void *base,
                  unsigned int clock_hz, unsigned int requested_hz);
int atcspi200_set_speed(struct atcspi200 *spi, unsigned int requested_hz);

/* Requires init to have validated clock and FIFO capacity; otherwise EINVAL.
 * Deassert CS before recovery. Restore configuration; never replay data.
 * Failure leaves the controller unusable until recovery succeeds.
 */
int atcspi200_recover(struct atcspi200 *spi);

/* Synchronous exchange, chunks <=512 bytes, CS untouched between chunks.
 * TX NULL sends FF, RX NULL still drains RX. count=0 performs no MMIO.
 * Exact in-place TX/RX supported; other overlapping buffers unsupported.
 * Return 0 on full success, negative errno otherwise. Partial RX is invalid
 * on failure; recovery is mandatory before another exchange.
 * Success guarantees all RX consumed and controller no longer busy.
 */
int SPI_Master_send_receive(struct atcspi200 *spi, const unsigned char *tx,
                            unsigned char *rx, unsigned int count);

/* Monotonic milliseconds modulo 2^32. Timeouts use unsigned subtraction. */
unsigned int atcspi200_milliseconds(void);

#ifdef PRODOCK_SPI_TEST
/* Host-model link seam, absent from production binaries. */
unsigned int atcspi200_test_read(void *base, unsigned int offset);
void atcspi200_test_write(void *base, unsigned int offset, unsigned int value);
unsigned int atcspi200_test_milliseconds(void);
#endif
#endif

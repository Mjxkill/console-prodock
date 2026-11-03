/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Host-side register model for ATCSPI200. Declarations and types only. */
#ifndef SPI_REGISTER_MODEL_H
#define SPI_REGISTER_MODEL_H

#include <stdint.h>

struct spi_model {
    unsigned capacity;
    unsigned latency;
    unsigned first_delay;
    int stopped;
    int force_full;
    int busy_hold;
    int reset_blocked;
    int bad_empty;

    unsigned char tx_fifo[128];
    unsigned char rx_fifo[128];
    unsigned tx_head;
    unsigned tx_tail;
    unsigned tx_count;
    unsigned rx_head;
    unsigned rx_tail;
    unsigned rx_count;
    unsigned rx_capacity;

    int active;
    uint64_t due;
    unsigned char active_tx;
    unsigned active_index;
    unsigned global_index;
    unsigned completed;
    unsigned total_shifted;

    int started;
    unsigned starts;
    unsigned prefill;
    unsigned programmed;
    unsigned writes;
    unsigned reads;
    unsigned credit;
    unsigned violations;

    unsigned format;
    unsigned count;
    unsigned timing;
    unsigned irq_enable;
    unsigned config;
    int reset_pending;
    unsigned reset_start;
    unsigned reset_writes;
    unsigned resets_completed;
    unsigned format_writes;
    unsigned timing_writes;
    unsigned irq_writes;
    unsigned access_count;

    uint64_t time;
    unsigned ms_offset, timer_reads;
    unsigned aggregate_writes, aggregate_reads;
    unsigned preparing;
    unsigned steps;
    unsigned polls_before_rx;

    char events[65536];
    unsigned events_n;

    unsigned char serial[8192];
};

void spi_model_init(struct spi_model *model, unsigned capacity, unsigned latency);
void spi_model_set_active(struct spi_model *model);
unsigned spi_model_read(struct spi_model *model, unsigned offset);
void spi_model_write(struct spi_model *model, unsigned offset, unsigned value);
unsigned spi_model_ms(void);

#endif

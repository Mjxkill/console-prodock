/* SPDX-License-Identifier: GPL-2.0-or-later */
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "prodock-spi-pio.h"
#include "spi_register_model.h"

#define STATUS_BUSY 1U
#define STATUS_RX_EMPTY (1U << 14)
#define STATUS_TX_EMPTY (1U << 22)
#define RESET_ALL 7U
#define REG_FORMAT 0x10
#define REG_COUNT 0x20
#define REG_CMD 0x24
#define REG_DATA 0x2c
#define REG_CTRL 0x30
#define REG_STATUS 0x34
#define REG_IRQ 0x38
#define REG_TIMING 0x40
#define REG_CONFIG 0x7c

static struct spi_model *host_active_model;

static void model_event(struct spi_model *m, char value)
{
    if (m->events_n >= sizeof(m->events) - 1) {
        fprintf(stderr, "trace overflow\n");
        abort();
    }
    m->events[m->events_n++] = value;
}

static void reset_transfer_state(struct spi_model *m)
{
    m->active = 0;
    m->started = 0;
    m->tx_count = 0;
    m->rx_count = 0;
    m->tx_head = m->tx_tail = 0;
    m->rx_head = m->rx_tail = 0;
    m->active_tx = 0;
    m->active_index = 0;
    m->global_index = 0;
    m->completed = 0;
    m->total_shifted = 0;
    m->credit = 0;
    m->prefill = 0;
    m->programmed = 0;
    m->writes = 0;
    m->reads = 0;
}

static unsigned capacity_code(unsigned capacity)
{
    unsigned code = 1;
    unsigned value = 4;
    while (value < capacity && code < 6) {
        value <<= 1;
        ++code;
    }
    return code;
}

void spi_model_init(struct spi_model *m, unsigned capacity, unsigned latency)
{
    memset(m, 0, sizeof(*m));
    if (capacity == 0 || capacity > 128)
        capacity = 8;
    if (latency == 0)
        latency = 1;
    m->capacity = capacity;
    m->rx_capacity = capacity;
    m->latency = latency;
    m->config = capacity_code(capacity) | (capacity_code(capacity) << 4);
    m->time = 0;
    m->steps = 0;
}

void spi_model_set_active(struct spi_model *m)
{
    host_active_model = m;
}

static unsigned char answer_byte(unsigned index, unsigned char tx)
{
    unsigned value = tx ^ 0xa7U ^ (index * 13U) ^ ((index >> 8) * 17U);
    return (unsigned char)value;
}

static void tx_enqueue(struct spi_model *m, unsigned char value)
{
    if (m->tx_count >= m->capacity) {
        fprintf(stderr, "TX FIFO overflow\n");
        abort();
    }
    m->tx_fifo[m->tx_tail % 128] = value;
    ++m->tx_tail;
    ++m->tx_count;
}

static unsigned char tx_dequeue(struct spi_model *m)
{
    unsigned char value = m->tx_fifo[m->tx_head % 128];
    ++m->tx_head;
    --m->tx_count;
    return value;
}

static void rx_enqueue(struct spi_model *m, unsigned char value)
{
    if (m->rx_count >= m->rx_capacity) {
        fprintf(stderr, "RX FIFO overflow\n");
        abort();
    }
    m->rx_fifo[m->rx_tail % 128] = value;
    ++m->rx_tail;
    ++m->rx_count;
}

static unsigned char rx_dequeue(struct spi_model *m)
{
    unsigned char value = m->rx_fifo[m->rx_head % 128];
    ++m->rx_head;
    --m->rx_count;
    return value;
}

static void model_tick(struct spi_model *m)
{
    if (m->steps >= 1000000U) {
        fprintf(stderr, "model step bound\n");
        abort();
    }
    ++m->steps;
    ++m->time;

    if (!m->started || m->stopped)
        return;

    if (m->active && m->time >= m->due) {
        rx_enqueue(m, answer_byte(m->active_index, m->active_tx));
        ++m->completed;
        m->active = 0;
    }

    if (!m->active && m->tx_count > 0 && m->rx_count < m->rx_capacity) {
        m->active_tx = tx_dequeue(m);
        m->active_index = m->global_index++;
        if (m->active_index >= sizeof(m->serial)) abort();
        m->serial[m->active_index] = m->active_tx;
        ++m->total_shifted;
        m->active = 1;
        m->due = m->time + m->latency;
        if (m->global_index == 1)
            m->due += m->first_delay;
    }
}

static unsigned status_word(struct spi_model *m)
{
    if (m->started && !m->active && m->tx_count == 0 && m->rx_count == 0 && !m->busy_hold) {
        m->started = 0;
        m->credit = 0;
    }
    int busy = 0;
    if (m->started &&
        (m->active || m->tx_count > 0 || m->rx_count > 0 || m->busy_hold))
        busy = 1;
    if (m->reset_pending)
        busy = 1;
    if (m->started && m->reads == 0)
        ++m->polls_before_rx;
    return (m->rx_count == 0 ? STATUS_RX_EMPTY : 0U) |
           (m->tx_count == 0 ? STATUS_TX_EMPTY : 0U) |
           (busy ? STATUS_BUSY : 0U);
}

static void perform_reset(struct spi_model *m)
{
    reset_transfer_state(m);
    /* Deliberately erase settings: recovery must restore both registers. */
    m->format = 0;
    m->timing = 0;
    m->irq_enable = ~0U;
    m->preparing = 0;
    if (m->bad_empty)
        m->tx_count = 1;
    m->reset_pending = 0;
    ++m->resets_completed;
    model_event(m, 'X');
}

static int should_tick(unsigned offset)
{
    return offset == REG_STATUS || offset == REG_CTRL || offset == REG_TIMING ||
           offset == REG_CONFIG || offset == REG_COUNT || offset == REG_FORMAT ||
           offset == REG_IRQ || offset == REG_CMD;
}

unsigned spi_model_read(struct spi_model *m, unsigned offset)
{
    ++m->access_count;
    if (should_tick(offset))
        model_tick(m);

    switch (offset) {
    case REG_FORMAT:
        return m->format;
    case REG_COUNT:
        return m->count;
    case REG_CMD:
        return 0;
    case REG_DATA:
        if (m->rx_count == 0) {
            fprintf(stderr, "DATA read while RX empty\n");
            abort();
        }
        {
            unsigned char value = rx_dequeue(m);
            ++m->reads;
            ++m->aggregate_reads;
            m->credit = 1;
            model_event(m, 'R');
            return value;
        }
    case REG_CTRL:
        if (m->reset_pending) {
            if (m->reset_blocked) {
                return RESET_ALL;
            }
            {
                perform_reset(m);
                return 0;
            }
            return RESET_ALL;
        }
        return 0;
    case REG_STATUS:
        model_event(m, 'S');
        if (m->preparing) {
            fprintf(stderr, "STATUS during prefill\n"); abort();
        }
        return status_word(m);
    case REG_IRQ:
        return m->irq_enable;
    case REG_TIMING:
        return m->timing;
    case REG_CONFIG:
        return m->config;
    default:
        return 0;
    }
}

void spi_model_write(struct spi_model *m, unsigned offset, unsigned value)
{
    ++m->access_count;
    switch (offset) {
    case REG_FORMAT:
        m->format = value;
        ++m->format_writes;
        model_event(m, 'F');
        break;
    case REG_COUNT:
        if (m->started || m->active || m->tx_count || m->rx_count) {
            fprintf(stderr, "COUNT while previous transaction active\n"); abort();
        }
        m->count = value;
        m->programmed = (value & 511U) + 1U;
        if (((value >> 12) & 511U) + 1U != m->programmed) abort();
        m->writes = m->reads = m->completed = m->total_shifted = 0;
        m->credit = 0;
        m->preparing = 1;
        model_event(m, 'N');
        break;
    case REG_CMD:
        if (value || !m->preparing || m->started || m->active || !m->tx_count || m->rx_count) {
            fprintf(stderr, "invalid CMD start\n"); abort();
        }
        m->started = 1;
        m->preparing = 0;
        ++m->starts;
        m->prefill = m->writes;
        model_event(m, 'C');
        break;
    case REG_DATA:
        if (m->started) {
            if (!m->credit || !m->events_n || m->events[m->events_n - 1] != 'R') {
                ++m->violations;
                fprintf(stderr, "TX WITHOUT RX\n");
                abort();
            }
            m->credit = 0;
        }
        if (m->force_full || m->tx_count >= m->capacity) {
            fprintf(stderr, "TX FIFO full\n");
            abort();
        }
        if (m->writes >= m->programmed) {
            fprintf(stderr, "DATA beyond programmed count\n"); abort();
        }
        tx_enqueue(m, (unsigned char)value);
        ++m->writes;
        ++m->aggregate_writes;
        model_event(m, 'W');
        break;
    case REG_CTRL:
        if (value & RESET_ALL) {
            ++m->reset_writes;
            m->reset_pending = 1;
            m->reset_start = m->time;
            model_event(m, 'Q');
        }
        break;
    case REG_IRQ:
        m->irq_enable = value;
        ++m->irq_writes;
        break;
    case REG_TIMING:
        m->timing = value;
        ++m->timing_writes;
        model_event(m, 'T');
        break;
    default:
        break;
    }
}

unsigned spi_model_ms(void)
{
    if (!host_active_model) abort();
    ++host_active_model->timer_reads;
    model_event(host_active_model, 'M');
    return host_active_model->ms_offset + (unsigned)(host_active_model->time / 8);
}

unsigned atcspi200_test_read(void *base, unsigned offset)
{
    return spi_model_read((struct spi_model *)base, offset);
}

void atcspi200_test_write(void *base, unsigned offset, unsigned value)
{
    spi_model_write((struct spi_model *)base, offset, value);
}

unsigned atcspi200_test_milliseconds(void)
{
    return spi_model_ms();
}

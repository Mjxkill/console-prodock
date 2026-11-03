#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#include "prodock-spi-pio.h"
#include "spi_register_model.h"

static struct atcspi200 spi;
static struct spi_model hw;

static void fail(const char *what)
{
    fprintf(stderr, "FAIL: %s\n", what);
    exit(1);
}

static void reset_hw(unsigned capacity, unsigned latency)
{
    memset(&hw, 0, sizeof(hw));
    spi_model_init(&hw, capacity, latency);
    spi_model_set_active(&hw);
    memset(&spi, 0, sizeof(spi));
}

static unsigned char answer_byte(unsigned index, unsigned char tx)
{
    return (unsigned char)(tx ^ 0xa7U ^ (index * 13U) ^ ((index >> 8) * 17U));
}

struct guarded {
    unsigned char *mapping;
    unsigned char *data;
    size_t page;
    unsigned n;
};

static struct guarded guard(unsigned n, int at_end)
{
    struct guarded g;
    memset(&g, 0, sizeof(g));
    if (n == 0) {
        return g;
    }
    g.page = (size_t)sysconf(_SC_PAGESIZE);
    if (g.page < n) {
        fail("page size too small");
    }
    g.mapping = mmap(NULL, g.page * 3, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (g.mapping == MAP_FAILED) {
        fail("mmap guard pages");
    }
    if (mprotect(g.mapping + g.page, g.page, PROT_READ | PROT_WRITE) != 0) {
        fail("mprotect");
    }
    g.data = g.mapping + g.page + (at_end ? g.page - n : 0);
    g.n = n;
    return g;
}

static void release_guard(struct guarded *g)
{
    if (g->mapping) {
        if (munmap(g->mapping, g->page * 3) != 0) {
            fail("munmap");
        }
        memset(g, 0, sizeof(*g));
    }
}

static unsigned char pattern(unsigned i)
{
    return (unsigned char)(i * 53 + 7 + (i >> 8) * 37);
}

static void check_trace(unsigned n)
{
    char data_events[20000];
    unsigned used = 0, index = 0;
    for (unsigned i = 0; i < hw.events_n; ++i)
        if (hw.events[i] == 'W' || hw.events[i] == 'R' || hw.events[i] == 'C') {
            if (used == sizeof(data_events)) fail("data trace capacity");
            data_events[used++] = hw.events[i];
        }
    while (n) {
        unsigned part = n > 512 ? 512 : n;
        unsigned prefill = part < 4 ? part : 4;
        for (unsigned k = 0; k < prefill; ++k)
            if (index >= used || data_events[index++] != 'W') fail("trace prefill writes");
        if (index >= used || data_events[index++] != 'C') fail("trace start follows prefill");
        for (unsigned got = 0; got < part; ++got) {
            if (index >= used || data_events[index++] != 'R') fail("trace RX first");
            if (got < part - prefill && (index >= used || data_events[index++] != 'W'))
                fail("trace refill per RX");
        }
        n -= part;
    }
    if (index != used) fail("extra data trace events");
}

static void success(unsigned n, unsigned capacity, unsigned latency,
                    unsigned mode, int end)
{
    reset_hw(capacity, latency);
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("init in success");
    }

    struct guarded tx = guard(n, end);
    struct guarded rx = guard(n, end);
    for (unsigned i = 0; i < n; ++i) {
        if (tx.data) {
            tx.data[i] = pattern(i);
        }
        if (rx.data) {
            rx.data[i] = 0;
        }
    }
    if (tx.data) {
        if (mprotect(tx.mapping + tx.page, tx.page, PROT_READ) != 0) {
            fail("TX read-only");
        }
    }

    const unsigned char *tx_ptr = (mode == 1 || mode == 3) ? NULL : tx.data;
    unsigned char *rx_ptr = (mode == 2 || mode == 3) ? NULL : rx.data;

    unsigned base_access = hw.access_count;
    unsigned resets = hw.reset_writes, formats = hw.format_writes;
    unsigned timing_writes = hw.timing_writes, irq_writes = hw.irq_writes;
    unsigned timing = hw.timing;
    hw.events_n = 0;
    int rc = SPI_Master_send_receive(&spi, tx_ptr, rx_ptr, n);
    if (rc != 0) {
        fprintf(stderr, "rc=%d n=%u mode=%u\\n", rc, n, mode);
        fail("successful transfer rc");
    }
    if (hw.violations != 0) {
        fail("TX-without-RX violation");
    }

    if (hw.reset_writes != resets || hw.format_writes != formats ||
        hw.timing_writes != timing_writes || hw.irq_writes != irq_writes || hw.timing != timing)
        fail("configuration write during transfer");
    unsigned last = n ? (n - 1) % 512 + 1 : 0;
    unsigned prefill = last < 4 ? last : 4;
    if (n > 0) {
        if (hw.prefill != prefill) {
            fprintf(stderr, "prefill %u expected %u\\n", hw.prefill, prefill);
            fail("prefill count");
        }
        if (hw.starts != (n + 511) / 512) {
            fail("start count");
        }
        if (prefill > capacity) {
            /* capacity must fit min(4,n) */
        }
        if (hw.aggregate_writes != n || hw.aggregate_reads != n || hw.global_index != n ||
            hw.completed != last) {
            fprintf(stderr, "w=%u r=%u shifted=%u completed=%u n=%u\\n",
                    hw.writes, hw.reads, hw.total_shifted, hw.completed, n);
            fail("byte counts");
        }
        if (hw.active != 0 || hw.tx_count != 0 || hw.rx_count != 0) {
            fail("FIFO drain");
        }
        if (prefill > capacity) {
            fail("capacity below prefill");
        }
        check_trace(n);
    } else {
        if (hw.starts != 0 || hw.writes != 0 || hw.reads != 0) {
            fail("zero transfer MMIO");
        }
        if (hw.access_count != base_access) {
            fail("zero transfer access count");
        }
    }

    if (tx.data) {
        for (unsigned i = 0; i < n; ++i) {
            if (tx.data[i] != pattern(i)) {
                fail("TX bytes changed");
            }
        }
    }
    for (unsigned i = 0; i < n; ++i)
        if (hw.serial[i] != (tx_ptr ? pattern(i) : 0xff)) fail("wire TX bytes");
    if (rx_ptr) {
        for (unsigned i = 0; i < n; ++i) {
            unsigned char sent = tx_ptr ? pattern(i) : 0xff;
            unsigned char expected = answer_byte(i, sent);
            if (rx.data[i] != expected) {
                fprintf(stderr, "rx[%u]=%u expected=%u\\n", i, rx.data[i], expected);
                fail("RX bytes exact");
            }
        }
    }

    release_guard(&tx);
    release_guard(&rx);
}

static void scenario_init(void)
{
    /* invalid base */
    struct atcspi200 s;
    memset(&s, 0, sizeof(s));
    reset_hw(8, 2);
    if (atcspi200_init(&s, NULL, 80000000, 20000000) != -EINVAL) {
        fail("null base init");
    }
    /* invalid clock */
    reset_hw(8, 2);
    if (atcspi200_init(&s, &hw, 0, 20000000) != -EINVAL) {
        fail("zero clock init");
    }
    /* invalid high request */
    reset_hw(8, 2);
    if (atcspi200_init(&s, &hw, 80000000, 41000000) != -EINVAL) {
        fail("high speed init");
    }
    /* invalid low request */
    reset_hw(8, 2);
    if (atcspi200_init(&s, &hw, 80000000, 1000) != -ERANGE) {
        fail("low speed init");
    }
    /* invalid CONFIG codes */
    reset_hw(8, 2);
    hw.config = 0;
    if (atcspi200_init(&s, &hw, 80000000, 20000000) != -ENODEV) {
        fail("config code init");
    }

    /* valid init */
    reset_hw(8, 2);
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("valid init");
    }
    if (hw.format != (7U << 8)) {
        fail("FORMAT value");
    }
    if (hw.irq_enable != 0) {
        fail("IRQ enable");
    }
    if ((spi.timing & 255U) != 1) {
        fail("divider");
    }
    if (hw.resets_completed < 1) {
        fail("reset not performed");
    }

    /* set_speed invalid and same divider */
    if (atcspi200_set_speed(&spi, 41000000) != -EINVAL) {
        fail("set_speed high");
    }
    if (atcspi200_set_speed(&spi, 0) != -EINVAL) {
        fail("set_speed zero");
    }
    if (atcspi200_set_speed(&spi, 1000) != -ERANGE) {
        fail("set_speed low");
    }
    unsigned accesses = hw.access_count;
    unsigned timing_writes = hw.timing_writes;
    if (atcspi200_set_speed(&spi, 20000000) != 0) {
        fail("set_speed same");
    }
    if (hw.access_count != accesses || hw.timing_writes != timing_writes) {
        fail("same divider MMIO");
    }
}

static void scenario_multiple(void)
{
    unsigned char tx[32];
    unsigned char rx[32];
    for (unsigned i = 0; i < 32; ++i) {
        tx[i] = pattern(i);
        rx[i] = 0;
    }

    reset_hw(8, 2);
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("init multiple");
    }

    unsigned reset_writes = hw.reset_writes;
    unsigned format_writes = hw.format_writes;
    unsigned timing_writes = hw.timing_writes;
    unsigned timing = spi.timing;

    for (int t = 0; t < 3; ++t) {
        int rc = SPI_Master_send_receive(&spi, tx, rx, 32);
        if (rc != 0) {
            fail("multiple transfer");
        }
    }

    if (hw.reset_writes != reset_writes || hw.format_writes != format_writes ||
        hw.timing_writes != timing_writes) {
        fail("configuration written during transfer");
    }
    if (spi.timing != timing) {
        fail("divider changed during transfer");
    }
    if (!spi.ready) {
        fail("not ready after multiple");
    }
}

static void scenario_zero(void)
{
    reset_hw(8, 2);
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("init zero");
    }
    unsigned accesses = hw.access_count, timer_reads = hw.timer_reads;
    if (SPI_Master_send_receive(&spi, NULL, NULL, 0) != 0) {
        fail("zero ready transfer");
    }
    if (hw.access_count != accesses || hw.timer_reads != timer_reads) {
        fail("zero MMIO/time");
    }

    /* not ready returns EIO before MMIO */
    spi.ready = 0;
    unsigned accesses2 = hw.access_count;
    if (SPI_Master_send_receive(&spi, NULL, NULL, 0) != -EIO) {
        fail("zero not ready");
    }
    if (hw.access_count != accesses2) {
        fail("zero not ready MMIO");
    }
}

static void scenario_timeout(void)
{
    reset_hw(8, 2);
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("init timeout");
    }
    hw.stopped = 1;
    unsigned char tx[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    unsigned char rx[8] = {0};
    if (SPI_Master_send_receive(&spi, tx, rx, 8) != -ETIMEDOUT) {
        fail("RX timeout rc");
    }
    if (spi.ready) {
        fail("ready after timeout");
    }
    if (hw.writes != 4 || hw.reads != 0) {
        fprintf(stderr, "w=%u r=%u\\n", hw.writes, hw.reads);
        fail("RX timeout counts");
    }

    unsigned accesses = hw.access_count, timer_reads = hw.timer_reads;
    if (SPI_Master_send_receive(&spi, tx, rx, 8) != -EIO ||
        hw.access_count != accesses || hw.timer_reads != timer_reads)
        fail("faulted exchange had side effects");
    /* recovery then same transfer succeeds */
    hw.stopped = 0;
    if (atcspi200_recover(&spi) != 0) {
        fail("recover after timeout");
    }
    if (!spi.ready) {
        fail("ready after recover");
    }
    if (SPI_Master_send_receive(&spi, tx, rx, 8) != 0) {
        fail("transfer after recover");
    }

    /* BUSY held beyond final RX */
    reset_hw(8, 2);
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("init busy hold");
    }
    hw.busy_hold = 1;
    if (SPI_Master_send_receive(&spi, tx, rx, 8) != -ETIMEDOUT) {
        fail("BUSY timeout rc");
    }
    if (hw.reads != 8 || hw.writes != 8) {
        fail("BUSY timeout counts");
    }
    if (spi.ready) {
        fail("ready after busy timeout");
    }
}

static void scenario_recover(void)
{
    unsigned char tx[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    unsigned char rx[8] = {0};
    reset_hw(8, 2);
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("init recover");
    }
    unsigned timing = spi.timing;
    if (SPI_Master_send_receive(&spi, tx, rx, 8) != 0) {
        fail("initial transfer");
    }
    /* blocked reset */
    hw.reset_blocked = 1;
    if (atcspi200_recover(&spi) != -ETIMEDOUT) {
        fail("blocked reset rc");
    }
    if (spi.ready) {
        fail("ready blocked reset");
    }
    hw.reset_blocked = 0;
    if (atcspi200_recover(&spi) != 0) {
        fail("recover succeed");
    }
    if (!spi.ready) {
        fail("not ready after recover");
    }
    if (spi.timing != timing || hw.timing != timing || hw.format != (7U << 8) || hw.irq_enable != 0) {
        fail("configuration not restored");
    }
    if (hw.resets_completed < 1 || hw.tx_count != 0 || hw.rx_count != 0) {
        fail("empty flags after recover");
    }
    if (SPI_Master_send_receive(&spi, tx, rx, 8) != 0) {
        fail("transfer after recover2");
    }

    /* bad empty */
    reset_hw(8, 2);
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("init bad empty");
    }
    hw.bad_empty = 1;
    if (atcspi200_recover(&spi) != -EIO) {
        fail("bad empty rc");
    }
    hw.bad_empty = 0;
    if (atcspi200_recover(&spi) != 0) {
        fail("bad empty recover");
    }
}

static void scenario_credit(void)
{
    unsigned char tx[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    unsigned char rx[8] = {0};
    reset_hw(8, 2);
    hw.first_delay = 20;
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("init credit");
    }
    if (SPI_Master_send_receive(&spi, tx, rx, 8) != 0) {
        fail("credit transfer");
    }
    if (hw.violations != 0) {
        fail("TX-without-RX credit");
    }
    if (hw.polls_before_rx < 2) {
        fail("delayed first RX");
    }
    if (hw.writes != 8 || hw.reads != 8) {
        fail("credit counts");
    }
}

static void scenario_wrap(unsigned near)
{
    unsigned char tx[1] = {42};
    unsigned char rx[1] = {0};
    reset_hw(8, 2);
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("init wrap");
    }
    hw.ms_offset = (unsigned int)(-500);
    unsigned before = spi_model_ms();
    hw.stopped = 1;
    if (SPI_Master_send_receive(&spi, tx, rx, 1) != -ETIMEDOUT) {
        fail("wrap timeout rc");
    }
    unsigned elapsed = spi_model_ms() - before;
    if (elapsed < 1000 || elapsed > 1001) fail("wrap deadline interval");
    /* Tick clock is 64-bit; exported milliseconds wrap modulo 32 bits. */
    (void)near;
}

static void scenario_inplace(void)
{
    unsigned char buf[16];
    for (unsigned i = 0; i < 16; ++i) {
        buf[i] = pattern(i);
    }
    reset_hw(8, 2);
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != 0) {
        fail("init inplace");
    }
    if (SPI_Master_send_receive(&spi, buf, buf, 16) != 0) {
        fail("inplace rc");
    }
    for (unsigned i = 0; i < 16; ++i)
        if (buf[i] != answer_byte(i, pattern(i))) fail("in-place data");
    if (hw.violations != 0 || hw.writes != 16 || hw.reads != 16) {
        fail("inplace counts");
    }
}

static void scenario_constructor_recovery(void)
{
    reset_hw(8, 2);
    hw.config = 0;
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != -ENODEV)
        fail("invalid capacity accepted");
    unsigned accesses = hw.access_count, timers = hw.timer_reads;
    if (atcspi200_recover(&spi) != -EINVAL || hw.access_count != accesses ||
        hw.timer_reads != timers) fail("recovery bypasses invalid init");
    reset_hw(8, 2);
    hw.timing = 0x200;
    hw.reset_blocked = 1;
    if (atcspi200_init(&spi, &hw, 80000000, 20000000) != -ETIMEDOUT)
        fail("initial reset timeout");
    hw.reset_blocked = 0;
    if (atcspi200_recover(&spi) || !spi.ready || hw.timing != 0x201 ||
        hw.format != 0x700) fail("recover after valid init reset timeout");
    unsigned resets = hw.reset_writes, formats = hw.format_writes;
    if (atcspi200_set_speed(&spi, 10000000) || hw.timing != 0x203 ||
        spi.actual_hz != 10000000 || hw.reset_writes != resets ||
        hw.format_writes != formats) fail("speed update only timing");
    if (atcspi200_recover(&spi) || hw.timing != 0x203 || spi.actual_hz != 10000000)
        fail("new divider preserved across reset");
}

int main(void)
{
    scenario_init();
    scenario_multiple();
    scenario_zero();

    /* all normal success cases */
    const unsigned sizes[] = {1, 2, 3, 4, 5, 15, 16, 29, 511, 512, 513, 1025};
    unsigned cases = 0;
    for (size_t k = 0; k < sizeof(sizes) / sizeof(sizes[0]); ++k) {
        for (unsigned mode = 0; mode < 4; ++mode) {
            for (unsigned end = 0; end < 2; ++end) {
                success(sizes[k], 8, 2, mode, (int)end);
                ++cases;
            }
        }
    }
    success(512, 16, 7, 0, 1);
    success(512, 4, 1, 0, 1);
    cases += 2;

    scenario_timeout();
    scenario_recover();
    scenario_credit();
    scenario_wrap(500);
    scenario_inplace();
    scenario_constructor_recovery();

    printf("PASS: %u buffer vectors and 9 scenario groups; register/FIFO/timeout checks\n", cases);
    return 0;
}

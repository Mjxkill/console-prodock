// G0/G1/G2/G3/G4 diagnostic console. Code in ITCM, writable data in ILM, stack in DLM.
// Commands: ? identification, D destructive DDR test, E + uint16 LE + data echo.
#include <stdio.h>
#include <stdint.h>
#include "ae350.h"
#include "cache.h"

#ifdef CONSOLE_GPU
#define GPU ((volatile uint32_t *)0xe9000000UL)
#define PAGE0 0x00800000UL
#define PAGE1 0x00900000UL
static unsigned displayed_page;
static unsigned page_sums[2];

static void gpu_status(void)
{
    printf("GPU base=%08x enable=%u frames=%u underflows=%u sum=%08x fetched=%u busy=%u layers=%u max_cycles=%u invalid=%u sprites=%u invalid_sprites=%u max_sprites=%u cache_cycles=%u max_sprite_pixels=%u cache_loads=%u\r\n",
           (unsigned)GPU[4], (unsigned)GPU[5], (unsigned)GPU[6], (unsigned)GPU[7],
           (unsigned)GPU[8], (unsigned)GPU[9], (unsigned)GPU[3],
           (unsigned)GPU[0x34/4],(unsigned)GPU[0x2c/4],(unsigned)GPU[0x38/4],
           (unsigned)GPU[0x44/4],(unsigned)GPU[0x48/4],(unsigned)GPU[0x4c/4],(unsigned)GPU[0x50/4],(unsigned)GPU[0x54/4],(unsigned)GPU[0x58/4]);
}

static unsigned demo_pixel(unsigned x, unsigned y, unsigned page)
{
    unsigned c = ((x * 8 / 800) << 5) | ((y * 8 / 480) << 2) | (((x >> 5) ^ (y >> 5)) & 3);
    if (page) c ^= 0xe3;
    if (x < 4 || x >= 796 || y < 4 || y >= 476) c = 255;
    if (x >= 280 && x < 520 && y >= 190 && y < 290) c = page ? 0x1c : 0xe0;
    return c;
}

static int gpu_commit(unsigned page)
{
    unsigned timeout = 1000000;
    while ((GPU[3] & 1) && --timeout) {}
    if (!timeout) return 0;
    GPU[1] = page ? PAGE1 : PAGE0;
    GPU[2] = 1;
    GPU[0x30/4]=0; // Legacy framebuffer mode, including after a G3 demo.
    GPU[0x40/4]=0;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    GPU[3] = 1;
    timeout = 1000000;
    while ((GPU[3] & 1) && --timeout) {}
    return timeout != 0;
}

static void gpu_demo(void)
{
    unsigned id = GPU[0];
    printf("GPU ID=%08x\r\n", id);
    if (id != 0x47505531U) { printf("GPU FAIL ID\r\n"); return; }
    // Program an RGB332 palette, expanded to the panel's RGB666.
    for (unsigned i = 0; i < 256; ++i) {
        unsigned r = (i >> 5) * 9, g = ((i >> 2) & 7) * 9, b = (i & 3) * 21;
        GPU[0x100 + i] = (r << 12) | (g << 6) | b;
    }
    for (unsigned page = 0; page < 2; ++page) {
        volatile uint32_t *dst = (volatile uint32_t *)(page ? PAGE1 : PAGE0);
        unsigned sum = 0;
        for (unsigned y = 0; y < 480; ++y)
            for (unsigned x = 0; x < 800; x += 4) {
                unsigned word = demo_pixel(x,y,page) | (demo_pixel(x+1,y,page) << 8)
                              | (demo_pixel(x+2,y,page) << 16) | (demo_pixel(x+3,y,page) << 24);
                *dst++ = word;
                sum += word;
            }
        page_sums[page] = sum;
        ae350_dcache_flush_range(page ? PAGE1 : PAGE0, 800UL * 480);
    }
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    displayed_page = 0;
    if (!gpu_commit(0)) { printf("GPU FAIL COMMIT\r\n"); return; }
    printf("GPU READY sum0=%08x sum1=%08x\r\n", page_sums[0], page_sums[1]);
}
#include "gpu_demo.h"
#include "gpu_layers_demo.h"
#include "gpu_sprites_demo.h"
#endif

static unsigned char get_byte(void)
{
    while (!(AE350_UART2->LSR & 1U)) {}
    return AE350_UART2->RBR;
}

static void put_byte(unsigned char c)
{
    while (!(AE350_UART2->LSR & 0x20U)) {}
    AE350_UART2->THR = c;
}

// Do not call printf from a trap: its formatter can hide the original fault.
long except_handler(long cause, long epc)
{
    const char *label = "\r\nTRAP cause/pc/value=";
    while (*label) put_byte(*label++);
    unsigned values[3] = {(unsigned)cause, (unsigned)epc, read_csr(NDS_MTVAL)};
    for (unsigned n = 0; n < 3; ++n) {
        for (int bit = 28; bit >= 0; bit -= 4) {
            unsigned digit = (values[n] >> bit) & 15;
            put_byte(digit < 10 ? '0' + digit : 'a' + digit - 10);
        }
        put_byte(' ');
    }
    put_byte('\r'); put_byte('\n');
    for (;;) {}
}

static void check(unsigned addr, unsigned expected, unsigned got, unsigned *errors)
{
    if (expected != got) {
        if (*errors < 8)
            printf("FAIL @%08x expected=%08x got=%08x\r\n", addr, expected, got);
        ++*errors;
    }
}

static unsigned pattern(unsigned addr, unsigned pass)
{
    if (pass == 0) return addr;
    if (pass == 1) return ~addr;
    unsigned x = addr ^ 0x9e3779b9U;
    x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    return x;
}

#ifdef CONSOLE_GPU
static void test_shared_ddr(void)
{
    unsigned errors = 0;
    for (unsigned a = 0x200000; a < 0x300000; a += 4)
        *(volatile uint32_t *)a = pattern(a, 2);
    ae350_dcache_flush_range(0x200000, 0x100000);
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    for (unsigned a = 0x200000; a < 0x300000; a += 4)
        check(a, pattern(a, 2), *(volatile uint32_t *)a, &errors);
    printf("SHARED END errors=%u\r\n", errors);
}
#endif

static void test_ddr(void)
{
    unsigned errors = 0;
    unsigned saved_cache = read_csr(NDS_MCACHE_CTL);
    printf("DDR BEGIN core=800MHz bytes=1048576 cache=%08x\r\n", saved_cache);
    // Writable state is in ILM/DLM, so cache maintenance cannot discard it.
    ae350_dcache_flush_all();
    clear_csr(NDS_MCACHE_CTL, 2);
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    volatile uint32_t *w = (volatile uint32_t *)0x00100000UL;
    volatile uint8_t *b = (volatile uint8_t *)w;
    volatile uint16_t *h = (volatile uint16_t *)w;
    printf("DDR MASK begin\r\n");
    for (unsigned lane = 0; lane < 64; ++lane) {
        for (unsigned i = 0; i < 16; ++i) w[i] = 0xa5a5a5a5U;
        b[lane] = (uint8_t)lane;
        for (unsigned i = 0; i < 64; ++i)
            check((unsigned)b + i, i == lane ? lane : 0xa5, b[i], &errors);
    }
    for (unsigned lane = 0; lane < 32; ++lane) {
        for (unsigned i = 0; i < 16; ++i) w[i] = 0x5a5a5a5aU;
        h[lane] = (uint16_t)(0x1200 + lane);
        for (unsigned i = 0; i < 32; ++i)
            check((unsigned)h + 2*i, i == lane ? 0x1200 + lane : 0x5a5a, h[i], &errors);
    }
    printf("DDR MASK errors=%u\r\n", errors);
    // Distinct addresses spanning the configured 1 GiB; catches address aliasing.
    *(volatile uint32_t *)0 = 0x12345678U;
    for (unsigned k = 2; k < 30; ++k)
        *(volatile uint32_t *)(1UL << k) = 0xabc00000U + k;
    check(0, 0x12345678U, *(volatile uint32_t *)0, &errors);
    for (unsigned k = 2; k < 30; ++k)
        check(1UL << k, 0xabc00000U + k, *(volatile uint32_t *)(1UL << k), &errors);
    printf("DDR ADDRESS errors=%u\r\n", errors);
    write_csr(NDS_MCACHE_CTL, saved_cache);
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    for (unsigned pass = 0; pass < 3; ++pass) {
        printf("DDR PASS %u write\r\n", pass);
        for (unsigned a = 0; a < (1UL << 20); a += 4)
            *(volatile uint32_t *)a = pattern(a, pass);
        ae350_dcache_flush_all();
        __asm__ volatile ("fence iorw, iorw" ::: "memory");
        for (unsigned a = 0; a < (1UL << 20); a += 4)
            check(a, pattern(a, pass), *(volatile uint32_t *)a, &errors);
        ae350_dcache_flush_all();
        printf("DDR PASS %u errors=%u\r\n", pass, errors);
    }
    printf("DDR END errors=%u\r\n", errors);
}

int main(void)
{
    const unsigned div = (80000000UL + 8UL * 115200) / (16UL * 115200);
    AE350_UART2->LCR |= 0x80;
    AE350_UART2->DLL = div & 0xff;
    AE350_UART2->DLM = div >> 8;
    AE350_UART2->LCR = 3;
    AE350_UART2->FCR = 7;
    for (;;) {
        switch (get_byte()) {
        case '?':
#ifdef CONSOLE_GPU
            printf("MegaPro GPU G4 core=800MHz bus=80MHz\r\n");
#else
            printf("MegaPro GPU G0 core=800MHz bus=80MHz\r\n");
#endif
            break;
#ifdef CONSOLE_GPU
        case 'V': gpu_demo(); break;
        case 'S': gpu_status(); break;
        case 'M': test_shared_ddr(); break;
        case 'L': gpu_layers_demo(); break;
        case 'P': gpu_layers_next(); break;
        case 'O': gpu_sprites_demo(); break;
        case 'N': gpu_sprites_next(); break;
        case 'B':
            // Return to the front page before modifying the back page.
            if (!GPU[5]) gpu_demo();
            if (!gpu_commit(0)) printf("BLIT FAIL COMMIT\r\n");
            else { displayed_page=0; gpu_accel_demo(); }
            break;
        case 'F':
            displayed_page ^= 1;
            if (!gpu_commit(displayed_page)) printf("GPU FAIL COMMIT\r\n");
            else printf("GPU FLIP page=%u\r\n", displayed_page);
            break;
#endif
        case 'D': test_ddr(); break;
        case 'E': {
            unsigned n = get_byte();
            n |= (unsigned)get_byte() << 8;
            while (n--) put_byte(get_byte());
            break;
        }
        default: break;
        }
    }
}

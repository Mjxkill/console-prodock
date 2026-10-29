/* Destructive DDR test, executed entirely from ITCM with a DTCM stack.
 * No Linux, libc, caches, DMA or SD accesses. Results survive DDR corruption.
 * CONFIG at DTCM+0x800: magic, mode (0=short, 1=full), seed.
 * Result words at DTCM+0x1000 are decoded by tools/board/check_ddr.py.
 */
#include <stdint.h>

#define R ((volatile uint32_t *)0xa0201000u)
#define C ((volatile uint32_t *)0xa0200800u)
#define DDR_END 0x40000000u
#define MMIO(a) (*(volatile uint32_t *)(a))
#define FENCE() __asm__ volatile("fence rw,rw" ::: "memory")

__attribute__((naked, aligned(4))) void trap(void)
{
	__asm__ volatile("li t1,0xa0201000\n"
		"csrr t0,mcause\n sw t0,60(t1)\n"
		"csrr t0,mepc\n sw t0,64(t1)\n"
		"csrr t0,mtval\n sw t0,68(t1)\n"
		"li t0,3\n sw t0,8(t1)\n 1: j 1b");
}

static void check(uint32_t addr, uint32_t expected, uint32_t got)
{
	R[10]++;
	if (expected == got) return;
	if (!R[6]) { R[12] = addr; R[13] = expected; R[14] = got; }
	if (R[6] < 32) {
		unsigned n = 256 + R[6] * 4;
		R[n] = R[3]; R[n+1] = addr; R[n+2] = expected; R[n+3] = got;
	}
	R[6]++; R[7]++;
}

static uint32_t pattern(uint32_t a, unsigned kind, uint32_t seed)
{
	uint32_t x = a ^ seed;
	if (kind == 0) return x;
	if (kind == 1) return ~x;
	if (kind == 3) return 0xaaaaaaaau;
	if (kind == 4) return 0x55555555u;
	x ^= 0x9e3779b9u;
	x ^= x << 13; x ^= x >> 17; x ^= x << 5;
	return x;
}

static void begin(unsigned stage)
{
	R[3] = stage; R[4] = 0; R[5] = 0; R[7] = 0;
}

static void finish(void)
{
	R[32 + R[3]*4] = R[7];
	R[33 + R[3]*4] = R[10];
	R[34 + R[3]*4] = R[11];
	R[35 + R[3]*4] = 0x444f4e45u;
	R[18]++;
}

/* Address bits 2..29: hold all signatures simultaneously to catch aliasing. */
static void address_bus(void)
{
	begin(0);
	MMIO(0) = 0x13579bdfu;
	for (unsigned k=2; k<30; k++) MMIO(1u<<k) = 0xa5c30000u | k;
	FENCE();
	check(0, 0x13579bdfu, MMIO(0));
	for (unsigned k=2; k<30; k++)
		check(1u<<k, 0xa5c30000u | k, MMIO(1u<<k));
	for (unsigned k=2; k<30; k++) {
		MMIO(1u<<k) = 0x5a3cffffu ^ k;
		FENCE();
		check(0, 0x13579bdfu, MMIO(0));
		for (unsigned j=2; j<30; j++)
			check(1u<<j, j==k ? (0x5a3cffffu ^ k) : (0xa5c30000u | j), MMIO(1u<<j));
		MMIO(1u<<k) = 0xa5c30000u | k;
	}
	R[11] += 85;
	finish();
}

/* Data-line walking ones/zeros at both ends of each 64-MiB region. */
static void data_bus(void)
{
	begin(1);
	for (unsigned region=0; region<16; region++)
	for (unsigned edge=0; edge<2; edge++) {
		uint32_t base = region * 0x04000000u + (edge ? 0x03ffff80u : 0);
		for (unsigned bit=0; bit<32; bit++)
		for (unsigned inv=0; inv<2; inv++) {
			uint32_t value = inv ? ~(1u<<bit) : (1u<<bit);
			for (unsigned lane=0; lane<32; lane++) MMIO(base+4*lane) = value ^ (lane&1 ? ~0u : 0);
			FENCE();
			for (unsigned lane=0; lane<32; lane++)
				check(base+4*lane, value ^ (lane&1 ? ~0u : 0), MMIO(base+4*lane));
			R[11] += 32;
		}
	}
	finish();
}

static void range(uint32_t start, uint32_t bytes, unsigned kind, uint32_t seed, unsigned phase)
{
	R[4] = phase;
	uint32_t end = start + bytes;
	for (uint32_t n=0; n<bytes; n+=4) {
		uint32_t a = phase==3 ? end-4-n : start+n;
		if (!(n & 0xfffffu)) R[5] = a;
		uint32_t e = pattern(a,kind,seed);
		if (phase==1) MMIO(a) = e;
		else check(a,e,MMIO(a));
	}
	if (phase==1) R[11] += bytes/4;
	FENCE();
}

/* Full mode covers every DDR word with address data and two read orders.
 * Remaining patterns cover 8 MiB in each 64-MiB region (128 MiB total).
 * Short mode covers 1 MiB per region for all patterns (16 MiB total).
 * All regions are written before reading any: distant aliasing is visible.
 */
static void patterns(unsigned full, uint32_t seed)
{
	for (unsigned kind=0; kind<5; kind++) {
		begin(2+kind);
		for (unsigned phase=1; phase<=3; phase++) {
			if (full && kind==0) range(0,DDR_END,kind,seed,phase);
			else for (unsigned n=0; n<16; n++) {
				unsigned region = phase==3 ? 15-n : n;
				uint32_t size = full ? 0x800000u : 0x100000u;
				uint32_t offset = (region & 1) ? 0x4000000u-size : 0;
				range(region*0x4000000u+offset,size,kind,seed,phase);
			}
		}
		finish();
	}
}

/* Exercise byte enables in every lane of a 128-bit DDR response and check
 * untouched neighbours, then halfword enables. Aligned accesses only.
 */
static void masks(void)
{
	begin(7);
	for (unsigned region=0; region<16; region++) {
		uint32_t base = region*0x04000000u + 0x00100000u;
		for (unsigned n=0; n<4096; n+=16) {
			uint32_t a=base+n, expected[4];
			for (unsigned i=0; i<4; i++) expected[i]=MMIO(a+4*i)=0x96a53cc3u;
			for (unsigned lane=0; lane<16; lane++) {
				unsigned shift=(lane&3)*8, i=lane/4;
				uint32_t v=(lane*37+n+region)&255;
				*(volatile uint8_t *)(a+lane)=v;
				expected[i]=(expected[i]&~(255u<<shift))|(v<<shift);
				FENCE();
				for (unsigned j=0; j<4; j++) check(a+4*j,expected[j],MMIO(a+4*j));
			}
			for (unsigned lane=0; lane<8; lane++) {
				unsigned shift=(lane&1)*16, i=lane/2;
				uint32_t v=(lane*413+n+region)^0x5aa5;
				*(volatile uint16_t *)(a+2*lane)=v;
				expected[i]=(expected[i]&~(65535u<<shift))|(v<<shift);
				FENCE();
				for (unsigned j=0; j<4; j++) check(a+4*j,expected[j],MMIO(a+4*j));
			}
			R[11]+=28;
		}
	}
	finish();
}

static void retention(uint32_t seed)
{
	begin(8);
	for (unsigned r=0; r<16; r++) range(r*0x04000000u,0x100000u,2,seed,1);
	R[4]=4;
	uint32_t start=MMIO(0xe800009cu);
	while ((uint32_t)(MMIO(0xe800009cu)-start)<30000) __asm__ volatile("nop");
	for (unsigned repeat=0; repeat<4; repeat++)
		for (unsigned r=0; r<16; r++) range(r*0x04000000u,0x100000u,2,seed,2+(repeat&1));
	finish();
}

void run(void)
{
	for (unsigned i=0; i<512; i++) R[i]=0;
	R[0]=0x44445254u; R[1]=1; R[2]=1;
	__asm__ volatile("csrw mtvec,%0" :: "r"(trap));
	__asm__ volatile("csrr %0,0x7ca" : "=r"(R[8]));
	__asm__ volatile("csrr %0,0x7d0" : "=r"(R[9]));
	R[19]=DDR_END; R[20]=C[2]; R[21]=C[1];
	/* Do not run a destructive test with an active acquisition writer. */
	if (C[0]!=0x44445243u || C[1]>1 || (R[8]&3) ||
	    MMIO(0xe8000000u)!=0x4c413136u || (MMIO(0xe8000038u)&0x80000000u)) {
		R[2]=4;
		for (;;) __asm__ volatile("nop");
	}
	address_bus(); data_bus(); patterns(C[1],C[2]); masks(); retention(C[2]);
	FENCE(); R[2]=2;
	for (;;) __asm__ volatile("nop");
}

__attribute__((naked,section(".entry"))) void _start(void)
{
	__asm__ volatile("csrwi mie,0\n csrwi mstatus,0\n csrwi satp,0\n sfence.vma\n"
		"li t0,6\n csrw 0x7cc,t0\n csrwi 0x7ca,0\n"
		"csrci 0x7d0,8\n csrsi 0x7d0,4\n fence rw,rw\n fence.i\n"
		"li sp,0xa020f000\n j run");
}

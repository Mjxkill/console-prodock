// E2 : bannière puis écho binaire pour vérifier AE350 <-> USB CDC.
// Horloges : cœur 800 MHz, AHB/APB 80 MHz ; UART2 115200, 8N1.
#include <stdio.h>
#include "ae350.h"

#define CONSOLE_PCLK_HZ 80000000UL

static void console_init(unsigned long baud)
{
	unsigned long div = (CONSOLE_PCLK_HZ + 8UL * baud) / (16UL * baud);
	AE350_UART2->LCR |= 0x80;
	AE350_UART2->DLL = div & 0xff;
	AE350_UART2->DLM = (div >> 8) & 0xff;
	AE350_UART2->LCR = 0x03;          // 8 bits, 1 stop, sans parité, DLAB = 0
	AE350_UART2->FCR = 0x07;          // FIFO activées et vidées
}

int main(void)
{
	console_init(115200);
	printf("\r\nMegaPro Console E2 : AE350 800 MHz, APB 80 MHz, echo UART2\r\n");
	while (1) {
		if (AE350_UART2->LSR & 1U) {
			unsigned char c = AE350_UART2->RBR;
			while (!(AE350_UART2->LSR & 0x20U)) {}
			AE350_UART2->THR = c;
		}
	}
	return 0;
}

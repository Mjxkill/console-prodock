// SPDX-License-Identifier: BSD-2-Clause
/* Derived from the LA16 platform override, adapted to C37 on the Pro Dock. */
#include <libfdt.h>
#include <platform_override.h>
#include <sbi/riscv_asm.h>
#include <sbi/riscv_io.h>
#include <sbi/sbi_error.h>
#include <sbi/sbi_ecall.h>
#include <sbi/sbi_trap.h>
#include <sbi_utils/fdt/fdt_helper.h>
static int prodock_early_init(bool cold, const void *dt, const struct fdt_match *m)
{
    (void)dt; (void)m;
    if (!cold) return 0;
    if (readl((void *)0xe9000000) != 0x47505531 ||
        readl((void *)0xe9001000) != 0x424c5432 ||
        readl((void *)0xe9001030) != 0x1ff)
        return SBI_ENODEV;
    if ((csr_read(0x7ca) & 3) != 3) return SBI_EINVAL;
    /* BSP enables Andes vectored/preemptive mode; generic Linux must not. */
    writel(0, (void *)0xe4000000);
    return 0;
}
/* Private Pro Dock functions within the Andes vendor extension. PIO drivers
 * do not need DMA services. The GPU owns separate reserved DDR; CPU writers
 * publish it before submission and invalidate after GPU completion.
 * L1D WBINVAL_ALL=6 is the SDK operation already qualified on this A25.
 * Single hart, M-mode interrupts masked by the SBI trap handler. */
static int prodock_vendor(long fid, struct sbi_trap_regs *regs,
                          struct sbi_ecall_return *out, const struct fdt_match *m)
{
    (void)regs; (void)m;
    if (fid == 0x101) { out->value = 0x50444301; return 0; }
    if (fid != 0x100) return SBI_ENOTSUPP;
    __asm__ volatile("fence iorw,iorw" ::: "memory");
    csr_write(0x7cc, 6);
    __asm__ volatile("fence iorw,iorw" ::: "memory");
    out->value = 0;
    return 0;
}
static const struct fdt_match prodock_match[] = {
    { .compatible = "mjx,prodock-linux" }, { }
};
const struct platform_override prodock = {
    .match_table = prodock_match, .early_init = prodock_early_init,
    .vendor_ext_provider = prodock_vendor,
};

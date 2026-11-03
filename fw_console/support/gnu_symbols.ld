/* gnu_symbols.ld — symboles que l'éditeur de liens Andes (nds ld) fournit implicitement et que
 * GNU ld (toolchain xPack de GMD) ne fournit pas quand on impose un script -T.
 * Script implicite : passé au linker SANS -T, il complète le ae350-*.ld du BSP Gowin. */

/* gp : convention RISC-V = début des petites données + 0x800 (accès ±2 Ko en 1 instruction). */
PROVIDE(__global_pointer$ = ADDR(.sdata) + 0x800);

/* Fin du tas pour _sbrk (demo/stubs/sbrk.c). Valeur fournie par le Makefile de l'application
 * (-Wl,--defsym=_heap_end=…) selon la mémoire où elle s'exécute ; pas de valeur par défaut
 * silencieuse : si absente, le lien échoue. */

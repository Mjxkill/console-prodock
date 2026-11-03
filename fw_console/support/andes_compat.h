// andes_compat.h — équivalents des fonctions intégrées du compilateur Andes utilisées par le
// BSP Gowin (RiscV_AE350_SOC_V1.3), pour la toolchain xPack GCC de GMD. Injecté par -include
// (toolchain.mk) pour ne pas modifier le SDK. Seul __nds__mfsr est appelé par le BSP
// (trap.c:87, lecture de mhartid) ; on n'ajoute un équivalent que quand le lien le réclame,
// pour ne pas masquer un usage non vérifié (règle : pas de repli silencieux).
#pragma once
#define __nds__mfsr(csr) \
	({ unsigned long __v; __asm__ volatile("csrr %0, %1" : "=r"(__v) : "i"((csr))); __v; })

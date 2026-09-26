# TESTS E0 — Tang Mega 138K Pro Dock, console de jeux (2026-09-25)

**E0c : VALIDÉE par Michael (25/09 soir) — écran 800×480 affiche la mire.**

Architecture de référence : `ARCHI/ARCHI_V1.md` (validée par Michael le 25/09 : 8 bpp, langage
maison grammaire § 5 « on essaie comme ça », soft USB à la place du BL616).

## E0a — chemin de programmation + soft USB Sipeed (bitstream d'exemple)

| Test | Résultat |
|---|---|
| Détection JTAG Pro Dock | idcode 0x1081b, `Gowin GW5AST-138`, irlen 8 — via `openFPGALoader --busdev-num 5:9 -b tangmega138k --detect` ✓ |
| Chargement SRAM bitstream Sipeed `usb_uart_loopback` | `Done / DONE` ✓ |
| Énumération CDC-ACM | `/dev/ttyACM0` = `Sipeed Tang USB2Serial` (359f:2010), **pas de BL616** ✓ |
| Loopback UART | `console E0a test / ping 0123456789` renvoyé à l'identique ✓ |

## E0b — premier bitstream console (mire LCD + soft USB CDC maison)

Build : `tang/build_e0b.tcl` (gw_sh 1.9.12 headless), device **GW5AST-LV138FPG676AC1/I0**
(gw5ast138b-007), bitstream `tang/impl/pnr/console_e0b.fs` (34 Mo).

Panneau réel : **CJ050QGH50-05442Y-05** = 5 pouces **800×480** (référence lue au dos par Michael).
Les demos 480×272 du dépôt Sipeed ne correspondent PAS à ce panneau : `lcd_timing.v` et la PLL
ont été remplacés par ceux de `rgb_screen/800_480_screen` (pclk 35 MHz = 50×21/30).

| Test | Résultat |
|---|---|
| Build complet (synthèse + P&R + bitstream) | `Bitstream generation completed` ✓ |
| Timing (TNS) | 0,000 sur toutes les horloges ✓ |
| Chargement SRAM sur carte | `Done / DONE` ✓ |
| Énumération CDC | `/dev/ttyACM0` = `Electrosens MegaPro Console` (359f:2011) ✓ |
| Loopback UART sur notre bitstream | renvoyé à l'identique ✓ |
| **Mire LCD 800×480** | **VALIDÉE par Michael (E0c)** : barres colorées visibles ✓ |

## Diagnostics E0b (faits mesurés, non-négociables pour la suite)

1. **PLLs toujours placées explicitement** dans le `.cst` (SUG935 A.3.2, `INS_LOC "u_.../PLL_inst"`) :
   USB → `PLL_R[0]`/`PLL_R[1]`, LCD → `PLL_L[0]`. Sans ces contraintes, le placeur libre casse
   l'énumération USB (reproduit 2× : builds 22:47 et plonly 22:34 vs OK 22:26 / 23:0x).
2. **`lcd_clk` routé du port PLL directement au pin** (modèle exact de la demo Sipeed 800×480).
   Mesuré : dès que `lcd_clk_pix` sort par un assign banal (consommateurs internes + sortie),
   l'USB tombe ; en port-PLL → pin direct, tout marche (énum + loopback).
   Note : le `WARN PR1014` (clk_d en routage générique) apparaît dans les deux cas — non corrélable.
3. **`PRODUCTSTR_LEN`** = longueur exacte de la chaîne (EX3784, « MegaPro Console » = 15).
4. **Énumération CDC après re-câblage** : elle ne revient qu'au prochain chargement de bitstream —
   pas un bug : recharger pour tester, toujours.
5. **`usb_desc` Sipeed** : pas de ports `o_desc_index/o_desc_type` malgré le TOP de leur exemple.

## Identification des cartes (règle de routage — ne jamais se fier à l'index)

| Carte | Détection | Usage |
|---|---|---|
| **Pro Dock (console)** | USB Debugger Sipeed, série **2023112818**, dev `5-2.3` (devnum variable, toujours relire) | `-b tangmega138k` |
| Tang Console (analyseur, NE PAS TOUCHER) | USB Debugger Sipeed, série **2025041420**, dev `3-4.4.1` | `-b tangconsole` |
| ESP-Prog (JTAG AE350 de la Console) | FTDI `Dual RS232-HS` sur `3-4.4.2` | — |

Le port SOFT-USB du Pro Dock apparaît comme `359f:2010` (Sipeed) ou `359f:2011` (notre CDC) —
c'est **un autre câble USB-C** que le JTAG|UART.

## Étape suivante (E1)

- E1 : AE350 + DDR3 sur le Pro Dock — critère `pro_ddr_test` (`57 52 FF FF FF` sur la console).
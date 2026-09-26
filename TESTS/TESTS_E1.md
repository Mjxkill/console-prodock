# TESTS E1 — Tang Mega 138K Pro Dock, AE350 + DDR3 (2026-09-26)

**E1 : VALIDÉE (26/09, fin de session) — `WR FF FF FF` reçu sur le CDC : la DDR3 écrit et relit
les 16 777 215 mots de 256 bits sans erreur (num_ok = 0xFFFFFF, critère Sipeed `57 52 FF FF FF`).**

Le bitstream validé : `tang/impl/pnr/ddr_e1_cdc.fs` (LCD 800×480 mire + CDC + moteur de test DDR3).

## Configuration qui débloque (invariants de build E1)

1. **CLOCK_LOC avec chemin hiérarchique complet** pour le sclk du PHY USB :
   `CLOCK_LOC "u_usb_softphy_top/usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/sclk" BUFG[7] = CLK`
   (le nom court "sclk" n'est pas trouvé par le CST — le net vit dans la netlist chiffrée).
2. **Les 8 CLOCK_LOC** : clk_d/phy_clk/fclk_960m/clk48/lcd_clk_d → BUFG[0..4], sclk → BUFG[7].
   Sans eux, `clk_d` (50 MHz, les 4 PLLs) tombe en LW et le PHY USB ne se cale plus.
3. **Placement PLL** : F→R[0], B→R[1] (côté du pin 50 MHz), LCD→L[1], DDR→L[0] (côté du PHY DDR3).
4. **Boucle `pll_stop` câblée** : la netlist DDR3 sort `pll_stop`, la PLL Sipeed l'écoute via
   `enclk2` (câblage exact du top Sipeed). Sans ce fil, la PLL interne du PHY DDR3 ne démarre
   jamais → `clk_x1` mort → le test reste en état 0.
5. **Contraintes Sipeed** : `u_dll` → DDRDLLM_BL, `fclkdiv` → LEFTSIDE[4] (chemins `u_ddr3/gw3_top/...`).
6. **Déclaration `pll_stop` en tête de module** (default_nettype none : pas de wire implicite).

## Bugs corrigés pendant E1 (non-régression)

1. `pll_ddr_lock` flottant après le retrait de la PLL Sipeed (la netlist attend `pll_lock` en entrée).
2. Machine CDC « flood » : 60 000 impulsions `W` par ms (287 670 octets en 60 s) → FIFO EP2 noyé.
   Corrigé : **un octet par transition d'état**.
3. Émission CDC avant `usb_online` → EP0 bloqué. Corrigé : conditionnée à `usb_online`.
4. Conflit PLL_L[0] (LCD et DDR sur la même position) → LCD passée en L[1].
5. LED0 : le « battement » ne pouvait jamais atteindre 0xFF (compteur 1,7 M) — remplacé par
   `usb_online` (LED0 = USB configuré, plus parlant).

## Tests

| Test | Résultat |
|---|---|
| Build E1-CDC (LCD + CDC + netlist DDR3 + PLL DDR Sipeed) | `Bitstream generation completed` ✓ |
| Timing | TNS 0,000 toutes horloges ✓ |
| Horloges globales | toutes PRIMARY sauf `memory_clk` (HCLK BANK6/7 — routage dégradé mais fonctionnel) |
| Énumération CDC | ttyACM0 = Electrosens MegaPro Console ✓ |
| USB configuré (LED0) | allumée : SET_CONFIGURATION reçu ✓ |
| Calibration DDR3 (LED5) | allumée : init_calib_complete ✓ |
| **Rafale `57 52 FF FF FF` sur le CDC** | **REÇUE ✓** — DDR3 écrite et relue, 0xFFFFFF |
| Test DDR3 en boucle | première rafale `WR FF FF FF` reçue ; la boucle suivante ne re-émet pas (état à vérifier, LED0) |

## Non-régression à jouer avant E2

- Recharger E0b et confirmer mire + CDC (fait plusieurs fois ce jour ✓)
- Recharger E1-CDC et confirmer la rafale (fait ce jour : 1 rafale reçue ✓)

## Étape suivante (E2)

- AE350 sur le Pro Dock : portage de l'analyseur (ae350_soc) + console CDC pour le langage.
- Le lien de chargement des programmes restera le CDC (décision actée).

## E1 — test DDR3 Sipeed (pro_ddr_test), console par CDC

#
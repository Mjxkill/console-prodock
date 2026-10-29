# Relais de sortie BL616 : revue N56 / N56r1

`result.json` compare sans accès matériel les netlists routées du parent N56
et de N56r1. Les 342 primitives de `u_console_output`, dont 155 bascules, leurs
connexions et leurs paramètres sont identiques. Les pilotes externes et buffers
IO sélectionnés sont également identiques.

- Toutes les bascules du relais utilisent `vid_hclk`, alias physique du bus
  80 MHz provenant de `u_pll_ae350/u_pll/PLL_inst.CLKOUT0`, routé PRIMARY.
- L'entrée série provient directement de `UART2_TXD` du hard AE350. Elle passe
  par deux bascules de synchronisation avant décodage.
- Le reset est `ae350_rst_sync[1]`, généré par deux DFFPE initialisées à 1.
  Leur PRESET est l'inverse de la validation combinée PLL/initialisation.
- Aucun CE/reset du relais n'est présent dans le tableau des routes globales.
  Le plus grand groupe de CE local comporte 16 bascules.
- La sortie `uart_tx_d` provient de `u_console_output/u_tx/tx_s0` (DFFSE,
  INIT=1), puis de l'OBUF `uart_tx_obuf`. Le rapport place `uart_tx` en U15,
  LVCMOS33, drive 8 mA ; `uart_rx` est en V14 avec pull-up.
- Le RTL fixe RX=694 cycles/bit, soit environ 115274 bauds à 80 MHz, et TX=40
  cycles/bit, soit 2 Mbauds. Les commentaires génériques parlant de 100 MHz
  dans le fichier vendor ne correspondent pas aux paramètres de cette instance.

Le relais **de sortie** ne dépend ni de `phy_clk` ni de `usb_app_reset`.
L'arbitre **d'entrée** utilise en revanche ces signaux et n'est pas couvert par
cette comparaison. Le relais de sortie emploie une petite FIFO de registres
dans un domaine unique, pas une FIFO asynchrone.

Aucun défaut de raccordement ou changement logique N56→N56r1 n'est identifié
ici. Cette revue n'explique pas à elle seule la console muette : elle ne mesure
ni le signal UART natif, ni le niveau de reset en fonctionnement, ni les
broches ou le relais BL616. L'identité des équations ne prouve pas le timing
effectif ou l'absence de défaut électrique. Les SHA des sources, rapports et
netlists lus sont conservés dans `result.json`.

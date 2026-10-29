# Candidat 02 couplé : parent R21r1 conservé

Ce candidat reprend les corrections du candidat01 et couple son entrée
`pll_ready` à `pll_ae350_lock && ae350_por_n`. Ainsi, une assertion effectivement
retenue par la première chaîne asynchrone invalide également la qualification.
Cette amélioration traite une incohérence de contrat possible ; elle ne prouve
ni une capture physique asymétrique sur la carte, ni la cause du démarrageR21.

Le parent R21r1, R19 et la ProDock ne sont pas modifiés. Le build isolé est
`tang/impl/console_neo_n56r21r2_resetqual_coupled`. L'assemblage conserve toutes
les sources sauf le helper Neo et le raccordement du top. La netlist conserve
les modules UART RX, DDR, GPU et PLL byte pour byte. Hors helper, elle ajoute
une LUT2 dans le top pour le couplage et une LUT2 dans le SoC pour l'assertion
de CLEAR des deux init_sync. CLK, D, CE et INIT des quatre bascules restent
identiques. CST, SDC et options PnR sont identiques.

Le test `check_mapped.py` extrait les cellules réellement assemblées, sans
changer leurs équations, puis utilise les primitives fonctionnelles officielles.
Deux LUT4 du parent calculent respectivement l'état PLL qualifié (INIT8000) et
son complément (INIT7FFF) depuis les mêmes trois bits d'état et PLLLOCK.
Le test fixe l'état de PLL_INIT à111 et fait varier LOCK, DDRready et UART :
c'est une frontière de stimulation explicite, pas un modèle de PLL ou du CPU.
La netlist mappée est comparée à chaque front et perte asynchrone au RTLcouplé.
Le banc générique surveille chaque montéePOR et les délais2ms/50ms.

La tentative d'exécuter exactement les mêmes primitives sous Verilator a été
refusée : `assign/deassign` Verilog1995 n'est pas pris en charge par cet outil.
Aucun modèle de remplacement n'a été introduit pour contourner ce refus.
L'exécution fonctionnelle mappée se poursuit sous Icarus4états.

La largeur minimale d'une impulsion capturable dans le FPGA, la métastabilité,
la récupération/removal et le timing physique des nouveaux resets ne sont
pas qualifiés par ces tests. Les impulsions numériques1ns ne constituent pas
une spécification électrique. Les nouveaux CLEAR asynchrones et leur libération
via les deux registres AHB doivent être examinés après routage, sans élargir
les exceptions pour obtenir artificiellement PASS.

# Candidat isolé 01 : qualification reset

Ce candidat reste un témoin de simulation non routé. La variante couplée suivante
se trouve dans `../candidate_02`. Les sources partagées et les références FPGA
sont inchangées.

`rtl_result.json` lie les trois phases Verilator complètes (1 / 3,125 / 11 ns),
la phase Icarus 4 états complète et le témoin original en échec attendu. Chaque
cas utilise le délai réel de 50 ms. Le banc surveille chaque montée POR, refuse
les autorisations périmées et les impulsions supplémentaires, teste les pertes
LOCK/DDR brèves, les pertes en début/fin d’attente, UART modes0/1, commandes
invalides/expirées, AHB arrêté, puis clk50 arrêté/repris.

Le banc initial (`invariants_tb_initial.sv`) avait une attente de phase absolue
modulo100ns. Après l’arrêt/reprise de clk50, ses fronts étaient décalés de10ns :
le rendez-vous n’arrivait plus au cas15. Ses trois timeouts sont conservés.
La version v2 retire uniquement cette condition ; aucun changement du candidat.

Mode0 impose désormais une nouvelle attente2,08ms, au lieu du bypass historique.
Mode1 conserve50ms. Les impulsions numériques1ns ne prouvent pas la capture
physique d’une impulsion1ns par le FPGA. Synthèse/mapping, STA et carte restent
des validations distinctes. Aucun lien causal avec l’échec matérielR21 n’est établi.

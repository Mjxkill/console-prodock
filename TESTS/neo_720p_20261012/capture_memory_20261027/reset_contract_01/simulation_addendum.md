# Addendum après autorisation de simulation et correctif isolé

La restriction du rapport papier initial portant sur une autorisation distincte
des simulations est levée par l'instruction root/utilisateur suivante. Les preuves
papier originales restent figées ; cet addendum ne les remplace pas.

Le RTL exact partagé par les snapshotsR19 etR21r1 a reproduit deux défauts
numériques du reset : une qualification50ms conservée après une perteLOCK
entre deux fronts50MHz, puis une impulsion POR d'un cycle80MHz issue d'un bit
d'autorisation périmé dans le pipeline alors que le compteur est déjà invalidé.
La phase et la largeur changent l'expression du défaut ; les trois phases ont
été testées et le cas canonique est identique sous deux simulateurs.

La preuve de reproduction est `simulation_01/result.json`. Le terme
REPRODUCTION_PASS qualifie la détection du défaut, pas le RTL comme sain.

Le banc générique suivant, indépendant des comptes de défaut par phase, refuse
toute montéePOR avant le nouvel intervalle et couvre UART/arrêts d'horloge.
L'original échoue sur le premier cas court (47ns, condition2ms violée). Le
candidat01 passe trois phases Verilator et une suite complète Icarus4états ;
le résultat est `candidate_01/rtl_result.json`. Les quatre phases supplémentaires
sont conservées séparément par root dans `root_phase_sweep_01/result.json`.

La première version du banc générique a rencontré un timeout causé par son
attente modulo100ns après décalage de phase de10ns du clk50 relancé. Retirer
ce rendez-vous impossible est le seul changementv2 ; les logs initiaux sont
conservés et ne sont pas présentés comme défaut du candidat.

Le candidat02 ajoute le couplage de la qualification à la première chaîne
de reset pour imposer une nouvelle attente quand cette chaîne a effectivement
retenu une perteLOCK. Les contre-revues restent des analyses à vérifier,
et les primitives mappées sont testées séparément.

Aucune de ces preuves numériques n'établit la cause physique de l'échec de
démarrageR21r1, ni la capture électrique d'une impulsion1ns. Aucune carte,
source commune, référence ProDock ou bitstream existant n'est modifié.

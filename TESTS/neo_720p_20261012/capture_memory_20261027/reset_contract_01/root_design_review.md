# Revue indépendante du correctif de qualification R21r1

27 octobre 2026. Revue de conception par l'agent principal, avant assemblage
et routage du candidat. Ce document ne qualifie aucun bitstream.

## Modification examinée

Le parent est `console_neo_n56r21r1_capture_memory`. Les changements restent
dans un candidat Neo isolé : `neo_reset_trial.v` et le raccord de son
autorisation dans `console_neo.v`. Les sources communes, la DDR, les PLL et
la Pro Dock ne sont pas modifiées par cette correction.

Dans `ae350_soc.v`, `rst_key_n` ne commande que les deux bascules
`init_sync`, hors du fil `unused`. La nouvelle condition ne réinitialise
donc pas le contrôleur DDR. `init_sync[1]` alimente ensemble POR_RSTN et
HW_RSTN du macro AE350, comme dans le parent.

## Pourquoi les deux défauts logiques sont corrigés

1. Une chute de `ddr_ready && pll_ready` efface asynchronement les deux
   bascules `ready_meta`. Elle abaisse aussi immédiatement
   `release_request`. Une impulsion située entre deux fronts de clk50 ne
   peut plus conserver l'autorisation jusqu'au prochain front.
2. Au retour de cette disponibilité, `ready_meta` passe par 00, 01, 11.
   Le compteur observe donc obligatoirement un zéro avant de recommencer.
   Son ancienne valeur et `delay_done` ne peuvent pas être réutilisés.
3. L'autorisation devient également une condition de maintien hors reset
   des deux bascules finales :
   `CLEAR = ae350_rst_sync[1] || !trial_release` en polarité active haute.
   Une perte d'autorisation efface **les deux étages** ; un ancien 1 ne peut
   plus traverser le second étage après l'annulation du délai.
4. La sortie du reset attend ensuite deux fronts AHB. Le compteur reste
   dans clk50 et les deux étages finaux restent dans AHB ; aucun compteur
   multibit ne traverse cette frontière.
5. Une commande UART valide remet le compteur à zéro, impose le maintien
   demandé, puis exige une nouvelle qualification. Le mode normal conserve
   2 500 000 cycles à 50 MHz, soit 50 ms nominaux. Le mode de diagnostic
   court attend désormais 104 000 cycles, soit 2,08 ms nominaux ; il ne
   contourne plus la qualification LOCK de la documentation UG306-1.0.9E.

La marge 50 ms est une politique choisie pour cette expérience, pas une
durée minimale AE350 établie par la documentation. Le minimum 2 ms concerne
la confirmation du verrouillage PLL. Les valeurs en secondes supposent
l'horloge de référence nominale ; les simulations idéales n'en mesurent pas
la tolérance réelle.

## Ce que cette logique ne prouve pas

- La simulation prouve le comportement sur les stimuli injectés. Elle ne
  prouve pas qu'une perte LOCK identique se produit sur R21r1 physique.
- La capture d'une impulsion très courte dépend de la largeur minimale
  acceptée par les entrées asynchrones et du routage. Un test RTL de 1 ns
  n'est pas une garantie de capture de 1 ns en silicium.
- Le circuit n'est pas un détecteur de perte d'horloge : si une horloge
  s'arrête sans changement de LOCK/disponibilité ni commande, aucun nouveau
  reset n'est promis. Les essais d'horloge arrêtée doivent préciser le
  signal d'invalidation ou la commande utilisés.
- Le macro CPU, ses séquences internes et les phénomènes analogiques PLL
  ne sont pas remplacés par un modèle validé par ces bancs.

## Vérifications d'implémentation requises

Après synthèse, vérifier les INIT et les deux chaînes de synchronisation,
les entrées réellement raccordées à CLEAR, l'unicité du pilote de chaque
net et la conservation du reste des modules. Tester aussi la chaîne
assemblée avec les primitives Gowin, pas seulement le helper RTL.

Les SDC héritées bornent déjà les trajets clk50/AHB à 8 ns et retirent leur
exigence de hold entre domaines. Elles ne constituent pas, à elles seules,
une preuve de couverture des nouvelles entrées asynchrones. Il faut lire
les trajets de récupération/removal réellement rapportés et les trajets
entre étages. Aucune exception supplémentaire ne doit masquer un échec
pour obtenir artificiellement PASS.

La régression générale `20261027_r21r2_reset_qualification` passe ses
11 groupes, avec références Pro Dock préservées. Elle est distincte des
preuves spécifiques du snapshot et des futurs résultats physiques.
SHA-256 du résultat :
`b1892baa281b306d07afd273af4aa11b71959e5e037fd9446ffdc83525abc614`.

**En attente au moment de cette revue :** gel des preuves spécifiques,
revues contradictoires du paquet cohérent, assemblage, routage, audit
physique et essai sur Neo. La R19 demeure le bitstream de repli identifié.

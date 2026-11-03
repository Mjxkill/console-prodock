# Stockage commandes Neo : FF en banques, lecture one-hot

Candidat **hors application et hors carte**, fondé sur le contrat SDPB des deux
files commandes inventoriées dans `../mapping_01/CONTRACT.md`. L'objectif est
précis : réduire les fanouts des sept adresses du multiplexeur FF qui a donné
un candidat non routé. Ce n'est pas une correction démontrée de PR0004, ni une
conclusion sur la cause des rejets COPY matériels.

## Implémentation retenue

Source unique candidate : `banked_words32.v` (77 lignes). Top
`neo_command_ff128`, mêmes ports sans paramètres que le premier helper.
`neo_command_ff128.v` est **l'archive du premier essai vectoriel de cette tâche**,
conservée pour expliquer ses timeouts Icarus ; ce n'est pas une seconde source
courante. Le changement vers128wires32bits est réversible textuellement et ne
change ni index ni cellule de stockage. `qualify_helper.py` vérifie cette inverse.

- Capacité128×32, quatre validations d'octets et4096DFFRE de stockage conservés.
- Seize LUT4 décodent ADB[8:5] en one-hot ; huit LUT3 décodent ADB[11:9].
- Huit banques de16mots. Par bit, les mots sont combinés par paires
  `(d0 & select0) | (d1 & select1)` en LUT4, puis par réduction OR locale.
- Le même principe combine les huit sorties de banque. Les LUT primitives
  explicites évitent de demander au synthétiseur de reconstruire librement
  un multiplexeur binaire à partir d'une sélection variable.
- Les32DFFRE de sortie gardent **un front CLKB de latence** ; pas de pipeline
  supplémentaire. RESET synchrone et prioritaire sur CEB ne touche que DO.
  CLKA/CEA et tous les pointeurs, niveaux, protocoles, resets externes restent
  hors helper et inchangés.
- INIT=0 ; GSR inactif après configuration. Les adresses/control testés sont
  binaires. La collision lecture/écriture simultanée même adresse reste hors
  garantie physique UG300 ; le banc original l'exclut explicitement.

La division en banques est une structure logique, **pas un placement physique
imposé**. Aucun LOC, aucune région, aucune nouvelle contrainte n'est ajoutée.

## Mesures après synthèse du helper seul

GowinSynthesis V1.9.12.03, stage02 rc0, durée1,616s. Netlist retenue :
`stage_02/helper/neo_command_ff128.vg`, SHA256
`e5c576bdb1f439870279e1051ef790e16fcea9b107dc4df9375b4efb115de41f`.

| Par helper | Premier mux FF | Banques one-hot | Delta |
|---|---:|---:|---:|
| LUT totales |4113|3541|−572 (−13,9%)|
| LUT4 |3092|3206|+114|
| LUT3 |969|79|−890|
| LUT2 |52|256|+204|
| FF stockage+sortie |4128|4128|0|
| RAM |0|0|0|
| Profondeur maximale LUT combinatoire |6|6|0|

Pour deux instances, le delta logique est **−1144LUT**, FF inchangées. Ce calcul
ne donne pas l'occupation CLS après placement. **CLS, délais, congestion et
routabilité restent inconnus.** Aucune synthèse de l'application ni aucun PNR.

| Adresse | Fanout ancien (entrées primitives) | Nouveau |
|---|---:|---:|
| ADB[5] |1336|16|
| ADB[6] |881|16|
| ADB[7] |693|16|
| ADB[8] |64|16|
| ADB[9] |61|8|
| ADB[10] |83|8|
| ADB[11] |99|8|

Le gain ne supprime pas les réseaux distribués : chaque row_select pilote256
entrées, chaque DI128FF et CLKA4096FF. Le synthétiseur partage désormais une
validation d'écriture vers512entrées LUT. Cet effet secondaire de partage est
visible dans `COMPARISON.json` ; aucune amélioration générale de tous les
fanouts n'est revendiquée. Le timing du décodeur et de ses sélections décodées
reste à vérifier sur un éventuel placement.

## Vérifications effectuées

- Six scénarios RTL contre **le SDPB officiel Gowin intégral** et le scoreboard
  existant : horloges80/75MHz,125/124,9 et125/125,2MHz, phases différentes,
  fronts coïncidents, horloge commune, constantes exactes cmem ; tous PASS.
- Cinq mutations détectées : mauvais index, mauvaise donnée, reset mal
  conditionné par CE, reset qui efface le stockage, lecture retardée d'un cycle.
- Les mêmes six scénarios passent avec la **VG synthétisée inchangée**, sans
  bibliothèque simplifiée ni renommage de simulation supplémentaire.
-4096FF de stockage et32FF de sortie vérifiés individuellement : indices,
  Q/D, horloges, reset, INIT. Un GSR relié à VCC ; zéro primitive RAM.
- Le graphe LUT a une profondeur maximale6, pas de cycle dans la traversée.
  Ce contrôle n'est pas une analyse temporelle.

`QUALIFICATION.json` lie ces preuves au helper exact. Il ne qualifie pas une
netlist applicative assemblée : **aucun assemblage applicatif n'a été produit**.
`COMPARISON.json` contient les résultats détaillés sans masquer le fanout512.

## Incidents conservés

Le premier RTL utilisait un bus words[4095:0]. Deux scénarios Icarus ont atteint
90s avant résultat ; le runner a été interrompu explicitement (exit130), puis
le stockage a été déclaré comme128wires32bits. Un probe avec le même banc et
les mêmes primitives passe alors, suivi de la campagne complète. Cela établit
un effet de représentation sur cet outil ; ce n'est pas un défaut matériel ni
une preuve de la cause interne du simulateur.

Stage01 de synthèse a échoué avant analyse RTL : AF_NETLINK refusé et hostid
non disponible dans le bac à sable. Après autorisation, stage02 utilise les
mêmes sources/options hors du bac à sable et passe. Aucun changement de licence
ou contournement de ce contrôle. Les deux tentatives restent archivées.

## Décision suivante à la charge de root

Les objectifs mesurables helper sont satisfaits : sept fanouts d'adresse
fortement réduits, moins de LUT, même stockage, même latence et mêmes contrôles.
Cela justifie d'évaluer ce candidat, **pas d'affirmer qu'il routera**. Root peut
choisir d'intégrer ce seul helper dans une copie avec inversion exacte, puis
analyser le placement/routage. Les références Pro Dock et Neo, l'application,
les contraintes, le matériel et les autres travaux n'ont pas été modifiés ici.

# Témoin avant banque UTNA, 28 octobre 2026

**Candidat Neo hors carte préparé. Aucune correction matérielle revendiquée.**
Le défaut R19 observé (mot de version 0 au lieu de 1) reste FAIL. Le but de ce
candidat est de séparer une valeur déjà fausse à la sortie FIFO d'une valeur
masquée/altérée après sa présentation à la banque, sous les contrôles du
[contrat MMIO](CONTRACT.md).

Le dernier essai matériel analysé reste
`../utna_activity_analysis_01/capture_analysis.json`, dérivé de
`TESTS/neo_common_cause_20261027/utna_activity_prepared_01/activity_20261028_000942/result.json`.
Il prouve une activité des ticks et du compteur SOF, mais pas le bon transfert
du mot 1. Aucune lecture ou écriture sur carte n'a été faite dans ce chantier.

## Candidat et conservation

- Parent exact : `tang/impl/console_neo_n56r19_capture_ce_local`.
- Netlist parent : `dfac41d80eecaa0b6a3c152d36d8fcdb902060cecbd450647ede445d1c8004b6`.
- Bitstream parent : `1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`.
- Netlist préparé : [candidate_01/console_neo.vg](candidate_01/console_neo.vg),
  SHA `fa0185400736119ed68d6792656b6a80e328742acfa1deff7e7acdc02e4f24d1`.
- Transformation et audit : [prepare_candidate.py](prepare_candidate.py),
  [candidate_01/assembly.json](candidate_01/assembly.json).

Les modules d'origine restent identiques sauf le mux ajouté devant D des
32 registres de retour UTNA et l'instance passive du témoin. Tous les anciens
CLK, RESET, CE, Q et paramètres primitifs sont conservés. La transformation
inverse restitue le netlist R19 octet pour octet. Les sources communes et
le snapshot parent ne sont pas modifiés ; le helper est ajouté uniquement
à la copie Neo. Ni top, PLL, reset, DDR, USB datapath ni arbitre ne sont changés.

Le helper seul a été mappé par Yosys 0.69+286, déjà installé. Aucun lancement
Gowin, aucune synthèse du système entier, aucun placement/routage. Le dossier
ne contient aucun programme de chargement carte. Les noms des signaux HCLK
sont vérifiés dans le netlist parent, puis les connexions des bascules ajoutées
dans le JSON Yosys.

## Preuves locales

| Épreuve | Résultat |
|---|---|
| RTL et helper mappé, scoreboard indépendant | 12 013 cycles chacun, PASS |
| Débordement injecté des 6 compteurs, RTL et mappé | 12 cas, PASS |
| Ancien R19 et candidat en parallèle | 3 couples fréquence/phase × 3 modes, 9 cas PASS |
| Gardes de transformation, mux et réversibilité | 11 cas PASS |
| Suite locale complète des deux profils | 11 groupes PASS |
| Collecteur/décodeur hors carte, cas adverses | 85 cas PASS |

Les journaux et empreintes sont dans [helper_tests_02/result.json](helper_tests_02/result.json),
[integration_tests_02/result.json](integration_tests_02/result.json),
[guard_tests_01/result.json](guard_tests_01/result.json) et
`TESTS/dual_board/20261028_reply_witness_01/result.json`
(SHA `57594e246b0d6eaa499f886e54ce7cb719cf31f65d6cd310b22b4dc1e877bf20`).
La suite des profils protège les sources communes ; elle ne remplace pas
les essais spécifiques du snapshot candidat.

Le scoreboard vérifie reset prioritaire, toutes les adresses sur 256 offsets
dans les deux sens, captures complètes et partielles, tags, doublons, index
désordonnés, événements hors busy, 6 000 stimulations pseudo-aléatoires et
drapeaux persistants. Les débordements sont provoqués par force de compteur
explicite pour éviter quatre milliards de cycles ; aucune capture matérielle
n'est présentée comme équivalente à cette injection.

L'intégration utilise les primitives officielles Gowin. Le R19 original et
le candidat reçoivent exactement les mêmes entrées ; anciens retours MMIO et
contrôles de capture sont comparés. Toutes les lectures byte-offset sont
essayées, ainsi que les écritures de l'extension, qui ne changent aucun état.
L'horloge USB arrêtée, une commande en attente puis le reset/restart sont
également testés. Le helper reste sur HCLK.

Les trois modes donnent :

| Injection volontaire | Banque mot 1 | Témoin mot 1 |
|---|---:|---:|
| Aucune | 1 | 1 |
| Bit 0 de `reply` forcé à zéro uniquement au slot 1 | 0 | 0 |
| Résultat de validité lane 1 de banque forcé à zéro | 0 | 1 |

Pour chaque phase/rapport, les 160 mots des cinq captures sont comparés ;
seuls les cinq mots de version diffèrent entre le mode sain et chaque faute.
Les tags, compteurs, sentinelles et alias passent. Cela prouve la séparation
des **modèles injectés**, pas l'origine du défaut physique R19.

Deux premières compilations de banc ont échoué car le nom `total` est retenu
par Yosys sous l'alias aplati `r_total.q`. Les journaux restent dans
`helper_tests_01` et `integration_tests_01`. Les bancs ont été corrigés, sans
modifier le helper ni le candidat. `mapping_01` est une exploration avec ports
scalaires ; le candidat utilise uniquement `mapping_02` à ports vectoriels.

## Coût du témoin

Le mapping local ajoute exactement **402 DFFRE** : 96 bits de données,
96 bits de tags, 192 bits de compteurs et 18 bits de progression/drapeaux.
Il ne contient aucune mémoire, PLL ni nouvelle horloge.

Le helper comporte 493 LUT1..4, 119 mux de LUT larges et 197 cellules ALU.
L'intégration ajoute 32 LUT3, soit 525 LUT1..4 au total. Il s'agit de nombres
de primitives Yosys, **pas d'une occupation Gowin routée** : carry, packing
et mux dédiés ne doivent pas être sommés comme des LUT indépendantes pour
annoncer un pourcentage FPGA. Le timing et le routage restent à mesurer.

## Revue indépendante et limites

La revue DeepSeek porte sur [review_packet.txt](review_packet.txt), SHA
`b1f560228e32b30e0cce1c38545c45fb8ae207b20edbb3f2711d13596df37f24`.
La tentative dans le bac à sable a échoué avant tout avis (DNS) ; la seconde
tentative via le wrapper autorisé est terminée dans
`TESTS/assisted_reviews_20261026/neo_reply_witness_deepseek_r1_network`.
La [disposition contradictoire](DEEPSEEK_DISPOSITION.md) retient la précision
N≥1 et la vérification obligatoire de EC ; elle confronte les autres réserves
aux sources exactes. Aucun défaut logique démontré n'a imposé de changement
du candidat. Aucun correctif n'a été appliqué automatiquement.

Ces simulations sont fonctionnelles, sans SDF ni modèle de métastabilité.
La réception future du fichier par Gowin, son mapping final et son timing
ne sont pas qualifiés. Les taps et le mux augmentent la charge physique :
si le défaut disparaît lors du prochain routage, cela ne prouve pas sa cause.
La conclusion sur le GPU/USB global de la Neo reste distincte de cette anomalie
de diagnostic. Le retour matériel reste le bitstream R19 exact, conservé.

## Collecte et décodage hors carte : prêts

[offline_capture.py](offline_capture.py) lit uniquement des fichiers déjà
enregistrés. Le format `neo-utw1-offline-v1` contient contrôles avant/après
(`+00/+04/+08`) et deux images complètes (banque `+40..BC`, témoin `+C0..FC`),
dans cet ordre, soit 102 lectures. Les exemples complets, explicitement
synthétiques, sont dans [offline_tests_03](offline_tests_03).

```sh
# Exemple local valide ; dossier de sortie obligatoirement nouveau.
python3 TESTS/neo_common_cause_20261028/reply_witness_candidate_01/offline_capture.py \
  --capture TESTS/neo_common_cause_20261028/reply_witness_candidate_01/offline_tests_03/synthetic_valid.json \
  --out /tmp/utw_offline_example

# Construction du paquet depuis un journal JSONL déjà enregistré.
python3 TESTS/neo_common_cause_20261028/reply_witness_candidate_01/offline_capture.py \
  --jsonl TESTS/neo_common_cause_20261028/reply_witness_candidate_01/offline_tests_03/synthetic_reads.jsonl \
  --sequence 4 --command 2 --out /tmp/utw_offline_jsonl_example
```

Chaque ligne JSONL comporte exactement `phase`, `address`, `value`. Les
phases sont `before`, `image_a`, `image_b`, `after`. Les mots sont des entiers
32 bits ou des chaînes `0x` suivies de huit chiffres hexadécimaux. Les adresses
canoniques sont obligatoires ; miroirs, duplications, permutations, écritures,
captures partielles, clés JSON répétées et mots hors largeur sont refusés.

Pour un **futur** journal matériel, l'origine `hardware_capture` impose un
SHA du bitstream déclaré et un SHA attendu fourni séparément au décodeur.
Ce sont des déclarations du propriétaire de l'acquisition : le décodeur
n'atteste ni l'identité physique ni le chargement de la carte. Même un résultat
local valide conserve `hardware_qualified=false`. Une version0 reste FAIL et
sort avec le code 1 ; une capture incohérente n'est pas interprétée.

Les 85 cas de [offline_tests_03/result.json](offline_tests_03/result.json)
vérifient notamment les tags périmés, les alias divergents, les deux images
différentes, le cas EC=1 avec F0 normal et la limite d'un témoin lui-même faux.
Les premières versions `offline_tests_01/02` sont antérieures aux gardes JSON
strictes et à l'enregistrement de l'empreinte des octets invalides ; le résultat
final est `offline_tests_03`.

**État prêt :** candidat et décodeur hors carte disponibles pour revue root.
Licence, lecture du netlist par Gowin, P&R, timing et essais Neo restent en
attente. Aucune cause globale du FPGA n'est revendiquée.

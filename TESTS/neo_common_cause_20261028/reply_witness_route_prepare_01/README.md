# N56r22 UTW1 : préparation du routage depuis R19

**Prêt pour revue et lancement par root.** Cet agent n'a lancé ni Gowin,
ni outil carte. Le projet est `tang/impl/console_neo_n56r22_utw1` ; il reste
un diagnostic candidat, sans correction revendiquée du défaut R19.

Le netlist préparé est exactement le candidat UTW1 gelé :
`fa0185400736119ed68d6792656b6a80e328742acfa1deff7e7acdc02e4f24d1`.
Le snapshot complet est copié, les sources communes et références Pro Dock
restent intactes. Aucun helper n'est resynthétisé lors de cette préparation.

| Élément | SHA-256 |
|---|---|
| `preparation.json` | `62b1a2cbd261cc564d37b1895ea716587ac1627e0d5d68a55db72bbf01c36d1f` |
| Lanceur `launch_route.py` | `d2dd717b8ef6d09257e867d8bc46f0ca2bf52294ff5a1125a98a3ae0cf82ce48` |
| CST R19, identique | `6330c9dd971b9151c08bddcf8b7b6a529983bc25f1c03ab4193b0b6a224aeac1` |
| SDC R19, identique | `c8da535e839157a361e78b06b2f65b2912891f8e9dc48b02d5b315ae9f953113` |
| `gw_sh` installé, identique au lanceur R19 | `a387ae6cdf022748a243757b4aedd98c39d12e26e224d70620bb4d7896b49522` |

Le `build.tcl` est celui du R19, avec uniquement remplacement du chemin de
dossier. Même device PG484, place=3, route=2, replicate=0, clock_route_order=1,
mêmes sorties VO/SDF/STA. Il lit le `.vg` et exécute `run pnr`, sans synthèse.
**Routage complet** : la logique diffère du R19 ; aucun `inc_pnr`, `inc_place`
ni cache de placement du R19 ne sont utilisés ou présentés comme compatibles.

## Compatibilité du helper

`primitive_compatibility.json` dans le build compare la bibliothèque officielle
utilisée lors des simulations à `/home/michael/gowin/IDE/simlib/gw5a/prim_sim.v`
(installation V1.9.12.03 du projet). Les fichiers entiers diffèrent, mais les
12 modules utilisés par le helper sont **identiques octet pour octet** :
DFFRE, ALU, LUT1..4, MUX2_LUT5..8, VCC et GND. Les ports et paramètres de
chaque cellule Yosys sont vérifiés contre cette bibliothèque. Les 197 ALU
utilisent ALU_MODE=2. Les 402 DFFRE emploient HCLK et le hreset synchrone.

Le R19 emploie déjà tous ces types sauf LUT1, qui est défini dans la
bibliothèque actuelle. Les déclarations du helper et des trois nets ajoutés
sont placées avant leurs usages, contrairement au défaut de format connu sur
un précédent candidat. Aucune incompatibilité de bibliothèque n'a été
détectée. **L'acceptation par le lecteur netlist Gowin reste à constater** :
elle n'est pas remplacée par les simulations ni cet audit statique.

## Contraintes

Aucune nouvelle contrainte n'est ajoutée. Le témoin et le mux de lecture
utilisent le domaine HCLK existant, déjà contraint par `bus80_clk` à 12,5 ns.
Il n'y a ni nouvelle horloge, ni nouveau CDC, ni exception de timing à créer.
Les broches, PLL et contraintes DDR/USB/HDMI restent celles du R19.

Les nouveaux taps augmentent cependant la charge des sources HCLK, et le
mux ajoute un étage devant les registres hrdata. Il faut donc contrôler leur
setup/hold réel, leurs CE et leur RESET synchrones, ainsi que les chemins
originaux dont le fanout a changé. Une difficulté observée ne justifiera pas
de masquer ces chemins par une exception. Les rapports existants peuvent ne
pas lister tous les endpoints : absence de ligne ne signifie pas timing PASS.

## Commandes concrètes

La préparation a été exécutée avec :

```sh
python3 TESTS/neo_common_cause_20261028/reply_witness_route_prepare_01/prepare_route.py --prepare-only
```

Ce drapeau refuse un dossier déjà existant. Pour revérifier sans lancement :

```sh
python3 TESTS/neo_common_cause_20261028/reply_witness_route_prepare_01/prepare_route.py --check-only
```

Après sa revue, root fournit un fichier JSON avec `passed=true`,
`purpose="UTW1 full PNR"` et les trois champs `netlist_sha256`,
`preparation_sha256`, `launcher_sha256` correspondant aux valeurs ci-dessus.
Aucun fichier d'approbation root n'a été créé par cet agent.

```sh
python3 TESTS/neo_common_cause_20261028/reply_witness_route_prepare_01/launch_route.py \
  --review CHEMIN_REVUE_ROOT.json --check-only

# Exécuté exclusivement par root après sa revue et vérification de licence :
python3 TESTS/neo_common_cause_20261028/reply_witness_route_prepare_01/launch_route.py \
  --review CHEMIN_REVUE_ROOT.json
```

Le lanceur reprend `environment()` et les gardes du projet, revérifie les
SHA, ouvre un verrou propre au build et refuse toute réutilisation de log ou
`route_launch.json`. Il enregistre le PID, l'outil, la revue et les résultats.
Il n'accède à aucune carte et ne tue aucun autre processus. En cas
d'interruption du wrapper, root doit vérifier son PID enregistré avant toute
reprise ; le résultat n'est jamais promu automatiquement.

## Vérifications après routage

`postroute_expected.json` contient les cellules/ports/pins du helper Yosys
et les obligations de contrôle. Le lecteur ciblé est :

```sh
python3 TESTS/neo_common_cause_20261028/reply_witness_route_prepare_01/audit_postroute.py \
  --out TESTS/neo_common_cause_20261028/reply_witness_route_prepare_01/postroute_01
```

Il vérifie les 402 DFFRE, les types/paramètres et connexions de toutes les
cellules ajoutées, l'identité des pilotes de taps, les 32 LUT3 de lecture
(`INIT=CA`), les anciens CLK/CE/RESET/Q de hrdata, et l'absence de retour du
témoin vers l'état applicatif. Il résout les concaténations/ranges des sorties
SDPB.DO bit par bit, indispensables pour la provenance de `reply` du R19.
Une disparition, réécriture ou alias non prouvé reste un échec à analyser.

Il inventorie aussi les endpoints de 434 registres (402 nouveaux + 32 hrdata)
dans les rapports STA/SDF. Cet inventaire n'est **pas** une preuve complète
de timing : `full_setup_hold_coverage_proven` reste faux jusqu'à une revue
des chemins. Il faut aussi examiner le timing global et les deltas des
horloges, resets, DDR, USB et HDMI. L'audit ciblé n'autorise aucun chargement.

## Preuves locales

- `TESTS/dual_board/20261028_utw1_route_prepare_01/result.json` : 11 groupes
  PASS, SHA `4c3570937d6ddb6d5f1c20c9331985cfbc0d4ab342b126fd01c0bcc6490e9785`.
- `tests_03/result.json` : 20 contrôles PASS, sans Gowin. Gardes de revue,
  check-only sans lancement, graphe synthétique cohérent, puis mauvais
  CLK/RESET/CE/D/INIT, FF absent, mux erroné, RAM ajoutée et retour vers l'état
  applicatif tous rejetés. Un STA/SDF vide conserve les 434 endpoints incomplets.

Les essais de mise au point antérieurs ne sont pas des résultats FPGA :
`tests_01` avait bloqué aussi le `git ls-files` légitime du garde en simulant
Popen ; `tests_02` a révélé l'absence initiale d'expansion de SDPB.DO dans le
lecteur d'audit. Le banc et le lecteur ont été corrigés. Ni le netlist gelé,
ni le build préparé, ni le lanceur n'ont changé à cette occasion.

Qualification matérielle toujours absente ; l'anomalie version0 du R19 reste
FAIL. La restauration future reste le bitstream R19 exact, pas ce candidat.

# Contre-revue indépendante — raccord COPY → lecture CPU RB12

Relecture hors carte, sans modification de source ni accès matériel. Les
constats ne qualifient pas le FPGA, le contrôleur DDR ou une copie GPU réelle.

## Deux instructions seulement

Comparaison des binaires effectuée : les deux mesurent 588 octets. Seuls les mots
d'offset 384 et 388 changent, aux adresses 0xa0005180 et0xa0005184 :

- ancien `6b4d7e37 / b4de0e13` : chargement de 0x6b4d6b4d ;
- nouveau `fe028e13 / 007e4e33` : `addi t3,t0,-32`, puis `xor t3,t3,t2`.

Le calcul ne s'applique que pour les destinations 0x12000020..0x1200003c.
Il attend donc les huit mots source 0x12000000..0x1200001c, comme decode_copy.py.
Les sentinelles restent les mots seed 0..7 et 16..31. Tous les autres octets,
branches, adresses de journal et limites d'accès sont identiques.

## Contre-tests exécutés indépendamment

La construction du journal de décodeur est indépendante du modèle RV32 :
64 mots LE, RB12/version 1, phase 3/result 1, caches 0, ILM 0xa0000001, IRQ désactivées,
ID 0x424c5432, dernier accès 0x1200007c, 32 lectures, données attendues COPY.
Les compteurs GPU sont volontairement done 2/status 0/rejected 1 avant et après.

- 21 mutations de phase/résultat/compte/étendue/réservés/gardes/trap/ID/rapport
  d'erreur : toutes refusent readback_valid et restent unobserved.
- Quatre sentinelles altérées (indices 0, 7, 16, 31) avec métadonnées exactes :
  lecture valide, classification other_or_partial_change, gpu_passed=False.
  Pour chacune, falsifier ensuite le rapport d'erreur à zéro invalide la lecture.
- Cinq tailles de journal incorrectes (0,128,255,257,512) et les deux identités
  erronées sont rejetées par ValueError.
- Quatre associations de SHA absents/incorrects sont rejetées par decode_bound.
  La paire exacte est acceptée ; decode brut indique binding_checked=False.

Exécution indépendante des 588 octets dans Reader, avec remplacement du seul
stub d'état GPU par done 2/status 0/rejected 1 : copie exacte, seed inchangé,
partiel et sentinelle altérée effectuent 32 lectures ; trap au 8e mot donne 7 lectures,
et mauvais journal parent zéro lecture. Aucune commande GPU/écriture DDR et aucun
mot du journal parent modifié. Une transition pendant les lectures
(done 1→2, status 1→0, rejected 0→1) reste une observation valide, jamais GPU_PASS.

## Interprétation et provenance obligatoires

Le résultat CPU 1 signifie « 32 lectures achevées », pas «GPU terminé sans erreur».
Le précédent −5 n'est pas nécessairement un timeout : il peut suivre
check_gpu_errors après done 2/status 0/rejected 1. Le journal doit conserver ce
fait. Le décodeur relu retourne toujours gpu_passed=False, y compris quand les
32 mots correspondent à COPY. Une sentinelle corrompue peut donner une lecture
valide : cela signifie uniquement que l'observation et son rapport concordent.

Le header RB12/MD12 ne porte ni l'opération ni un nonce de nouvelle exécution.
Le contrôleur doit lier : bitstream exact, SHA firmware COPY parent, capture
MD12 exacte avant le lecteur, SHA des 588 octets du lecteur et capture RB12. Les SHA
passés à decode_bound sont déclarés par l'appelant ; ils ne sont pas une
attestation matérielle ni une preuve de fraîcheur. Conserver une preuve de
nouvelle exécution/initialisation ILM du journal pour éviter une ancienne capture
valide si le cœur ne repart pas. Ne pas ajouter d'écriture DDR pour cela.

Les 32 loads ne forment pas un instantané atomique : le GPU peut progresser et
les accès CPU peuvent modifier l'arbitrage. Capturer l'état GPU avant la lecture,
puis conserver l'avant/après. Cela ne sépare pas à lui seul FIFO, arbitre et DDR.

## Empreintes relues

Toutes les entrées ci-dessous sont restées identiques pendant la contre-épreuve
finale du décodeur/provenance. Le test RV32 précédent utilisait la même logique
de Reader avant ajout des nouveaux scénarios par son propriétaire ; son stub
GPU était remplacé localement, sans édition de source.

- `TESTS/neo_common_cause_20261028/execution_diagnostic_02/copy_readback_r1/decode.py` : `b03d14c413daad8f9ad4e07b05bdce74ed3f405d0347cc7c00d878a18509a36f`
- `TESTS/neo_common_cause_20261028/execution_diagnostic_02/copy_readback_r1/readback_model.py` : `b500d2a184d07815f83178c2519ce8c3c2fd8e83076213d5c71a96e558286826`
- `TESTS/neo_common_cause_20261028/execution_diagnostic_02/copy_readback_r1/readback.S` : `8cebee352a7cff3d67b005484a3b987e1c20a453148339552d959adaf88faca9`
- `TESTS/neo_common_cause_20261028/execution_diagnostic_02/copy_readback_r1/build_01/readback.bin` : `15dfe11fd3f11edd3330d835420562494a7d170f7a95b5e1b1c3d451462ae0d2`
- `TESTS/neo_common_cause_20261028/execution_diagnostic_02/readback_r1/decode.py` : `5eeba4bc283e75bce035157f54a7f8bc1388ce6abfb26af7710abdff45ae2edf`
- `TESTS/neo_common_cause_20261028/execution_diagnostic_02/readback_r1/readback_model.py` : `3ac26b16e4c577aa2df4a8568beb4e98bf293eed10d40dce6cf7d6849f1620c9`
- `TESTS/neo_common_cause_20261028/execution_diagnostic_02/readback_r1/build_01/readback.bin` : `aa2a1a061c87de6cc47a567a217b6d4078df1d3c982242bfe2275ef7bcc50503`
- `TESTS/neo_common_cause_20261028/execution_diagnostic_02/copy_probe_01/firmware_delivery_01/decode_copy.py` : `e211bb0e75d02121275db789ea4ab35aef45867db19fb7d565afd3bc5e536d7b`
- `TESTS/neo_common_cause_20261028/execution_diagnostic_02/copy_probe_01/firmware_delivery_01/build_01/microdma.bin` : `4d3b91ee5fd7aae44abd7d55ab712c24f78167ec1ac318f7a9a21aea000a8684`

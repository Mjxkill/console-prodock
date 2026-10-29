# N56r3 : expérience ciblée sur la capture du matériau

Préparation locale du 21 octobre 2026. Aucun compilateur ni accès matériel lancé
pendant cette préparation. La tâche principale possède les deux cartes.

## Hypothèse testée

La tâche principale a isolé sur N56r1 une séquence mesh de onze commandes. Les
commandes 0 à 9 sont acceptées ; l'opcode matériau 25 apparaît correctement dans
les en-têtes géométrie et pixel (`0x19000000`). La commande DRAW, index 10,
génère ensuite neuf sommets et un triangle, mais deux rejets internes et un
dernier en-tête pixel nul. Le chemin `MAT_SEND`/`RESTORE` réutilise le registre
`material`, ce qui rend sa capture suspecte. Ce constat ne prouve pas à lui seul
que son contrôle de capture est la cause.

Dans le routage N56r1, le signal `u_accel/u_v1/n56864_3` est explicitement classé
LW. Son pilote est `u_accel/u_v1/n56864_s0`, LUT3 INIT `8'h80` : AND des trois
entrées `gpu_debug_state[46]`, `state[67]` et `n56864_4`. Les noms d'alias et les
connexions exactes sont conservés séparément pour les netlists synthèse/routage.

Le signal possède **253 charges, toutes des broches CE de DFFRE `material_*`**,
et aucune entrée d'horloge. Les bits 29, 30, 31 n'ont pas de bascule distincte
dans ce groupe synthétisé ; aucun autre registre ne figure parmi les charges.
Le nom du pilote, le type LUT3, INIT, ses quatre broches et le jeu complet des
253 charges sont vérifiés dans les deux netlists.

## Seul changement proposé

Parent : `tang/impl/console_neo_n56r1`, pas N56r2. La seule ligne ajoutée est :

```text
CLOCK_LOC "u_accel/u_v1/n56864_3" LOCAL_CLOCK;
```

Le netlist reste exactement
`c05e9b7a4bcafba8cd31e4b985b4ba37ace8ecbd0e4b999745ac60d7a5fb461d`.
Le SDC, les RTL, la DDR 5.9/300 MHz, les fréquences, les broches et les options
de placement/routage restent identiques à N56r1. Ses trois `LOCAL_CLOCK`
existants sont conservés. **Aucun des quatre INS_LOC de N56r2 n'est ajouté.**

Gowin recalculera placement et routage ; les équations logiques restent les
mêmes, mais le changement physique ne se limite pas nécessairement au seul fil.
Les contrôles de near/viewport et de faces encore classés LW restent hors du
périmètre de cet essai.

## Preuves et garde

- `constraints.diff` : ajout unique au CST.
- `material_proof.json` : pilote, INIT, broches et toutes les charges des deux
  netlists ; ligne LW du rapport parent.
- `manifest.json` : empreintes du parent, script, compilateur, SDC, sources,
  preuves et garde commune aux deux cartes.

La préparation a passé l'audit DDR et `before_build('neo', candidate=True)`.
Une relecture indépendante a confirmé les empreintes et les entrées courantes.
Le constructeur réutilise uniquement les contrôles de lecture du parent N56r1
de `build_timing_placement.py` ; il n'appelle jamais sa préparation/construction
N56r2. Son code de construction est propre à cette expérience.

Manifeste SHA-256 :
`02de071c5f52c4d9a91e04b53aa619bc59442e64b287f615112cf8d51fe86b4f`.

Commande proposée après revue, **non lancée** :

```sh
python3 TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/build_material_control.py --build-reviewed 02de071c5f52c4d9a91e04b53aa619bc59442e64b287f615112cf8d51fe86b4f
```

## Critères après routage

Vérifier à nouveau les quatre contrôles locaux : pilotes, INIT, connexions,
charges et absence du tableau de ressources globales. Vérifier l'identité du
netlist/SDC/profil DDR et le diff unique CST. Exécuter la qualification complète
setup/hold/recovery/removal et les audits structurels ; aucun résultat temporel
n'est présumé pour cette variante.

Si un essai matériel est ensuite autorisé, comparer d'abord exactement la même
séquence mesh et les trois mêmes fenêtres mémoire que sur N56r1 : absence des
deux rejets, en-tête restauré, compteurs et pixels/Z. Une amélioration de la
seule séquence ne qualifierait ni tous les modes 3D ni les autres contrôles LW.

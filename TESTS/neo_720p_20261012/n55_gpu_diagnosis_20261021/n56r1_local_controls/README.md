# Expérience N56r1 : trois commandes sur routage local

Cette variante n'est pas une correction fonctionnelle déjà validée. Elle vise
à tester une hypothèse physique issue de l'observation N56 : opcode correct
au blitter, en-tête géométrique nul, et `mem_up[1]` restant nul alors que son
entrée `mem_up[0]` est observée à un.

Trois réseaux non horloge utilisent LW dans N56. La preuve de leurs pilotes,
charges et initialisations dans les netlists `.vg` et `.vo` est conservée dans
`control_proof.json` :

| Réseau | Fonction | Charges pertinentes |
|---|---|---|
| `u_accel/u_v1/n56220_6` | AND des quatre conditions de capture | CE des 256 bits `captured_command` et de 56 bits des fins de mesh |
| `u_gpu_debug/n2835_5` | XOR `req_s[1]`, `ack` | CE de l'ACK et des 282 bits non constants de la capture debug |
| `u_gpu_debug/mem_up[1]` | second étage DFFCE de mise en route | reset/prêt du domaine debug, observé à zéro dans N56 |

`constraints.diff` contient seulement trois ajouts `CLOCK_LOC ... LOCAL_CLOCK`.
Le netlist, RTL, DDR, SDC, fréquences, broches et tous les `INS_LOC` sont ceux de
N56. Aucun placement destiné aux 22 endpoints négatifs de N56 n'est mélangé à
cette expérience. Le script local `../build_local_controls.py` vérifie les
copies, les fonctions nommées, la garde commune et les 21 fichiers DDR, puis
effectue exclusivement `run pnr`. Il ne programme aucune carte.

Après compilation, il faudra vérifier l'application réelle des trois
contraintes dans les rapports, le maintien des équations des pilotes et
charges, et la qualification temporelle complète. Une amélioration sur carte
localiserait une dépendance à cette configuration de routage, sans prouver à
elle seule un erratum silicium ni distinguer les trois réseaux. Les autres
fonctionnalités GPU ne seraient pas qualifiées par les configurations seules.

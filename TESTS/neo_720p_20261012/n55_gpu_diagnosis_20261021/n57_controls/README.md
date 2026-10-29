# Résolution des contrôles GPU après synthèse USB N57

La synthèse N57 remplace uniquement les deux IP USB générées officiellement
pour la cible Neo. La résolution ci-dessous est une préparation de contraintes,
pas une qualification de placement/routage ni un essai matériel.

- Référence : `tang/impl/console_neo_n56r3/console_neo.vg`.
- Candidat : `tang/impl/console_neo_n57_usb35_syn/impl/gwsynthesis/console_neo.vg`.
- Netlist N57 : `51ed167a714c8c3a3ef5f7a918a850ff4c4163b46c3d9f88b43a96db3b6cd190`.
- Résolution et provenance complètes : `resolution.json` (PASS).
- Fragment proposé, non appliqué : `proposed_controls.cst`.

| Fonction | Net proposé | Charges directes |
|---|---|---:|
| Capture commande | `u_accel/u_v1/n56220_6` | 312 |
| Capture mémoire observateur | `u_gpu_debug/n2835_5` | 283 |
| Domaine mémoire actif | `u_gpu_debug/mem_up[1]` | 2 |
| Matériau | `u_accel/u_v1/n56864_3` | 256 |
| Caméra | `u_accel/u_v1/n57378_3` | 204 |
| Face | `u_accel/u_v1/n59467_5` | 246 |
| Capture bus observateur | `u_gpu_debug/n4022_5` | 315 |
| Requête pixels en attente | `v1_pending` | 8 |
| Inverse attente pixels | `u_accel/v1_tx_addr_27_12` | 317 |

Les charges vectorielles CE des DSP sont comptées bit par bit. `v1_pending`
a quatre charges locales dans l'accélérateur et quatre dans l'arbitre DDR.
Aucun de ces neuf nets ne pilote de broche d'horloge. Les pilotes, ensembles
complets de charges et cônes combinatoires sélectionnés sont identiques entre
les deux synthèses. Les cônes s'arrêtent aux frontières séquentielles ou entrées
de module nommées ; ce contrôle ne constitue pas une équivalence formelle de
toute la console.

Le reset4 possède déjà `CLOCK_LOC "gpu_debug_state[48]" LOCAL_CLOCK;` dans le
CST N57 ; le fragment ne duplique pas cette ligne. Le pilote est
`u_accel/engine_resetn_4_s0`, son alias interne est
`u_accel/gpu_debug_state_48` et son alias au niveau supérieur est
`gpu_debug_state[48]`. Les deux synthèses ont huit charges directes identiques.
Le netlist routé R3 en a neuf après décomposition d'une cellule par le routeur.
R3 montre aussi qu'une contrainte LOCAL_CLOCK présente dans le fichier ne suffit
pas à prouver son respect physique : le rapport de ressources et le netlist
routé doivent être contrôlés à nouveau.

`gpu_accel` et `neo_gpu_debug` sont strictement identiques dans les deux
netlists de synthèse. Pour `gpu_geometry`, `geometry_rename_proof.json` (PASS)
et `geometry_renames.diff` montrent que quatre renommages explicites de cellules
et nets ALU suffisent à rendre les modules entiers strictement identiques.
Aucune autre substitution n'a été faite ; aucun de ces noms n'est cité dans le
CST, le SDC ou le fragment proposé. Cette comparaison ne couvre pas les IP USB
modifiées et ne prédit pas le résultat matériel du nouveau routage.

La revue du constructeur USB est consignée à côté de ce dossier dans
`n57_builder_review.json` : deux changements de sources exacts, Tcl limité à
`run syn`, et copies des trois fichiers ROM/font externes au manifeste source
revérifiées après synthèse. Aucun placement/routage n'a été lancé par cette
résolution et aucun accès aux cartes n'a été effectué.

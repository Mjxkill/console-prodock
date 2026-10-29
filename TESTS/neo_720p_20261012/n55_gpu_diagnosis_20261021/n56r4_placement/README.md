# N56r4 proposé : observation CDC et distribution du reset pixel

Préparation uniquement, sans compilation ni accès matériel. Parent exact :
`console_neo_n56r3`, bitstream
`77a76cdc6d16aaa34a939296cc74ed7f6e29980682ac2756b6b2658ae443fbe2`.
Le constructeur conserve ce parent intact, réutilise sa netlist de synthèse
et n'ajoute que sept `INS_LOC` à une copie de son CST.

Manifeste à revoir : `manifest.json`, SHA-256
`5c5673a0be74918f523bfc5aaa7745231347a04ebddb3df6d15bc03c27534323`.

## Deux chemins CDC mesurés

| Paires déplacées ensemble | Source observée et emplacement N56r3 | Région proposée |
| --- | --- | --- |
| `observe_words_s1/s2[57]` | Pixel packet25 à R39C41[3][B] | R35..45 / C38..48 |
| `observe_words_s1/s2[49]` | Pixel packet17 à R51C41[0][B] | R47..55 / C38..48 |

Les premiers étages sont actuellement respectivement à R43C143 et R50C136.
Ce sont les seuls endpoints setup négatifs du rapport : −0,453 et −0,278 ns
sous la borne CDC de 8 ns. Chaque s1 ne pilote que son s2 ; chaque s2 pilote
un cône combinatoire aboutissant à une seule entrée séquentielle MMIO.
Les deux étages sont rapprochés ensemble pour conserver un trajet court
entre synchroniseurs. Le chemin vers la réponse MMIO devra aussi être revérifié.

Les positions actuelles des s2 ne sont pas publiées dans les chemins du
rapport. Les contraintes sont régionales et laissent plusieurs centaines
de sites possibles ; elles n'affirment pas à l'avance une fermeture temporelle.

## Reset4 : ce que les preuves permettent de dire

`engine_resetn[4]` a pour alias routé `gpu_debug_state[48]` et fournit le
reset de `u_v1/u_pixels`. Son driver DFFCE est à **R22C52[2][B] dans N56r1
comme dans N56r3**. Il passe pourtant d'une distribution locale à LW dans
N56r3. La présence d'un `LOCAL_CLOCK` sur ce nom exact ne prouve donc pas
son application physique.

Le guide local Gowin SUG1018-1.7E §2.7 p15 décrit `LOCAL_CLOCK` comme une
contrainte de distribution locale sans `signal_type`. Le journal N56r3 ne
signale pas un net inexistant. L'origine précise de la promotion malgré cette
contrainte n'est pas établie ; aucun changement de syntaxe conjectural ni
aucune suppression de l'audit n'est introduit.

Le net a neuf charges directes : sept LUT du moteur pixel, une inversion,
et `u_gpu_debug/held_48_s0/D`. En suivant les LUT/inversions jusqu'aux
premières frontières séquentielles, il atteint **3207 pins** : 3134 RESET,
38 SET, 17 CE et 18 D. Le témoin ne représente donc qu'une petite partie
de la distribution effective.

Le chemin d'observation du reset est `held_48_s0` → `snapshot_48_s0`.
Il s'agit de données maintenues pendant une poignée de main entre domaines,
**pas** des deux étages `observe_words_s1/s2[48]` : ces derniers observent
packet16 et ne sont pas déplacés. Les positions held48/snapshot48 ne sont
pas publiées ; on ne peut pas affirmer qu'un témoin éloigné cause la promotion.

La proposition borne le driver reset4 et ces deux registres d'observation
à **R18..30 / C45..60**, région contenant le site actuel du driver. Elle
réduit la dispersion possible de cette branche et laisse le driver dans
sa région initiale. C'est une expérience de placement qui **ne garantit pas**
la disparition du LW, surtout compte tenu des milliers de charges fonctionnelles.

## Preuves et invariants

`placement_proof.json` résout les sept instances dans la netlist hiérarchique
de synthèse et dans celle après PnR. Il vérifie type et INIT, conserve les pins,
les charges, les cônes séquentiels, les chemins négatifs complets et indique
explicitement les positions inconnues. Les deux endpoints négatifs sont couverts.

`constraints.diff` contient seulement les sept ajouts. Aucun RTL, netlist,
SDC, période, pinout, DDR, fichier d'initialisation ni quatre `LOCAL_CLOCK`
issus de N56r1/r3 n'est changé. La garde commune aux deux cartes passe lors
de la préparation et sera réexécutée au lancement. Le constructeur refuse
toute dérive du parent, de ses audits ou du manifeste relu.

Après revue seulement :

```sh
python3 TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/build_observer_placement.py --build-reviewed 5c5673a0be74918f523bfc5aaa7745231347a04ebddb3df6d15bc03c27534323
```

Après compilation, vérifier les sept placements appliqués, les quatre
contrôles locaux et **l'intégralité** des ressources globales, tous les audits
DDR/GPU et setup/hold/recovery/removal. Un échec de routage du reset reste
un échec structurel distinct d'une violation setup ; aucune dérogation n'est
ajoutée ici. Les autres CE géométriques LW viewport/near-Z et face restent
hors de cette expérience. Aucun chargement ni démarrage Linux n'est effectué
par ce constructeur.

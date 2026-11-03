# Comparaison PR0004 — vérification indépendante, sans nouveau routage

Les deux versions en bascules échouent au routage. La version bancaire économise
des ressources et abaisse le total de connexions non routées, mais les rapports
ne permettent pas d'identifier ces connexions. Cela ne localise donc ni la
congestion ni le défaut fonctionnel COPY observé sur la référence REJECT R1.

| Mesure du rapport PNR | REJECT R1 | FF multiplexeur | FF bancaire |
|---|---:|---:|---:|
| État du routage | terminé | PR0004 | PR0004 |
| Connexions non routées annoncées | aucune erreur PR0004 | 6 960 | 4 243 |
| LUT | 65 832 | 74 058 | 72 914 |
| Registres / 139 095 | 56 305 | 64 561 | 64 561 |
| CLS / 69 120 | 59 413 | 62 006 | 61 717 |
| CLS, pourcentage calculé | 85,96 % | 89,71 % | 89,29 % |
| BSRAM / 340 | 263 | 259 | 259 |
| PRIMARY / 8 | 8 | 8 | 8 |
| LW / 8 | 7 | 7 | 7 |

Les chiffres LUT et registres décrivent des ressources différentes des CLS :
les pourcentages ne s'additionnent pas. La réduction bancaire est de 1 144 LUT,
289 CLS et 2 717 connexions non routées. Cette dernière différence n'est pas le
décompte des mêmes réseaux réparés : aucun appariement des réseaux n'est fourni.
Les 7 403 CLS restant arithmétiquement libres ne prouvent pas que les canaux
de routage nécessaires soient disponibles à l'endroit voulu.

## Preuves et limites d'observation

`NATIVE_CHECKS.json` vérifie 46 empreintes de sources/artefacts et leurs copies.
`project/inputs/HOST_INVENTORY.json` contient l'inventaire logique extrait des VO
complets, lié à leurs empreintes. Le modèle délégué reçoit cet inventaire dérivé
et les rapports textuels complets, pas les grandes netlists.

- Dans chaque version FF, les deux mémoires contiennent chacune 4 128 DFFRE.
  Chaque helper bancaire contient 3 541 LUT, contre 4 113 précédemment.
- `u_commands` conserve 4 096 FF sur `vid_hclk`, 32 sur `gpu_clk`, le reset
  de sortie `u_accel/n249_5` et aucun reset des cellules de stockage.
  `cmem` conserve 4 128 FF sur `gpu_clk`, reset à GND. Les nombres de broches
  CE et de réseaux CE restent identiques. Ce contrôle ne mesure aucun délai.
- Les quatre journaux/rapports pertinents de chaque échec ne donnent que
  « total 4243/6960 unrouted nets ». Les VO n'ont aucune annotation de réseau
  non routé, LOC/RLOC/BEL ou carte de congestion. Le `.p` est protégé fournisseur
  et le `.db` binaire ; ils n'ont pas été décodés.
- Le candidat bancaire n'a ni FS, ni SDF, ni rapport de timing TR. Aucune
  qualification temporelle n'en découle. Le routage achevé de REJECT R1 ne
  signifie pas que son timing soit fermé : ses violations documentées subsistent.

## Contraintes et charge de distribution

Les CST/SDC sont identiques octet par octet pour les trois variantes. Le TCL
ne diffère que par les trois chemins d'entrée. Aucun seed ni réglage de
placement/routage n'a changé ; `replicate_resources` reste à 0.

Le CST conserve 27 contraintes `INS_LOC` autour de `u_blitter`, dont
`cmem_s3`, `fill`, `wp` et des compteurs, dans `R[1:25]C[140:175]`
(lignes 379–405). Il n'existe pas de contrainte `INS_LOC` interne `u_commands`.
Ces ancrages ne placent pas explicitement les milliers de nouveaux FF. Leur
effet réel sur la distance des connexions reste inconnu sans carte de placement.

La preuve de synthèse antérieure réduit les charges logiques d'ADB[5:7] de
1 336/881/693 à 16 chacune. Elle conserve néanmoins des distributions communes :
sélections de ligne à 256 entrées, un enable partagé à 512 entrées, chaque DI
à 128 FF, et CLKA à 4 096 FF. Ce sont des nombres de broches logiques, pas des
capacités électriques, des délais ou la liste des réseaux que Gowin n'a pas routés.

## Expérience proposée, non exécutée

Une seule mémoire en FF bancaire à la fois réduit la charge ajoutée sans
changer sa profondeur ni ses cycles. Conserver REJECT R1 comme base et remplacer
uniquement `u_blitter/cmem` en premier est informatif : l'observation matérielle
`received=32,last_word=1` prouve que la première FIFO a transmis ce dernier mot.
Elle ne prouve pas les autres mots ni l'intégrité de la seconde mémoire.

Conserver strictement pointeurs, profondeur 128×32, CE/reset/horloges, latence
de lecture, graphe applicatif extérieur, instrumentation et contraintes.
Contrôler l'inversion textuelle de la substitution et l'inventaire d'une seule
mémoire remplacée. Les cellules de helper attendues sont 4 128 FF et 3 541 LUT ;
ne pas prédire un nombre exact de CLS après placement.

1. Si ce candidat route, analyser son timing avant toute comparaison fonctionnelle.
   Rejouer ensuite exactement les mots et témoins utilisés sur REJECT R1, avec
   limites exploratoires explicites si nécessaire. Un meilleur routage ne prouve
   pas que `cmem` causait le rejet COPY ; une réussite COPY seule reste aussi
   sensible au nouveau placement de l'application.
2. Si la première expérience ne départage pas les hypothèses, proposer ensuite
   `u_commands` seul en FF, toujours depuis la même référence. Deux essais
   individuels routables et le double échec renforceraient l'hypothèse d'une charge
   combinée, sans localiser une connexion fautive ni démontrer un erratum RAM.

Ces variantes ne sont ni construites ni lancées ici. Le choix appartient au
responsable du projet après cette revue ; aucun changement de seed ou de source
commune n'est proposé comme remède inexpliqué.

# R12 : refus du nom TCK GAO dans le CST principal

R12 reste **ROUTING_FAILED**, sans nouveau placement ni bitstream. Son
[journal](../../../../tang/impl/console_neo_n56r12_gao_tck_bufg/build.log)
signale CT1135 sur `control0[0]` après lecture de `gao.v`. Ce refus ne mesure
ni une allocation BUFG, ni une correction des treize violations hold R10.
R11 avait échoué sur le type BUFS non pris en charge ; les deux refus sont
distincts.

Le [manifeste de cette lecture](evidence.json) épingle les entrées et les
extraits du moteur installé. Aucun exécutable Gowin, placement, routage,
accès carte ou déchiffrement d’IP n’a été exécuté pour cette analyse.

## Noms effectivement générés

- Le wrapper avant synthèse relie `u_gw_jtag.tck_o` à `gao_jtag_tck`.
- Le [wrapper public de gao.v](gw_gao_wrapper.v.txt) consommé par le PNR
  déclare `wire [0:0] control0` et relie `tck_o` à `control0[0]`.
  Cette liaison alimente `u_icon_top.control0` et `u_la0_top.control0_1`.
- `constraint_mapping.json` concerne les contrôles applicatifs : aucune
  entrée `control0`, `gw_gao`, `tck_pad` ou `u_gw_jtag`.
- Le rapport temporel R10 montre la branche `u_gw_jtag/tck_o` à 250 charges.
  Un nom de broche dans le rapport ne constitue pas un nom de net CST.

Il n’existe donc pas de preuve pour remplacer la contrainte par un alias
`control0`, `gao_jtag_tck` ou `gw_gao/control0[0]` dans le CST applicatif.

## Deux espaces de contraintes dans le moteur

La lecture statique de `libgowin.so` montre le mécanisme suivant :

1. [NETLIST::readConstraints](readConstraints.asm), adresse `0x6c1390`,
   utilise le design au décalage `globalMem+0x0`, construit sa table de
   noms, puis appelle `readPhyConstraints` pour le CST principal. Il appelle
   `readGaoPhyConstraints` seulement si les étapes précédentes ont réussi.
2. [NETLIST::readGaoPhyConstraints](readGaoPhyConstraints.asm), adresse
   `0x6b93d0`, vérifie `getGaoCstFlag`, récupère `getGaoCstFile`, et construit
   la table de noms du design **distinct** à `globalMem+0x8`.
3. [readGaoCstFile](readGaoCstFile.asm), adresse `0x7321f0`, initialise le
   lecteur avec ce design GAO puis appelle le parseur CST. Le moteur
   contient l’option littérale `-gao_cst`.
4. [Cstreader::init](Cstreader_init.asm) mémorise le design fourni dans
   `Cstreader+0x28`. La [résolution de CLOCK_LOC](addNetClk_lookup.asm)
   appelle `Design::getObjByNet` sur ce pointeur.

Cela explique pourquoi une liaison présente dans la netlist GAO échoue
dans le CST du design principal. La déclaration vectorielle `[0:0]`
n’est pas une preuve d’erreur de nom ou de scalarisation.

## Expérience proposée, non exécutée

Le test fondé sur ces preuves conserverait **le CST R10 exact**, et
fournirait au moteur un fichier séparé par :

```text
-gao_cst <chemin-absolu/startup_clock.cst>
```

Ce fichier contiendrait uniquement :

```text
CLOCK_LOC "control0[0]" BUFG = CLK;
```

Ce n’est pas encore une recette de build validée : l’acceptation de
`CLOCK_LOC` dans ce lecteur, la résolution de ce net et l’exposition de
`-gao_cst` par le frontend `gw_sh` restent à vérifier. SUG1220 documente
`set_option -h` mais ne documente pas `set_option -gao_cst`. Le tableau
d’options du frontend inspecté ne contient pas cette chaîne ; il ne faut
pas inventer cette syntaxe ou modifier `cmd.do` en espérant que `run pnr`
la conserve. La présence de l’argument dans la bibliothèque ne prouve
pas qu’un lanceur public le transmet.

Une introspection sans compilation peut commencer avec
[inspect_frontend_options.tcl](inspect_frontend_options.tcl), lancé par
`gw_sh` dans un **dossier de recherche neuf**, avec l’environnement
`tools/gowin_toolchain.py`, sous le contrôle de root. Ce script ne charge
aucune entrée de build et n’appelle aucun `run`.

```text
/home/michael/gowin/IDE/bin/gw_sh /home/michael/console/TESTS/neo_720p_20261012/reload_r1_cold_20261022/gao_cst_namespace/inspect_frontend_options.tcl
```

Les commandes exactes `nm` et `objdump` permettant de reproduire les
preuves statiques sont dans `evidence.json`. Aucun nouvel essai de PNR
n’est autorisé par cette note. Un éventuel candidat doit garder
`-cst_error`, tous les audits, les huit PRIMARY applicatifs, le SDC et les
preuves FAIL R10–R12 ; il devra prouver la distribution physique obtenue
et son timing, sans résultat anticipé.

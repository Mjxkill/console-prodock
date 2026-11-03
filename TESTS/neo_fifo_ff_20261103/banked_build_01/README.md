# Préparation Neo — deux mémoires commandes FF en banques

Candidat assemblé depuis la netlist REJECT R1 uniquement. Source applicative
VG de départ : SHA76d56bd49776d12919c8051f5460bb5e7cadf73fb388ac2bd2cddea63c63b255.
Helper bancaire qualifié : SHAe5c576bdb1f439870279e1051ef790e16fcea9b107dc4df9375b4efb115de41f.
Assembly : SHA9026b77de01114a52fb87edc459a48417c4eb570c4ec0945025e18a44f9f7524.

`assemble.py` importe la transformation figée du premier essai FF. Seules les
cellules SDPB `ddr_dcfifo_3.\g_inferred_storage.mem_g_inferred_storage.mem_0_0_s`
et `blitter.cmem_cmem_0_0_s` deviennent `neo_command_ff128`. Leurs douze lignes
defparam sont retirées ; aucun port ni connexion ne change. Un seul module
helper est ajouté, instancié deux fois. Les autres mémoires restent intactes.

Preuves : inverse exacte des deux modules et de toute l'application ;153modules
applicatifs,151 byte-identiques ;0connexion modifiée ; helperidentique à la VG
ayant passé6scénarios mappés officiels. Les190INS_LOC sont conservées et aucune
ne cible les primitives remplacées. CST/SDC REJECT R1 sont identiques à ceux
S400 réutilisés par le moteur historique. Les options de routage sont égales,
sauf les trois chemins d'entrée relocalisés. Il n'y a ni seed changé, ni
réplication ajoutée, ni nouveau placement imposé.

L'ancien constructeur reste l'unique implémentation de substitution ; le moteur
`route_variant.py`/`route_d128.py` reste l'unique flot prepare/check/run. Les
scripts de ce dossier ne dupliquent ni synthèse ni routage. Aucune synthèse
applicative n'est effectuée. Aucun chargement de carte n'existe dans ce paquet.

La qualification `QUALIFICATION.json` associe l'intégrité de l'assemblage aux
preuves du helper. Elle ne prétend pas avoir simulé l'application complète et
ne constitue pas une qualification STA. Le contrôle à blanc `dry_run.py`
vérifie les gardes et le TCL sans créer le dossier `tang/impl` du candidat.

Après revue de root uniquement :

```
python3 TESTS/neo_fifo_ff_20261103/banked_build_01/route.py prepare
python3 TESTS/neo_fifo_ff_20261103/banked_build_01/route.py check
python3 TESTS/neo_fifo_ff_20261103/banked_build_01/route.py run --root-reviewed-single-pnr
```

Sortie attendue : `tang/impl/console_neo_fifo_banked_20261103_r1`. Le moteur
figé écrit encore le label historique D128_COPY_DMA ; `CANDIDATE.json` donne
l'identité correcte de l'expérience FF bancaire. La machine de lancement
conserve sa garde anti-double-exécution et son verrou ; aucune relance
automatique n'est autorisée.

Le choix de stockage FF est demandé par Michael. Le nouveau helper réduit les
fanouts des adresses brutes et économise1144LUT pour deux instances, mais les
sélections décodées et la validation d'écriture ont encore des charges élevées.
La réussite du routage reste inconnue et aucune cause de PR0004 ou des rejets
COPY n'est déclarée résolue. Pro Dock, sources communes et références inchangées.

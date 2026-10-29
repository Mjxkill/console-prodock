# COPY vide à base source identique à la destination

Préparation hors carte demandée après `root_sequence_run_01`. Aucun matériel,
contrôleur ou RTL de production modifié. Root conserve le chargement et les
verrous ; aucun nouveau bitstream n’est nécessaire.

Le firmware dérive **exactement** de `../copy_empty_01/build_01/microdma.bin`
MD12/928B, SHA `0e9b249f…`. Il ne dérive pas du préfixe MD13/CLEAR0.
Une seule valeur de paquet change : COPY w1 passe de `12000000` à `12000020`.
Au niveau binaire, **seul l’octet900 passe de00 à20**. Les instructions,
TARGET et les sept autres mots COPY sont identiques.

Binaire : `build_01/microdma.bin`, **928B**, SHA256
`39484a6b2068dc48f176b3c397eee2551801cbda86936a5d0b38532a208f0663`.

Paquet COPY :
`1d000000 12000020 00100001 00000020 00000000 00000000 00000000 00000000`.

## Contrat matériel conservé

- Entrée ILM4000, adresse complète `a0004000`, fin exclusive `a00043a0`.
  Code sous5000 ; aucune pile ; retour ROM80000000.
- Journal512B `a0006000`, remis à zéro, identitéMD12/version1.
- Scratch128B `[12000000,12000080)`, seed32CPUstores. Trois comparaisons
  de32CPUloads attendues si toutes les étapes réussissent.
- TARGET16×1 : couleur12000020, Z12000040, strides32. Source COPY16×1
  à12000020, stride32 identique, étendue demandée **0×0**.
- Gardes inchangées : caches0, MILMB=a0000001, satp0/mie0/MIE0,
  BLT2, GPUidle/done0/erreurs0, framebuffer désactivé. Aucun accès SD/USB.
- Boucles bornées et restauration mtvec conservées. Un accès AHB bloqué
  requiert toujours le watchdog hôte : le firmware seul ne borne pas ce cas.

Succès attendu : phase10/résultat1, done0→1→2, busy/full0,
errors/lost/rejected0, comparaisons32/32/32 et seed inchangé dans les128B.
Phase8/résultat−5 peut désigner un timeout **ou** une completion rejetée :
interpréter les compteurs. Aucun transfert GPU n’est attendu par le contrat.
L’absence de requête native est vérifiée en simulation, pas sur la carte.

## Décodeur lié et intégration par root

```python
result = decode_same_base.decode(raw512, firmware_sha256=reviewed_sha)
# result['empty_copy_test_passed'], classification, done_counts, compared_counts
```

Le décodeur exige le SHA39484a6b… et refuse celui de l’ancien COPY vide.
MD12 ne porte pas l’adresse source : son identité seule ne distingue pas
ces variantes. Le contrôleur doit vérifier le binaire chargé, la fraîcheur
d’exécution/journal et l’identité R19. Aucun nouveau profil du contrôleur
n’est ajouté ici ; ne pas réemployer un lecteur CPU lié à un autre firmware.

## Ce qui est réellement testé

Le RTL exprime le rejet de chevauchement comme :

```verilog
overlap && (w1 != {2'b0,dst_base} || w3[15:0] != dst_stride)
```

Avec bases **et** strides égaux, ce terme vaut0 quelle que soit la valeur
d’overlap, si les valeurs capturées sont bien celles attendues. Les autres
validations restent actives, notamment src_end, alignement, dimensions et w7.
Le changement d’adresse modifie aussi src_end de32octets ; une réussite
future ne suffirait donc pas à isoler une cause physique unique.

Les tests RTL ont volontairement forcé src_end=12000060 dans deux cas :
la base originale est rejetée, la base identique réussit. Cela prouve un
contre-exemple logique utile pour cette expérience, sans affirmer que ce
src_end erroné se produit sur la carte. Les calculs originaux restent corrects
dans les deux cas sains ; aucune panne du calculateur ou du timing n’est établie.

## Preuves locales

- 13cas RV32 exécutent les928octets exacts : succès/délai, timeout, donebusy,
  rejet, canaris/destination, seed/TARGET, guards et trap. Les classes de faute
  antérieures sont importées en lecture seule. Plage CPU et commandes contrôlées.
- 29cas de décodage : métadonnées, anciennes empreintes et journaux incomplets
  refusés ; les13journaux issus du modèle sont également décodés.
- 4cas de chaîne R19 entière (AHB/FIFO/géométrie/pixels/arbitre) : deux couples
  d’horloges, readycommande0 ou readyécriture0 après TARGET. Completiondone2,
 16mots reçus, aucune assertion valid/men/mwen, aucun accès tardif. Les16mots
  du banc sont liés aux64derniers octets du BIN.
- DeepSeek OpenCode exécution :10cas RTL complémentaires, **43,152s,
 10requêtes modèle,14appels d’outils**,3tests agent dont1échec initial.
  Bornes par défaut64étapes/128requêtes, pas de prolongation artificielle.
  Bases/strides égaux réussissent ; stride différent, hauteur0, mauvais
  alignement et w7 restent rejetés. Les deux src_end forcés donnent les
  résultats opposés attendus ; ready reste0 et valid n’est jamais asserté.

Le rapport et les tests DeepSeek sont conservés intacts dans
`deepseek_execution_01`. Une coquille de commentaire est relevée dans
`cases.py` : NATIVE_WIDTH16 désigne **16pixels**, pas16blocs32B ; elle ne
change aucun mot produit et la correction est fournie dans review_01.

Toutes ces preuves sont logicielles/RTL. Elles ne qualifient ni le CPU AE350
physique, ni le netlist routé, ni la DDR. Les références Pro Dock et les
snapshots historiques restent inchangés.

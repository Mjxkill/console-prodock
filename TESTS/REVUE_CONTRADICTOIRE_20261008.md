# Revue contradictoire C22 / ORBITAL / SD-USB — 8 octobre 2026

Suivi postérieur à cette revue :
[`corrections et qualification`](CORRECTIONS_REVUE_20261008.md).
Les constats ci-dessous décrivent la version examinée avant ces corrections.

**Verdict après sept itérations : la version fonctionne dans les scénarios qualifiés,
mais elle n'est pas dépourvue d'erreurs silencieuses.** Cinq constats reproductibles
sont retenus, dont deux concernent le résultat des écritures SD. Les tests ordinaires
passent malgré ces défauts : ils ne couvraient pas ces situations.

Cette revue ne modifie ni le RTL, ni le firmware de production, ni les archives C22.
Elle ajoute des contre-exemples et leurs résultats dans
[`revue_contradictoire_20261008/`](revue_contradictoire_20261008/).
Aucun chargement FPGA, accès au matériel ou écriture sur carte SD physique n'a été
effectué pendant cette revue. Les écritures des contre-exemples visent des tableaux
en mémoire ; le test FatFs utilise un fichier temporaire.

La méthode comporte une thèse, une objection, une vérification et un arbitrage par
itération. Il s'agit d'une revue contradictoire menée dans cette session, et non de
sept avis indépendants ni d'une preuve formelle exhaustive.

## Référence examinée

- Bitstream : `bitstreams/console_gpu_sdusb_800.fs`, build `gpu_sdusb_c22`.
- SHA-256 : `aacb08e0bca7d8948606cf497b2f2ba113476afd0e23adb80156ef89c7bfdadc`.
- Archive de sources : `TESTS/reprise_20261007/c22_sources.tar.gz`, SHA-256
  `979772256516a9c9cf339a34a15c3eaf8ecabfde954be7fe1f42ef2651e3c723`.
- Sources complémentaires : pilote SD, firmware MSC/USBDISK, chargeurs ILM/ORBITAL
  et validateur ORBITAL présents dans l'arbre de travail.
- La qualification C22 historique reste consultable dans
  [`TESTS_REPRISE_20261007.md`](TESTS_REPRISE_20261007.md) et
  [`console_gpu_sdusb_800.validation.json`](../bitstreams/console_gpu_sdusb_800.validation.json).

## Les sept itérations

### 1 — Les preuves concernent-elles réellement la version retenue ?

**Thèse :** les résultats publiés correspondent au bitstream et aux sources C22.

**Objection :** des résultats anciens ou des sources différentes pourraient rendre
la qualification trompeuse, même si tous les fichiers portent « PASS ».

**Vérification :** contrôle du SHA du bitstream, des 16 empreintes de preuves du
manifeste, de l'archive et des 121 sources figées. Comparaison des sources GPU
actuelles et des contraintes avec les copies du build. La différence entre le CST
source et celui de compilation correspond aux transformations prévues du build
(noms des FIFO et suppression d'anciens ancrages), pas à une modification cachée.

**Arbitrage :** intégrité confirmée dans ce périmètre. La qualification des
écritures physiques SD n'existait pas : les essais sur carte étaient en lecture
seule. Preuve : [`01_integrity.json`](revue_contradictoire_20261008/01_integrity.json).

### 2 — Les optimisations GPU ont-elles changé le comportement ?

**Thèse :** duplication de registres, pré-décodage et déplacement de calculs
réduisent les chemins critiques sans changer le rendu.

**Objection :** un cycle d'avance ou de retard, une borne de copie ou une adresse
échantillonnée trop tôt pourrait produire une corruption intermittente.

**Vérification :** revue des changements de `gpu_accel`, `gpu_raster`,
`gpu_line_reader` et `blitter` ; examen des preuves d'équivalence C20 encore
applicables aux sources C22. Le test d'acceptation des adresses a été relancé :
512 combinaisons passent. Le calcul de segmentation de copie a été comparé sur
1 048 576 couples représentables : décalage 0…511, longueur restante 0…2047.
La nouvelle borne et l'ancien `min(reste, 512-décalage)` donnent le même résultat.

**Arbitrage :** aucun nouveau défaut reproduit dans les chemins GPU examinés.
Les équivalences sont bornées par les stimuli et les propriétés testés ; elles
ne démontrent pas l'équivalence universelle de toutes les commandes du GPU.

Preuves : [`02_copy_bounds.json`](revue_contradictoire_20261008/02_copy_bounds.json),
[`02_address/result.json`](revue_contradictoire_20261008/02_address/result.json),
preuves existantes `reprise_20261007/c20_{v1,perspective,indexed}.json`.

### 3 — Les passages d'horloge, resets et contraintes sont-ils cohérents ?

**Thèse :** FIFO à deux horloges et purge acquittée empêchent la relecture de
données anciennes, y compris quand une horloge s'arrête.

**Objection :** horloges idéalement alignées, faux chemins trop larges ou pointeurs
de FIFO mal contraints pourraient masquer le défaut en simulation classique.

**Vérification :** relance de `TESTS/test_usb_msc_port.py` avec trois couples
d'horloges et phases distinctes : demi-périodes USB/AHB 8,333/6,250 ns,
8,342/6,242 ns et 8,325/6,258 ns ; phases 0, 2,137 et 5,731 ns.
Chaque cas couvre arrêt d'horloge pendant purge, reset avec émission en attente
et bouclage du compteur après 68 097 octets ; 228 paquets IN et 28 OUT par cas.
L'audit SDF C22 retrouve 84 trajets de pointeurs Gray et cinq trajets de purge :
maxima 1,109 ns et 0,906 ns, sous la limite auditée de 6,25 ns.

**Arbitrage :** ces tests passent. Ils ne simulent pas la métastabilité analogique
ni tous les comportements électriques du PHY. La restitution volontaire du
disque au matériel présente toujours la course déjà documentée, distincte du
fonctionnement normal des FIFO. La marge GPU de +0,009 ns est positive dans le
rapport, mais toute nouvelle compilation doit être requalifiée.

Preuves : [`03_cdc/result.json`](revue_contradictoire_20261008/03_cdc/result.json),
[`03_cdc_timing.json`](revue_contradictoire_20261008/03_cdc_timing.json).

### 4 — Une commande USB malformée peut-elle être exécutée ?

**Thèse :** les validations MSC empêchent qu'une commande incohérente écrive le
support et permettent une récupération fiable après désynchronisation.

**Objection :** les tests actuels utilisent essentiellement des en-têtes et
longueurs cohérents. La recherche de signature dans un flux pourrait aussi
réinterpréter des octets après une commande invalide.

**Vérification :** firmware `usb_msc.c` inchangé, modèle de disque existant,
témoin WRITE(10) valide puis mutations : longueur CDB déclarée à 1, bit réservé
des flags, bits réservés de longueur, enfin mauvaise signature suivie d'une
nouvelle écriture sans reset. Les quatre cas écrivent 512 octets et produisent
un CSW de succès. Le dernier compte 31 octets de resynchronisation.

**Arbitrage :** défaut de validation défensive et défaut de récupération BOT
retenus, avec une distinction normative importante : une commande dont les
champs ne sont pas « meaningful » n'a pas de réponse imposée par BOT ; ce cas
ne suffit donc pas à prouver une violation d'une réponse obligatoire. En
revanche, après un CBW invalide, la récupération libre par recherche de
signature ne respecte pas l'état d'erreur maintenu jusqu'au reset demandé
par BOT. La vérification normative de la septième passe précise ce classement.
Référence : [USB-IF BOT 1.0, §6.2–6.6](https://www.usb.org/sites/default/files/usbmassbulk_10.pdf).

Preuves : [`04_malformed_cbw.c`](revue_contradictoire_20261008/04_malformed_cbw.c),
[`04_malformed_cbw.log`](revue_contradictoire_20261008/04_malformed_cbw.log).

### 5 — Une erreur SD peut-elle remonter comme un succès ?

**Thèse :** CRC, jeton d'acceptation, attente de fin d'occupation et retries
suffisent à garantir le résultat de `sd_write()`.

**Objection :** l'acceptation du bloc précède sa programmation ; une erreur
tardive peut n'apparaître que dans le statut de la carte. Une attente intermédiaire
peut aussi échouer sans être propagée.

**Vérification :** extension du modèle SPI existant, sans modification du pilote :
un mode accepte les données et leur CRC, puis conserve les anciennes données
et présente un statut R2 non nul à CMD13. Un autre prolonge l'occupation après
le dernier bloc de CMD25 jusqu'à dépasser la première attente, tout en terminant
avant la fin de la seconde. Les écritures témoins fonctionnent.

**Arbitrage :** deux défauts distincts sont reproduits :

1. Retour `SD_OK` avec zéro octet écrit, sur 512 puis 1 024 attendus ; le pilote
   n'émet aucun CMD13, alors qu'une interrogation indépendante obtient R2=04.
2. Retour `SD_OK` après une écriture multiple sans aucun jeton STOP ; le modèle
   est encore dans l'état d'écriture au retour de la fonction.

Le modèle habituel écrit immédiatement à l'acceptation du bloc : il ne pouvait
pas détecter le premier défaut. Le second relève de la propagation des erreurs,
même si une carte lente ou défaillante a dépassé le délai que le pilote accepte.

Preuves : [`05_sd_failures.c`](revue_contradictoire_20261008/05_sd_failures.c),
[`05_sd_failures.log`](revue_contradictoire_20261008/05_sd_failures.log).

### 6 — Le validateur peut-il annoncer un faux PASS ?

**Thèse :** un PASS de `check_orbital.py` impose le débit minimal configuré.

**Objection :** le nombre d'images est comparé à la durée demandée, alors que
le programme mesure également une durée réellement écoulée potentiellement
plus longue, notamment si le PC est retardé.

**Vérification :** exécution du validateur inchangé avec UART et temps simulés.
Le témoin présente 300 images en cinq secondes et passe à 60 images/s. Dans
le contre-exemple, une attente de cinq secondes reprend après trente secondes :
300 images ont réellement été produites, soit 10 images/s. Les CRC, compteurs
et échos sont cohérents. Le script écrit pourtant `status=PASS`, pour un minimum
demandé de 54,5 images/s.

**Arbitrage :** faux positif démontré dans l'outil. Cela ne prouve pas que
la carte C22 a présenté ce ralentissement. Les autres remarques sur les outils
(assertions désactivables, absence d'acquittement de pause) sont conservées
comme risques distincts, sans les confondre avec cette reproduction.

Preuves : [`06_validator.py`](revue_contradictoire_20261008/06_validator.py),
[`06_validator.json`](revue_contradictoire_20261008/06_validator.json).

### 7 — Les accusations résistent-elles aux témoins et aux spécifications ?

**Thèse :** les contre-exemples révèlent des lacunes réelles, pas seulement un
modèle arbitraire ou une mauvaise interprétation des résultats.

**Objections et vérifications :**

- « Les tests ordinaires auraient détecté ces erreurs. » Relance complète des
  tests logiciels SD/FatFs et MSC sous ASan/UBSan : tous passent, dont
  **1 616 857 contrôles MSC** et relecture indépendante par mtools du fichier
  écrit par FatFs. Ces réussites coexistent avec les contre-exemples : ce sont
  bien des trous de couverture.
- « Le jeton SD d'acceptation garantit la programmation. » La spécification
  SPI de la SD Association distingue acceptation et programmation, et prévoit
  la consultation de CMD13 après celle-ci. Le défaut tardif injecté représente
  cette distinction ; ce n'est pas un défaut CRC inventé après coup.
  [SD Association, §7.2.4, p.182](https://www.sdcard.org/cms/wp-content/themes/sdcard-org/dl.php?f=Part1_Physical_Layer_Simplified_Specification_Ver5.10.pdf).
- « Toute commande USB malformée exige la même réponse. » Faux : BOT distingue
  CBW invalide et contenu non significatif. Le rapport classe donc séparément
  F3 et F4, et ne présente pas F3 comme une obligation de réponse normative.
- « La nouvelle critique du validateur annule l'endurance C22. » Recalcul
  depuis les données brutes : 28 549 images / 520,726557 s = **54,825320 images/s**,
  donc le seuil de 54,5 est bien atteint avec la durée réelle. Les 51 poses
  sont présentes ; les compteurs `uf` et `uf_total` restent nuls dans les
  échantillons d'endurance.
- « Les reproductions prouvent une corruption sur la carte actuelle. » Non :
  elles prouvent des chemins logiciels incorrects sous les conditions injectées.
  Aucun de ces scénarios d'écriture SD n'a été exécuté sur la carte physique.

**Arbitrage final :** cinq constats retenus ; les performances et le rendu C22
observés restent valables dans leur périmètre. L'expression « sans erreurs
silencieuses » serait incorrecte pour l'ensemble SD/USB et ses validateurs.

Preuves : [`07_baseline_sd.log`](revue_contradictoire_20261008/07_baseline_sd.log),
[`07_baseline_msc.log`](revue_contradictoire_20261008/07_baseline_msc.log),
[`07_actual_c22_endurance.json`](revue_contradictoire_20261008/07_actual_c22_endurance.json).
Les premières exécutions ASan dans le bac à sable ont rencontré l'incompatibilité
LeakSanitizer/ptrace ; les relances autorisées hors bac à sable ont terminé avec
code zéro. Ce problème d'environnement n'est pas compté comme un défaut produit.

## Constats à corriger

P1 signifie ici « à corriger avant de qualifier les écritures SD pour les données
utilisateur » ; P2 désigne un défaut de robustesse ou de qualification à corriger.
Il ne s'agit pas d'un classement d'exploitabilité de sécurité.

### F1 — P1 : une erreur de programmation SD peut être annoncée comme un succès

**Localisation :** `fw_console/sd.c:173` (fin de `sd_write`), propagation dans
`fw_console/usb_disk_main.c:32` puis `fw_console/usb_msc.c:215`.

Le pilote consulte le jeton de données et la fin d'occupation, mais pas CMD13/R2.
La fonction de rappel MSC transforme donc un `SD_OK` trompeur en succès d'écriture.
Le test obtient `result=0`, `changed=0/512` et `R2=04` ; le cas deux blocs échoue
de la même façon. Des données peuvent rester anciennes sans échec signalé à l'hôte.

**Correction attendue :** consulter et interpréter R1/R2 après programmation,
propager l'échec jusqu'au statut SCSI, et conserver l'injection de panne tardive
dans la suite permanente. Un jeton valide ne doit pas constituer seul la preuve
du succès de programmation.

### F2 — P1 : le timeout avant STOP d'une écriture multiple est ignoré

**Localisation :** `fw_console/sd.c:170`.

Si `wait_ready(500)` échoue, le STOP n'est pas envoyé et `status` reste `SD_OK`.
Si la carte redevient disponible pendant le `wait_ready(1000)` suivant, la
fonction retourne succès. Reproduction : `stop_tokens=0`,
`writing_after_return=1`, `result=0`.

**Correction attendue :** transformer cette attente échouée en erreur, effectuer
une récupération définie de l'état carte, et ne jamais renvoyer succès lorsque
la terminaison CMD25 n'a pas eu lieu. Tester les limites de délai et l'accès suivant.

### F3 — P2 : WRITE(10) est exécuté malgré des champs CBW incohérents

**Localisation :** `fw_console/usb_msc.c:195`, `fw_console/usb_msc.c:202`,
`fw_console/usb_msc.c:313`.

La longueur est masquée par `& 31`, les bits réservés des flags ne sont pas
validés et WRITE(10) utilise les octets de CDB sans exiger une longueur cohérente
avec cette commande. Les trois mutations testées écrivent le disque simulé avec
un CSW de succès. Aucun débordement mémoire n'est nécessaire pour reproduire cela.

**Correction attendue :** valider les champs complets, les longueurs par opcode
et la cohérence direction/longueur avant tout effet sur le support. Définir une
politique explicite de refus. BOT ne spécifiant pas la réponse aux CBW non
significatifs, ce constat relève de la validation défensive, pas d'une réponse
normative particulière prétendument obligatoire.

### F4 — P2 : resynchronisation BOT sans l'état d'erreur requis après CBW invalide

**Localisation :** `fw_console/usb_msc.c:293`.

Après une mauvaise signature, le firmware recherche simplement « USBC » dans
les octets suivants. Une écriture suivante est exécutée sans reset BOT, avec
31 octets comptés comme resynchronisés. Le test démontre la décision du parser ;
le modèle logiciel ne constitue pas une capture des handshakes USB physiques.

**Correction attendue :** maintenir un état d'erreur jusqu'à récupération BOT,
disposer des informations nécessaires sur les frontières et longueurs des
paquets, et assurer le comportement STALL/discard requis au niveau des endpoints.
Ne pas interpréter librement des octets suivant un CBW invalide comme une
nouvelle commande susceptible d'écrire le support.

### F5 — P2 : le critère de débit ORBITAL peut valider une animation trop lente

**Localisation :** `tools/check_orbital.py:52`.

Le seuil utilise `a.seconds` plutôt que la durée écoulée. Le témoin à 60 images/s
et le contre-exemple à 10 images/s passent tous deux un seuil de 54,5 images/s.

**Correction attendue :** calculer le débit sur une fenêtre mesurée cohérente,
avec compteur initial/final et temps effectif ; vérifier aussi que les données
de mesure sont fraîches. Remplacer les assertions de qualification par des
échecs explicites pour qu'un lancement Python avec `-O` ne désactive pas les
contrôles. Ajouter ce cas de retard du PC au test de l'outil.

## Risques supplémentaires et limites

- **Attentes SPI non bornées :** `fw_console/sd_ae350.c:23`, `:34`, `:47` et
  la boucle de transfert attendent des registres sans échéance. Si le contrôleur
  reste occupé ou ne produit plus de données, les timeouts de `sd.c` ne peuvent
  pas progresser puisque `sd_port_exchange()` ne revient pas. Constat statique ;
  aucun blocage du contrôleur physique n'a été injecté ici. L'interface de port,
  actuellement sans retour d'erreur pour les échanges, doit permettre de remonter
  un timeout matériel.
- **Pause non acquittée avant chargement :** `tools/load_ilm.py:46` et
  `tools/load_orbital.py:38` attendent 0,2 ou 0,5 seconde puis effacent la réception.
  Cela ne prouve pas que le firmware a traité la pause ou restitué le disque.
  Il faut attendre un acquittement et l'état inactif effectif avant l'arrêt J-Link.
  Le bon fonctionnement des chargements C22 observés ne démontre pas cette
  propriété sous charge arbitraire.
- **Course de restitution déjà connue :** `tang/rtl/usb/usb_msc_port.v:132`
  retire l'appartenance au firmware lorsque la demande tombe. Une commande
  arrivant à cet instant peut nécessiter un reset BOT. Cette limite figurait
  déjà dans l'archive ; la revue ne la présente pas comme une nouvelle découverte.
  Le commentaire promettant qu'aucune commande n'est perdue est trop fort.
- **Timing :** +0,009 ns au GPU est le résultat positif du STA C22, pas une
  réserve importante. Il faut reprendre les analyses et les contraintes de
  traversée d'horloges à chaque modification ; pas de garantie extrapolée à
  un autre placement/routage.
- **Périmètre :** pas d'essai de coupure d'alimentation pendant écriture,
  de retrait physique SD pendant transaction, ni de campagne électrique du PHY.
  Cette revue ne démontre ni l'absence de toute faille de sécurité ni l'absence
  de tout bogue dans l'ensemble des IP.

## Reproduire les principaux contre-exemples

Depuis la racine du dépôt, compiler puis exécuter chaque commande séparément :

```sh
cc -std=c11 -O1 -g -Wall -Wextra -fsanitize=undefined -fno-sanitize-recover=all -DUSB_MSC_HOST_MODEL -I . -I fw_console TESTS/revue_contradictoire_20261008/04_malformed_cbw.c fw_console/usb_msc.c -o /tmp/console_review_malformed_cbw_final
/tmp/console_review_malformed_cbw_final
cc -std=c11 -O1 -g -Wall -Wextra -fsanitize=undefined -fno-sanitize-recover=all -I fw_console TESTS/revue_contradictoire_20261008/05_sd_failures.c fw_console/sd.c -o /tmp/console_review_sd_failures
/tmp/console_review_sd_failures
python3 TESTS/revue_contradictoire_20261008/06_validator.py
```

**Attention au sens du code retour de ces trois reproductions :** zéro signifie
que les défauts attendus ont été reproduits et les témoins contrôlés, pas que
le produit satisfait une propriété de sûreté. Après correction, leur logique
devra être adaptée en tests de non-régression exigeant un refus/échec approprié.

Tests ordinaires et simulations relancés dans cette revue :

```sh
python3 TESTS/test_gpu_address_accept.py --reference-root tang/impl/gpu_sdusb_c13/source --out /tmp/console_review_address_20261008
python3 TESTS/test_usb_msc_port.py --out /tmp/console_review_msc_cdc_20261008
python3 TESTS/test_sd.py
python3 TESTS/test_usb_msc.py
```

Les chemins `--out` doivent être nouveaux lors d'une relance. Les résultats
retenus et leurs empreintes sont listés dans
[`manifest.json`](revue_contradictoire_20261008/manifest.json).

## Références normatives utilisées pour l'arbitrage

- [USB-IF, Mass Storage Bulk-Only Transport 1.0](https://www.usb.org/sites/default/files/usbmassbulk_10.pdf),
  §5.3.1 et §6.2–6.6 : CBW valide de 31 octets, distinction validité/contenu
  significatif, absence de réponse spécifiée au contenu non significatif,
  état d'erreur jusqu'à Reset Recovery après CBW invalide.
- [SD Association, Physical Layer Simplified Specification, téléchargement v5.10](https://www.sdcard.org/cms/wp-content/themes/sdcard-org/dl.php?f=Part1_Physical_Layer_Simplified_Specification_Ver5.10.pdf),
  §7.2.4, p.182 : écriture SPI, acceptation des données, période de programmation
  puis interrogation de statut CMD13 ; certaines erreurs ne sont détectées
  que pendant la programmation.

## Suite technique recommandée

1. Corriger et tester F1/F2 avec propagation des erreurs jusqu'au statut MSC,
   puis borner les attentes SPI basses. Qualifier les écritures physiques
   seulement après cette étape, sur un support de test prévu pour cela.
2. Corriger F3/F4 et la restitution du disque avec une machine d'état explicite
   de commande/récupération, des tests de paquets malformés et de changement
   de propriétaire simultané à une commande hôte.
3. Corriger F5 et les acquittements de chargement ; intégrer les contre-exemples
   comme contrôles de non-régression, puis requalifier la version réellement
   corrigée. Les preuves historiques C22 doivent rester identifiables comme telles.

Ces corrections ne sont pas réalisées dans ce compte rendu de revue. La
qualification vidéo observée est conservée ; la qualification générale
« sans erreurs silencieuses » est refusée sur les preuves ci-dessus.

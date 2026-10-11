# Linux : affichage partagé matériel — 11 octobre 2026

État historique : **affichage Linux R12 validé sur G22r0**, tests fonctionnels sur carte
et tests logiciels réussis. L’endurance finale de 131 secondes est également réussie ; ses chiffres
sont consignés en fin de document. R12 désigne ici le logiciel d’affichage du 11 octobre, pas un
nouveau bitstream ni le port Linux R12 historique du 9 octobre.
La présentation ultérieure des diagnostics R13 est consignée dans
`LINUX_DASHBOARD_20261011.md`.

## Périmètre

Même FPGA G22r0 que la dernière ASTRILLA validée, cœur 800 MHz,
AHB/DDR/LCD 80/75/35 MHz. Pas de nouveau RTL. G22r0 reste expérimental
(-0,564 ns, 9 violations setup, aucune hold) ; les tests fonctionnels
présents ne constituent pas une fermeture du timing.

L'interface fbcon tileblit du dépôt voisin a servi de référence pour les
caractères, couleurs et déplacements. L'implémentation utilise les tuiles
DDR3 du compositeur Pro Dock, avec publication du cache A25, banques
inactives, commit au retour vertical et propriété des couches/palette.

## Tests avant carte

- `linux/tests/test_text_model.py` : **8 355 840 pixels** comparés à un
  modèle indépendant, glyphes 1..255 × 16 premiers plans × 16 fonds,
  curseur, cellules hors fenêtre et bornes DDR. AddressSanitizer et UBSan
  actifs. LeakSanitizer exige l'exécution hors bac à sable sous ce lanceur.
- `linux/tests/test_orbital_api.py` : les 51 poses / 54 626 commandes
  historiques restent acceptées par les validateurs généraux. Les règles
  supplémentaires de partage (couches, pitch, palette) sont distinctes ;
  ceci ne constitue pas un port ni un essai Linux d'ORBITAL.
- `linux/tests/test_boot.py` : Linux RV32 réel sous QEMU, six tests KUnit,
  ABI utilisateur, threads, fork, mmap/mprotect/COW.
- `linux/tests/test_atomic_code.py` : aucun AMO/LR natif dans le noyau ;
  les nouveaux exécutables liés ont leurs préchargements/barrières A25 :
  terminal 26 sites, jeu 13, test texte 12.
- Construction du noyau, OpenSBI, initramfs et exécutables avec les outils
  épinglés du port. Pas d'avertissement dans les nouveaux pilotes/programmes ;
  avertissements préexistants BusyBox et attribut SDK `no_execit` consignés
  dans les journaux.

## R4 : premier essai physique

Le transfert USB DDR a été relu intégralement, puis revérifié par le CRC du
lanceur. Aucune écriture SD ni flash. Linux et le shell PTY démarrent sur
G22r0, USB toujours **480 Mbit/s**. Le terminal, les diagnostics et le GPU
sont détectés. Avant le test de pixels : erreurs=0, sous-alimentations=0,
maximum de ligne=**1 413 cycles / 2 556**.

Le test texte refuse la police reçue : la console provisoire Linux avait
sélectionné VGA8x8 (message de démarrage 50×30), alors que le compositeur
attendait VGA8x16. Le résultat R4 est donc **FAIL**, pas une validation
visuelle ou pixel. R5 ajoute `fbcon=font:VGA8x16` à la ligne de démarrage.

Le Linux R4 a été arrêté proprement (`System halted`), puis le même G22r0
a été rechargé en SRAM avant le nouveau lancement. L'ancien noyau n'a pas
été écrasé pendant son exécution.

Les traces et résultats sont dans `linux_desktop_20261011/`. Les paquets
volumineux régénérables restent ignorés par Git ; leurs manifestes et les
SHA des sources doivent accompagner la version retenue.

## R5 : pixels et dispositions corrects, attente logicielle trop lente

Le démarrage impose maintenant VGA8x16 et annonce bien **50×15**. Le premier
script de test écrivait ses propres résultats sur le PTY pendant les images
de référence : le relais de terminal pouvait modifier l'image suivante.
En retenant ces messages jusqu'à la fin des mesures, les quatre images
passent sans changement du rendu GPU. Le programme de test est également
corrigé dans R6 pour différer ses messages lui-même.

`board/check_r5b/result.json` passe :

- quatre images texte, sommes LCD conformes portant sur **1 536 000 pixels** ;
  ce contrôle agrégé ne remplace pas une lecture de chaque pixel physique ;
- 180 présentations du jeu au premier plan ;
- jeu au second plan pendant deux cycles complet jeu/terminal/partage ;
- shell utilisable pendant le rendu et arrêt SIGTERM du jeu ;
- zéro erreur GPU, couche/sprite invalide et sous-alimentation ;
- maximum de ligne **1 695 cycles / 2 556**, USB toujours HS.

Ce résultat est une preuve fonctionnelle, pas une validation de fluidité.
La progression du jeu est lente dans les compteurs (quelques images/s).
La configuration du noyau révèle `CONFIG_HIGH_RES_TIMERS` désactivé et
HZ=250 : les attentes `usleep_range` en microsecondes du pilote sont
arrondies au tick de 4 ms. R6 active les timers haute résolution ; le jeu
consigne désormais sa durée et ses FPS mesurés pour vérifier l'amélioration.

Le premier transfert R6 (`stage_r6`) a été rejeté par le transport MSC
(`Pipe error`). Le chargeur l'a marqué FAIL et n'a pas démarré ce paquet
incomplet. La SD physique n'a pas été écrite. Le transfert est repris depuis
un chargement SRAM complet du même FPGA, avec relecture intégrale et CRC.
Cette anomalie de transport reste distincte de l'activation des timers du
noyau, qui n'avait pas encore été lancé.

R6b démarre après retransfert intégral validé, mais sa mesure de jeu est
**9,18 FPS sur 180 images en 19,597 s** : le seuil de fluidité du test est
volontairement refusé. Les timers seuls ne suffisent donc pas. R8 ajoute
des temps cumulés pour l’envoi FIFO, l’attente GPU, le cache et la présentation.
R7 (compilé, non chargé) et R8 refusent aussi les ouvertures utilisateur de
fb0 et évitent une présentation texte redondante déjà consommée par le jeu.

Un transfert R8 en blocs de 64 Kio a échoué pendant sa relecture USB. Le
paquet n’a pas été démarré. R8b réessaie avec des blocs de 16 Kio, sans
changer la vérification complète ni le CRC du lanceur. Ces échecs de
transfert restent archivés ; ils ne sont pas effacés par un succès ultérieur.

R8b échoue aussi en transfert USB de 16 Kio. Un essai J-Link direct de
25 673 688 octets atteint ensuite la limite de 1 200 s du chargeur à 1 MHz,
sans démarrage. Cela n'est pas une validation du paquet. L'essai de profilage
suivant utilise temporairement C37, FPGA du port Linux R12 déjà qualifié,
SHA `6f47a8cdab5857a0b652f791ff61fbed9a26c3c7ba7f4f30de01da95f0c076e2`.
Le retour sur G22r0 doit être vérifié séparément avant livraison.

## Transport compact et mesures R8–R10

L'essai C37 est arrêté avant Linux : l'identité USBDISK reçue était tronquée.
Le FPGA G22r0 est ensuite rechargé en SRAM. R8p2 et R9 démarrent bien sur
**G22r0**, avec une image Linux transportée par J-Link à 4 MHz.

Le paquet brut contient de grandes plages nulles dues à l'alignement du
noyau : le transport de 25 673 688 octets est réduit à environ 3,2 Mo.
`linux/package.py` émet `payload.rle.bin` ; le lanceur ILM vérifie son CRC,
reconstruit les plages littérales/nulles dans une zone DDR distincte, puis
vérifie le CRC de l'image complète avant OpenSBI. Le décodeur C réel a été
testé avec ASan/UBSan, le vrai paquet, 1 000 troncatures, des tailles invalides
et des canaris. Le test n'est pas un contournement de la vérification d'image.

Le premier fichier compact avait l'extension `.rle`, refusée par J-Link
avant écriture. L'extension binaire `.rle.bin` corrige ce point. Les erreurs
USB bulk précédentes restent non résolues ; la validation Linux actuelle
utilise J-Link pour le chargement et le CDC HS pour le terminal.

| Version | Mesure physique | Conclusion |
|---|---|---|
| R5b | texte, 291 présentations, six changements de disposition | Fonctionnel, fluidité non qualifiée |
| R6b | 180 images / 19,597 s : 9,18 FPS | Timers haute résolution nécessaires, insuffisants |
| R8p2 | 90 images / 9,522 s : 9,45 FPS | Envoi FIFO 5,361 s, cache 0,066 s ; profilage |
| R9 | 90 images / 2,277 s : 39,53 FPS | Envoi FIFO 0,420 s ; gain après chemin rapide et cache des descripteurs |
| R10 | 600 images / 14,085 s : 42,60 FPS | Ordre MMIO conservé ; texte couplé aux PRESENT du jeu |

R9 supprime le calcul systématique d'une échéance lorsque la FIFO n'est
pas pleine. Si elle est pleine, l'attente utilise toujours une vraie horloge
et expire après 250 ms. Les deux banques de descripteurs ont chacune une
copie logicielle : leur premier passage écrit tous les mots, les suivants
seulement les mots modifiés. Une expiration rend le pilote fautif et interdit
une nouvelle soumission ; aucune commande dont l'issue est inconnue n'est rejouée.

R10 utilise les accès MMIO `relaxed` uniquement dans la boucle FIFO du même
périphérique, avec publication mémoire avant le lot et barrière complète
avant d'attendre DONE. Les synchronisations cache A25 restent en place.
Le worker texte se laisse remplacer par le prochain PRESENT d'un jeu actif ;
après 50 ms sans PRESENT récent, il peut reprendre sa propre présentation.

Le contrôle négatif fb0 de R9 a bien reçu `Not supported`. Le script de test
attendait la formulation glibc `Operation not supported`, alors que la cible
utilise musl ; sa comparaison textuelle a été corrigée. Cette erreur de test
n'est pas un défaut du refus d'ouverture, mais le test R9 reste marqué FAIL.

## Isolation du coût de console et mise à jour par cellules

R10 termine 600 images en 14,085 s (**42,60 FPS**). Une mesure indépendante
sur ax15, entre les messages de début et de résultat, donne 14,132 s ; les
horloges Linux et PC concordent à la latence série près. Le même essai,
avec le relais de terminal momentanément suspendu et le curseur masqué,
donne **55,04 FPS** (600 images / 10,902 s). Le relais est repris à la fin,
avec une reprise de secours déjà programmée. Le problème résiduel concerne
bien les mises à jour du terminal, pas le débit du rendu de rectangles.

55,04 Hz correspond à 35 MHz / (1 193 × 533), fréquence du scanout existant.
Le seuil du test d'acceptation reste 45 FPS avec terminal et diagnostics
actifs ; le résultat sans terminal n'est pas utilisé pour satisfaire ce seuil.

R11 compare les mots de chaque banque de grilles, mais reconstruit encore
64 Kio à chaque modification : 90 images / 2,047 s, **43,96 FPS**. R12 conserve
plutôt 4 500 cellules effectives par banque, curseur inclus. Une paire de
caractères modifiée produit seulement quatre écritures DDR alignées. Les
grilles complètes ne sont créées qu'à l'initialisation ou au redimensionnement.
Chaque banque garde sa propre copie ; une ancienne cellule de l'autre banque
ne peut donc pas être considérée à tort comme déjà présente.

Le modèle C compare l'encodeur de paires au modèle complet sur les deux
formats de terminal, avec déplacements de curseur, glyphes nuls et toutes
les couleurs. Les tests sur carte ajoutent huit modifications successives
de deux caractères, avec trois lectures du checksum à chaque étape.
Les ouvertures fb0 sont aussi vérifiées par `errno == EOPNOTSUPP` dans
le programme natif, indépendamment du message d'erreur de la libc.

Le jeu distingue désormais D majuscule de la séquence « flèche gauche » ;
les séquences ESC arrivent correctement même si elles sont divisées entre
plusieurs lectures du terminal.

## Acceptation physique de l'affichage Linux R12

Même FPGA **G22r0**, chargé en SRAM ; USB CDC toujours **480 Mbit/s**.
Manifeste et SHA des 61 sources exécutables dans
`linux_desktop_20261011/r12_manifest.json` et `r12_source_hashes.json`.
Le paquet transport compact a pour SHA-256
`53eb7adfd096a3e5fa10485afbcbe6a26daf1e7eec409d740211b19587f682e2`.

- Profil initial : 90 images en 1,711 s, **52,60 FPS**.
- Test d'acceptation : 180 images, **51,92 FPS**, consoles et diagnostics actifs.
- Quatre images texte complètes : checksums LCD attendus `241e36f8`,
  `cf213080`, `b45e8900`, `62761800`, chacun lu trois fois. Ce sont des sommes
  de pixels calculées par le scanout, pas une capture indépendante de chaque pixel.
- Huit modifications de seulement deux caractères : réutilisation alternée
  des banques, trois checksums stables par pose ; PASS.
- Six changements de disposition pendant un jeu en arrière-plan : dimensions
  50×15 et 100×30, shell disponible, arrêt propre du jeu ; PASS.
- 41 183 commandes envoyées/terminées pendant cette séquence, aucune erreur
  GPU, aucune couche/sprite invalide, aucune sous-alimentation LCD. Maximum
  observé : **1 711 / 2 556 cycles par ligne**.
- Le stress de redimensionnement et de sortie série continue atteint **28 FPS**
  sur 785 images / 28,033 s. La mesure à ~52 FPS est celle du jeu avec consoles
  et diagnostic périodique ; elle ne vaut pas pour ce stress de texte/dispositions.
- Runtime natif A25 : 2 threads / 20 000 incréments, 32 cycles fork,
  mmap/mprotect/COW ; PASS.
- Jeu interactif : lettres, flèches, Q puis autre lancement quitté par Ctrl-C ;
  retour au shell dans les deux cas. Cela valide la réception et la sortie du
  programme ; l'aspect visuel du mouvement de raquette reste une observation LCD.

Les preuves physiques sont dans `linux_desktop_20261011/board/check_r12`,
`runtime_r12`, `profile_r12`, `boot_r12` et `interactive_r12`. Aucun test
ci-dessus n'écrit sur la SD physique ni sur la flash. Linux reste chargé en
RAM ; le démarrage autonome sur SD est un chantier distinct.

### Endurance finale — PASS

`board/interactive_r12/result.json` : **130,958 s**, **6 691 nouvelles images**,
**51,09 FPS** moyens avec six interrogations série, **257 077 nouvelles
commandes GPU terminées**. Le compteur matériel DONE 16 bits franchit quatre
fois zéro et reste cohérent avec le total logiciel à chaque échantillon.
Le texte progresse de 1 625 à 2 554 publications. Erreurs GPU, sous-alimentations,
couches/sprites invalides et indicateur de faute restent à zéro. USB=0x62,
HS 480 Mbit/s ; ligne maximale inchangée à 1 711 cycles.

Le jeu autonome est laissé en arrière-plan, PID dans `/tmp/desktop-demo.pid`,
avec terminal et diagnostics visibles. La console série est libérée après
les tests. Aucun retour visuel utilisateur n'a encore été reçu pour ce nouvel
agencement ; les résultats ci-dessus sont les validations automatiques.

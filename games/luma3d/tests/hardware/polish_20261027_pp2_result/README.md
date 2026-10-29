# PP2 — R6 en boucle, fonctionnement validé, fluidité encore insuffisante

Essai borné terminé le 27 octobre 2026. Le jeu exact R6 reste visible :
`/tmp/luma3d-pp1 --showcase`, PID **2472**, startticks **21513398**.
Identité PID/startticks/arguments et progression vérifiées après la dernière
lecture de sauvegarde. Le contrôleur a fermé CDC et libéré le verrou.
L’instance tourne avec stdin `/dev/null` : les touches du shell ne la pilotent pas.

Le vrai tour accomplit **17 étapes et huit victoires**, avec boss, checkpoint,
cristaux et retour réel dans la vallée : **894,952 s murales**, **812,013 s
simulées**, 10 532 images, **11,77 FPS moyens**. Aucune victoire injectée ni
replay sans temps n’est présenté comme le tour normal. La démo n’ouvre pas de
sauvegarde. Le fichier V4 `/tmp/op2-live.save` (5 292 octets) reste identique,
SHA256 `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`.

Les [mesures par activité](metrics/README.md) conservent p95/p99, maximums,
coûts CPU/SUBMIT/PRESENT, octets UI et budgets. Les percentiles sont des bornes
de tranches de 4 ms ; les maximums sont mesurés directement. Ces fenêtres
incluent transitions et logs ordinaires : ce n’est pas un A/B à pose fixe.

- Vaisseau : **35,09 FPS**, p95≤112 ms, p99≤220 ms, maximum 309 ms.
- Blocs : **32,14 FPS**, p95≤112 ms, p99≤368 ms, maximum 434 ms.
- Fusion 1024 : **9,63 FPS**, p95≤408 ms, p99≤440 ms, maximum 454 ms.
- Exploration : **10,89 FPS** ; maison 5,91 ; Simon 13,51 ; tour 16,37.

Les moyennes supérieures à 30 sur deux activités ne prouvent pas la fluidité.
Fusion 1024 consomme 244,93 s en préparation sur 293,46 s d’intervalle total
(**83,46 %**). Le conseiller consomme 1,93 s (**0,66 %**, inclus dans la
simulation) : son optimisation n’est pas le levier principal ici. Les copies
UI totalisent35 450 344 octets, mais le profil agrège dessin CPU, recherche
des différences et publication ; il ne permet pas d’attribuer ces 244,93 s à
la seule copie. L’exploration est dominée par SUBMIT : 266,39/432,39 s
(**61,61 %**), regroupant alimentation, cache et attente GPU.

La suite prévue conserve les graphismes appréciés de R6 : fond immuable,
pièces réellement glissées et ombres alpha pour 1024/blocs, refonte Simon,
puis suppression des redessins UI inutiles dans les autres activités. Le
candidat de temps continu reste séparé et validé localement ; il ne crée pas
d’images supplémentaires et n’a pas été chargé. Aucun nouveau benchmark
matériel n’est lancé à la clôture de ce lot.

## Vérifications et reprise de PP1

PP1 avait passé les six premières activités puis refusé une comparaison
incorrecte des trous non publiés de l’allocation shooter 28–32 MiB. Son échec
et le repli SC1 restent conservés. PP2 réutilise exactement l’ELF et les
références déjà présents, vérifiés par CRC ; seul le helper de lecture a été
transféré (221 180 octets, 55,326 s).

Le témoin local prouve les plages réellement écrites/lues par le GPU.
PP2 compare exactement 835 584 octets de fonds (CRC d7fc4310) et 961 152 octets
d’atlas (CRC c42756a1), ainsi que le HUD du boss ; il ne tolère aucune erreur
dans ces octets. Le checkpoint reprend ses pixels 3D et son HUD exacts.
Les preuves PP1 précédentes et les deux scènes PP2 sont liées au même ELF.
Le tour normal complet suit ces fixtures explicites.

Après le tour puis en boucle : errors, underflows, invalid_layers,
sprite_overflows et fault sont tous nuls. Geometry_errors reste nul ;
13 slivers sont comptés pendant le tour et conservés comme tels.
Le framebuffer3D et les octets UI/atlas sont comparés. Palette/descriptors
sont validés localement, pas relus sur carte : aucune égalité du composite
LCD complet n’est revendiquée.

FPGA **G22r0** et noyau **6.12.112-prodock-luma3d-g3d1-r1** conservés.
Zéro écriture FPGA/noyau/SD/flash. Les essais Pro Dock ne qualifient pas Neo.
Les deux régions, missions courtes et huit activités restent une tranche de
jeu ; la durée du tour automatique n’est pas une campagne de plusieurs heures.
Le retour utilisateur « parcours plus fluide, Tetris/1024 plus beaux » est
archivé séparément comme appréciation visuelle, pas comme mesure FPS.

## Identités

- ELF R6 : `d8f65131f8ad4834501850d39354be98a666e484822085004dea13c8fd1c0a48`.
- Manifeste PP2 : `989eba8d12faa0965cd8b9c322fe1e970595923580d91fffc4efdbead626b2a0`.
- Résultat matériel : `e67eb4481091169da36c1825c5809e0eae1ddec9251f42fc275d4447df54ca36`.
- Échec PP1 référencé : `9348ea8a94f20a439a19985ba408ce81739c00f2944e8037a507b02818fc534c`.

Tous les journaux ax15 sont copiés dans ce dossier ; `archive_manifest.json`
identifie les octets de cette archive documentaire sans modifier les preuves.

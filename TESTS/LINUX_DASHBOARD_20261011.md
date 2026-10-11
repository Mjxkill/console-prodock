# Tableau de bord Linux R13 — 11 octobre 2026

R13 désigne le logiciel de l'affichage Linux, sur le **même FPGA G22r0**
que R12. La demande porte sur la présentation des diagnostics : tableaux,
voyants rouge/orange/vert, barres et valeurs lisibles. Le renderer est dans
`linux/userspace/prodock-dashboard.h`, appelé une fois par seconde par
`prodock-terminal`. Le jeu, le pilote, son ABI et le RTL sont inchangés.

## Présentation et mesures

- Grille native 100 × 15 caractères : en-tête, état global, trois tableaux
  GPU/USB/SD, rappel des commandes.
- Glyphes VGA 8 × 16, bordures et barres par tuiles matérielles ; pas de
  nouveau framebuffer CPU ni de nouveau atlas.
- FPS et commandes/s calculés par différence des compteurs, sur le temps
  monotone réellement écoulé. Barres : FPS/LCD, cycles de ligne/2 556,
  débits SD/1 Mio/s. La valeur numérique conserve les débits hors échelle.
- Indications USB fidèles au registre UMSC : vitesse négociée, perte FIFO
  MSC, resets mémorisés. Elles ne mesurent pas le débit utile CDC.
- SD : capacité et compteurs lus dans sysfs, sans montage ni écriture sur
  la carte. Un compteur indisponible ou réinitialisé donne `--`, pas un
  débit inventé. Les voyants ont aussi des libellés textuels.

Les seuils et la signification complète des champs sont décrits dans
`ARCHI/LINUX_AFFICHAGE_PARTAGE.md`, section « Tableau de bord R13 ».

## Vérifications avant chargement

- `python3 linux/tests/test_dashboard.py --preview TESTS/linux_dashboard_20261011/preview` :
  **PASS**, AddressSanitizer/UBSan/LeakSanitizer, taux, repos, resets
  mémorisés, défauts, données inconnues, compteurs 32 bits qui rebouclent,
  compteurs réinitialisés et dépassement du budget de ligne. LeakSanitizer
  a d'abord refusé le bac à sable ptrace ; la même commande passe hors du
  bac à sable, sans désactiver le contrôle.
- Les cinq aperçus 800 × 240 emploient la police réellement intégrée au
  noyau et la palette texte. **Leurs entrées sont synthétiques**, pas des
  captures du LCD ou des mesures de débit de la SD.
- Construction `linux/build.py all` : **PASS**. Terminal compilé avec
  `-Wall -Wextra -Werror`. Les avertissements préexistants du SDK Gowin
  et de BusyBox restent dans le journal, sans être masqués.
- `test_package.py` : **PASS**, tailles, adresses et SHA.
- `test_atomic_code.py` : **PASS**, aucun AMO/LR natif dans le noyau ;
  les 26 sites du terminal lié conservent le préchargement/barrière A25.
- `test_boot.py` : **PASS**, démarrage RV32 QEMU, ABI, tests du runtime
  et six tests KUnit du GPU. QEMU ne valide pas les périphériques FPGA.

## Chargement sur la Pro Dock

L'utilisateur a quitté le jeu puis fermé miniterm. Le port a été vérifié
libre avant ouverture exclusive. Linux R12 s'est arrêté avec `System halted`,
puis G22r0 a été rechargé en SRAM et R13 chargé en ILM/DDR par J-Link 4 MHz.
Le paquet compact et son contenu décompressé ont leurs contrôles SHA/CRC.
Ce chargement n'installe rien sur SD ou flash.

Paquet figé : `linux_dashboard_20261011/r13_manifest.json` ; SHA des sources :
`r13_source_hashes.json`. Noyau, initramfs, OpenSBI et binaires sont contenus
dans le payload :

```
fw_payload.bin  b622790d2317d7cc3fe31f705133aad207af4ab077bfbc41d820cf5117b2ec88
prodock-terminal d2c602806d52fb5c745c6f3dc9dbc4222034855dbc6d07dfb35d53dc7a1d9942
```

Premier profil sur 90 présentations : **51,02 FPS** (1,764 s), zéro défaut
GPU, zéro sous-alimentation, zéro couche/sprite invalide, pic de ligne
1 650/2 556, USB HS à 480 Mbit/s, registre `0x62`.

## Validation finale sur carte

`board/check_r13/result.json` : **PASS**.

- **52,43 FPS** sur 180 images, avec diagnostics actifs.
- Quatre références texte plein écran : sommes matérielles conformes
  portant sur 1 536 000 pixels au total. Ce sont des contrôles agrégés,
  pas une relecture individuelle de chaque pixel physique.
- Huit modifications texte éparses conformes après réutilisation des
  banques, et six changements de disposition pendant le jeu.
- Shell utilisable, arrêt du jeu réussi, garde `/dev/fb0` vérifiée.
- 43 754 commandes supplémentaires, compteur DONE cohérent modulo 65 536.
- Zéro erreur GPU, faute, sous-alimentation et couche/sprite invalide.
- Pic de ligne **1 767/2 556**, USB HS **480 Mbit/s**, état `0x62`.

`board/observe_r13/result.json` : **PASS**. Le jeu continue pendant les
mesures du tableau : 1 656 nouvelles images, 208 mises à jour texte,
68 970 commandes et un rebouclage de DONE, sans erreur. La fenêtre hôte
de 33,872 s comprend les commandes série et donne **48,89 FPS environ** ;
ce chiffre n'est pas la mesure interne précise du test de 180 images.

La SD reste à 31 116 288 secteurs, huit secteurs lus et zéro écrit avant
et après observation. Les barres de débit SD sont donc normalement vides
pendant ce test sans accès à la carte. Les previews avec du débit sont des
fixtures de présentation, jamais présentées comme un benchmark physique.

Le jeu autonome reste lancé en mode partagé, PID enregistré dans
`/tmp/desktop-demo.pid`. Le port série est libéré après les contrôles.
L'utilisateur confirme l'affichage physique : **« Oui, c'est lisible et
stable »**, pour les trois tableaux, voyants et barres.

G22r0 garde son statut expérimental de timing : cette révision d'interface
n'est pas une fermeture des contraintes temporelles.

## Double prompt à la touche Entrée : réglage du client

L'utilisateur signale `prodock# prodock#` à chaque Entrée. Le miniterm
documenté jusque-là utilise CR+LF par défaut, même avec `--raw`.
Reproduction sur le Linux R13 déjà chargé, port vérifié libre, accès série
exclusif, sans arrêter le jeu ni redémarrer la carte :

| Octets envoyés | Réponse brute | Prompts |
|---|---|---|
| CR+LF | `\r\n\r\nprodock# prodock# ` | 2 |
| LF | `\r\nprodock# ` | 1 |
| CR | `\r\nprodock# ` | 1 |

Correction : la commande de connexion impose maintenant **`--eol LF`**.
Les octets CR/LF ne sont pas filtrés arbitrairement dans le relais PTY,
ce qui préserve le terminal brut des applications. Les preuves sont dans
`linux_dashboard_20261011/board/enter_diagnostic/`. Aucun binaire de la
carte ne change pour ce réglage.

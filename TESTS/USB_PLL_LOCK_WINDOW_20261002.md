# Qualification des LOCK USB pendant 2 ms — 2 octobre 2026

Le banc confirme le défaut de durée de l'ancienne configuration et valide
la nouvelle chaîne numérique de qualification. Il ne démontre pas que
l'instabilité USB HS observée sur carte est résolue.

La condition testée est celle relevée dans le guide fournisseur
Gowin **UG306-1.0.9E**, daté du 12 août 2026, tableau 5-2, page 40 :
surveiller un LOCK continuellement établi pendant au moins 2 ms avant de
l'utiliser. Le banc injecte des niveaux LOCK et des horloges numériques ;
il ne contient aucun modèle analogique de PLL.

## Configuration effectivement testée

Le runner extrait les trois instances `usb_reset_release`, leurs paramètres
et leurs connexions directement du top. Il extrait aussi les expressions
des entrées `pll_locked_i` et `rst_i` du PHY HS. Les fréquences de référence
sont lues dans le SDC. Le modèle simulé reprend ces instances, avec le vrai
module `usb_reset_release.v`, sans changer le RTL de production.

| Étape | Ancien top figé `gpu_usb_hs33_ep0_r1/source` | Nouveau top |
| --- | --- | --- |
| Qualification PLL_F | 1024 cycles à 48 MHz | 104000 cycles à 50 MHz carte |
| Qualification PLL_B | 1024 cycles à 60 MHz | 104000 cycles à 50 MHz carte |
| Libération du contrôleur | 64 cycles à 60 MHz | 64 cycles à 60 MHz |
| PHY `pll_locked_i` | `~phy_lock_reset` | `~rst_usb` |
| PHY `rst_i` | `PHY_RESET` | `PHY_RESET \| rst_usb` |

La qualification des deux LOCK dépend ainsi de la référence carte disponible
pendant l'acquisition des PLL. La libération finale reste synchronisée sur
le domaine PHY. La perte d'un LOCK affirme le reset de façon asynchrone,
même lorsque les sorties PLL sont arrêtées.

## Résultats

Rapport machine : [usb_pll_lock_window_20261002.json](usb_pll_lock_window_20261002.json).
Les trois compilations Icarus réussissent et `sources_unchanged=true`.

| Cas | Résultat attendu et obtenu |
| --- | --- |
| Ancien top, garde PLL_F | Échec : libération détectée à 21,370 µs, avant 2 ms |
| Ancien top, garde PLL_B | Échec : libération détectée à 17,110 µs, avant 2 ms |
| Nouveau top, démarrage normal | Deux qualifications à 2,080030 ms ; contrôleur libéré après 66 fronts PHY |
| Nouveau top, glitches tardifs | Après un glitch à 1,5 ms sur chaque LOCK, nouvelle attente complète de 2,080029 ms |
| Nouveau top, sorties PLL arrêtées | Assertion du reset de toute la chaîne et du PHY ; qualification sur 50 MHz indépendante ; maintien du reset final tant que 60 MHz reste arrêté |
| Nouveau top, reprise des sorties PLL | Reset final maintenu pendant 2,5 ms supplémentaires sans fronts PHY, puis libéré après 66 fronts PHY ; état stable ensuite |

Le délai inclut les deux étages de synchronisation de `usb_reset_release`.
La détection des libérations de qualification est échantillonnée à 50 MHz,
donc les temps rapportés peuvent dépasser le front réel d'au plus 20 ns.
Les anciens délais nominaux des seuls compteurs sont respectivement
21,333 µs et 17,067 µs. Les six nouvelles qualifications mesurées restent
supérieures à 2 ms et proches de 2,08 ms.

Les glitches injectés durent environ 0,732 ns et sont placés hors des fronts
de la référence. Cela vérifie l'assertion asynchrone du RTL dans le simulateur,
sans prétendre établir la largeur minimale détectable sur silicium.

## Reproduction et identité

```sh
python3 tools/check_usb_pll_lock_window.py --output TESTS/usb_pll_lock_window_20261002.json
```

Le runner utilise Icarus installé dans
`/tmp/console-usb-sim-tools/extracted/usr` ; les chemins des sources précédentes
et actuelles sont remplaçables avec `--previous-root` et `--current-root`.
Le rapport contient les commandes exactes, les configurations extraites,
les sorties du simulateur et les SHA-256.

- Nouveau `console_top.v` testé : `d2017d52070953c3c8811ea289ecbdb7dac68f718841f58a16d8b0f218475e6a`.
- Ancien `console_top.v` figé : `abec24bf547e9aee973fec9e0c19dcc71956fa1206931103b13c9b55473526fd`.
- Module de reset commun : `0de3b296817601f50e0eed23301201c4490a3d067832a98fdda03c113a5454a9`.
- SDC commun, inchangé : `c9367c2d390554345db5bcc5dbb115a8c348b955dd5013e99e1ecade80c8f64b`.

L'archive `usb_pll_lock_window_20261002.tar.gz` conserve le banc, le runner,
ce rapport, les résultats, les journaux et les sources actuelles/précédentes
effectivement testées. Son manifeste adjacent donne le SHA de chaque membre
et de l'archive.

## Limites

Cette simulation ne mesure ni acquisition analogique, ni métastabilité,
ni probabilité de glitch, ni phase ou gigue des horloges HS. Elle ne remplace
pas le contrôle de timing du prochain bitstream ni les essais de rechargement
sur carte. Le contrôleur et le PHY propriétaires ne sont pas simulés ici :
seules leurs entrées de reset/LOCK raccordées au top sont vérifiées. Aucune
compilation Gowin et aucun accès matériel n'ont été effectués par ce runner.

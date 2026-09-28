# G4 — 64 sprites matériels

Date : 28 septembre 2026. Cible : Tang Mega 138K Pro Dock, AE350 800 MHz.
Interface : [GPU_G4_REGISTRES.md](../ARCHI/GPU_G4_REGISTRES.md).

**Validé en simulation et sur carte**, en 800×480, build `gpu_g4_r12`.
Michael confirme également le rendu du LCD le 28 septembre 2026
(« l'image est bonne ! »).

## Simulation

`rtl/gpu_layers_tb.sv` conserve G3 et ajoute le paramètre `SPRITES=1` :

- 64 sprites DDR3, tailles 8/16/32 et rectangles 1×31, 17×7, 31×1,
  9×23, transparence, flips X/Y, clipping,
  priorités entre couches et entre objets, changement d'image.
- 16 couches complètes avec objets répartis sur l'écran.
- 64 objets de 32×32 sur la même ligne, couches désactivées.
- Rejet des bases non alignées, dimensions invalides et adresses hors DDR.
- Comparaison RGB de chaque pixel et empreinte ordonnée de chaque scène.
- Lectures CPU concurrentes, latence DDR variable, panne de plusieurs
  trames pendant un commit, écriture bloquée dans la table tant que BUSY
  est actif, récupération et retour au framebuffer G1.

Résultat complet dans [gpu_g4_simulation.txt](gpu_g4_simulation.txt) :
1 124 984 lectures CPU concurrentes ; maximum de **2 341 / 2 556 cycles**
pour les scènes normales, rechargement du cache en **5 889 cycles**.
Une surcharge volontaire de 16 couches complètes et 64 sprites sur une
même ligne atteint **2 898 cycles** : le compteur de lignes manquantes
augmente, puis l'affichage redevient correct après retour à une scène
respectant le budget. Les 64 sprites seuls passent sans ligne manquante.

La référence dessine directement les rectangles dans une image logicielle.
Elle n'utilise ni cache, ni listes chaînées, ni pipeline du matériel.

```sh
verilator --binary --timing -Wno-fatal --top-module gpu_layers_tb \
  -GW=800 -GH=480 -GVT=533 -GSPRITES=1 --Mdir /tmp/console_gpu_g4 \
  TESTS/rtl/gpu_layers_tb.sv tang/rtl/video/gpu_scanout.v \
  tang/rtl/video/gpu_line_reader.v tang/rtl/video/gpu_sprite_cache.v \
  tang/rtl/board/ddr_gpu_arb.v tang/rtl/board/cdc_word.v
/tmp/console_gpu_g4/Vgpu_layers_tb
```

## Démonstration et images attendues

`O` prépare trois ensembles immuables d'images en DDR3, à partir de
32 Mio, et teste trois scènes. `N` passe à la scène suivante sans couper
l'affichage : position, orientation, image et couches changent ensemble
au retour vertical. Les couches viennent de la démonstration G3 ; les
sprites sont de petits vaisseaux asymétriques avec cockpit et flamme.

| Scène | Contenu | Empreinte logicielle |
|---|---|---|
| [0](images/gpu_g4_pose0_expected.png) | 16 couches, 64 sprites répartis, tailles mixtes et masquage | `0e156d56` |
| [1](images/gpu_g4_pose1_expected.png) | Déplacement, retournements et deuxième image | `8e2f03f3` |
| [2](images/gpu_g4_pose2_expected.png) | 64 sprites de 32×32 sur la même ligne, couches désactivées | `92c94fc0` |

`tools/render_gpu_sprites.py --pose N` exécute la création des textures
et descripteurs C puis les compose en Python. `--hardware-log` permet
de comparer l'empreinte au journal de la carte. Les images représentent
exactement les valeurs RGB666 attendues, hors réponse physique du LCD.

Le test USB `tools/check_gpu_console.py` conserve G0/G1/G2/G3 et ajoute
les trois scènes, six permutations et un test DDR CPU de 1 Mio pendant
chaque affichage. Il vérifie empreinte, activité, absence d'erreurs et
absence de lignes manquantes.

## Validation matérielle finale

Le [journal USB complet](gpu_g4_uart.txt) conserve les essais sur la Pro Dock :

- Identification G4 à 800 MHz, écho exact de 5 441 octets.
- G0 : masques, adresses et trois passes de 1 Mio en DDR, zéro erreur.
- G1 : deux pages et quatre permutations, sommes exactes, accès CPU concurrents.
- G2 : trois dessins de 56 commandes, pixels et gardes exacts, somme `da3c6a80`.
- G3 : trois scènes de 16 surfaces et six permutations, empreintes exactes.
- G4 : trois scènes de 64 sprites et six permutations atomiques ; les trois
  empreintes du tableau ci-dessus correspondent au calcul CPU et au rendu Python.
  Un test CPU de 1 Mio accompagne chaque permutation. Aucun descripteur invalide,
  aucune erreur mémoire, aucune ligne manquante.

Le maximum sur carte atteint **2 435 / 2 556 cycles DDR par ligne**, soit
32,47 µs sur 34,09 µs disponibles, avec le trafic CPU. Le rechargement du
cache atteint **6 509 cycles**, soit 86,79 µs, pendant le retour vertical.
Les compteurs sont cumulatifs : le maximum de 64 objets et de 2 036 pixels
de sprites sur une ligne vient de la scène 2, dont les couches sont désactivées.
Les scènes 0 et 1 conservent les 16 surfaces et répartissent les objets.
Ces mesures ne garantissent pas 16 surfaces et 64 objets sur chaque ligne.

La régression G3 de ce build atteint 2 085 cycles avec trafic CPU, contre
2 477 lors de sa validation précédente. La lecture DDR et la composition
en parallèle libèrent du temps pour les sprites. Ces maxima observés ne
constituent pas une borne pour tout autre trafic mémoire.

Le test termine sur la scène 0 : bandes 00 à 15 et petits vaisseaux.
`N` passe à la scène suivante ; `O` prépare et vérifie les trois scènes.

## Bitstream conservé

- [console_gpu_g4_800.fs](../bitstreams/console_gpu_g4_800.fs), chargé en SRAM
  sur la Pro Dock FTDI `2023112818`, USB `3:12`. La flash n'est pas modifiée.
- SHA-256 : `6d09c0b3f90bd4c9e05cf5d9403c93b7d0cb76438d788835465ab32f07ff9c28`.
- Build isolé : `tang/impl/gpu_g4_r12`, 71 fichiers figés et empreintes dans
  `sources.json` ; aucune différence avec les sources courantes de compilation.
- Reproduction : `python3 tools/build_gpu.py --name NOM_NOUVEAU`.
- Timing : 110 chemins détaillés positifs, minimum **+0,138 ns**, 24 lignes
  TNS setup/hold à zéro. Cœur 800 MHz, AHB 80 MHz, DDR UI 75 MHz, LCD 35 MHz.
- Ressources : 22 156 cellules logiques, 17 015 registres, 202/340 BSRAM,
  7/298 DSP et 8/8 horloges PRIMARY.

## Ajustements avant validation FPGA

La première compilation `gpu_g4_r1` échoue au timing (minimum −2,117 ns).
L'ajout d'une seconde écriture spéciale dans le tampon source faisait
synthétiser sa banque paire en registres. Un port d'écriture commun et
registré rétablit la RAM et retire environ 4 000 registres. La simulation
ci-dessus valide la latence supplémentaire et la lecture parallèle.

Les douze banques ITCM encore laissées libres sont également placées
près des vingt banques déjà fixées. Le cache de sprites ne peut ainsi
les repousser vers des colonnes BSRAM éloignées. Les fréquences et
interfaces du processeur restent identiques.

La compilation `gpu_g4_r2` conserve des chemins trop longs dans le contrôle
ITCM et depuis le reset du DMA du blitter (minimum −3,146 ns). Le contrôle
d'adresse/lecture/écriture ITCM est rapproché du processeur matériel. Le
signal de requête native du blitter est enregistré sur les mêmes transitions
que ses états SEND, sans cycle de transfert ajouté. La régression
[gpu_g4_blitter_simulation.txt](gpu_g4_blitter_simulation.txt) repasse :
100 commandes, trois pages et leurs gardes exactes, 20 381 écritures,
190 415 lectures concurrentes après la correction finale de l’arbitre.

`gpu_g4_r3` ramène le défaut maximal à −0,685 ns : décodage d'adresse sur
le retour HREADY, puis deux banques ITCM. Le décodage des écritures qui
attendent un commit est déplacé dans la phase d'adresse AHB ; le banc teste
explicitement cette attente. Deux banques ITCM sont rapprochées du contrôle.

`gpu_g4_r4` ne conserve qu'un défaut de −0,534 ns : la boucle HREADY du
pont EXTS traversait deux fois le FPGA entre le processeur et une LUT de
contrôle. Cette LUT est placée près du processeur ; aucune modification
fonctionnelle du pont ni assouplissement des contraintes d'horloge.

`gpu_g4_r5` valide le pont HREADY. Les seuls défauts restants concernent
deux banques ITCM encore dans les colonnes de gauche (−0,382 ns au pire).
Les banques de ce groupe sont rapprochées du décodeur central pour garder
une implantation mémoire cohérente, plutôt que dépendre du routage long.

`gpu_g4_r6` valide l'ITCM mais fait ressortir la boucle valid → arbitrage →
ready du blitter (−0,784 ns). Le choix CPU/blitter est enregistré ; un
changement de client peut ajouter un cycle vide. L'affichage conserve la
priorité, et le blitter n'est acquitté qu'à l'acceptation réelle du transfert
DDR, ce qui préserve la signification de sa barrière de fin.
La régression [gpu_g4_arb_simulation.txt](gpu_g4_arb_simulation.txt) vérifie
les trois clients, les masques, la file pleine, les pauses et les retours
simultanés : 146 lectures, 23 écritures, aucune erreur d'attribution.

`gpu_g4_r7` s'arrête avant placement : la nouvelle synthèse renomme la
LUT d'activation HREADY de `n147_s6` en `n147_s7`. La contrainte est
adaptée au pilote réel de `m_hready_s1/CE` dans la nouvelle netlist.

`gpu_g4_r8` ne conserve qu'un chemin de découpage vertical du texte trop
long (−0,238 ns). Les registres de ligne du texte sont chargés sans dépendre
de la visibilité ; leur contenu est inutilisé pour une ligne découpée.
La décision de dessiner reste identique, sans cycle supplémentaire.

`gpu_g4_r9` fait ressortir l'alignement de pixels (sélection pair/impair
puis décalage variable, −0,293 ns) et une banque ITCM (−0,385 ns).
La sélection des deux mots source et leur alignement sont séparés par
un registre ; cela ajoute un cycle de vidange par couche/objet.
Les 32 banques ITCM occupent désormais un groupe compact sur les rangées
10/28/46 et les colonnes 13..23 du FPGA.

`gpu_g4_r10` valide les chemins graphiques. Le regroupement des RAM fait
ressortir le trajet entre le contrôle ITCM déplacé et ses anciens registres
de tampon (−0,600 ns). Ces registres sont déplacés ensemble près de leur
contrôle, en conservant leur placement relatif ; le protocole reste inchangé.

`gpu_g4_r11` réduit les défauts à deux chemins d'adresse ITCM, −0,120 et
−0,108 ns. Tous les chemins graphiques passent. La variante suivante utilise
le mode de routage 1 de Gowin, avec les mêmes sources RTL et contraintes
d'horloge, pour fermer ces deux derniers chemins.

`gpu_g4_r12` passe le timing avec ce mode de routage, minimum +0,138 ns.
C'est le premier bitstream G4 chargé ; les essais matériels ci-dessus passent.
Aucune image en défaut de timing n'a été chargée.

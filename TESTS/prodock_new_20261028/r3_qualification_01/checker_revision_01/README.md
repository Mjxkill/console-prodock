# Qualification hors carte du Pro Dock SD R3

**R3 est refusé pour le démarrage SD : sa ROM contient encore le firmware
GPU historique, exactement comme G22r0.** Le compilateur termine avec succès,
mais ce succès ne qualifie ni le contenu du boot ni le timing. Le parent a
suspendu le chargement SRAM ; aucun accès matériel n'a été fait par cet audit.

## Identité et cause du mauvais firmware

FS R3 : `5b516ea97edc04b64a28c5364743ed149216a4359b9e23cc0130e2e8fa7d6859`.
La reconstruction du VO post-routage lit 32 SP 16K×1, avec AD=ILMADDR[15:2]
et DO[0] relié explicitement à chacun des 32 bits ILMRDATA. Leur ordre vient
des connexions, pas des noms de banques. Le modèle officiel SP place INIT_RAM_00
aux adresses basses ; les paramètres omis sont nuls.

- Les 64 Kio reconstruits de R3 et de G22r0 sont strictement identiques : SHA
  `11e18421c8f8a729a7fc7897d0a67e89328f110551de5a06b81d2bb6fbd89195`.
- Les 2 127 paramètres des 32 SP, dont 1 967 INIT_RAM explicites, sont identiques.
- Sur les 20 936 octets du nouveau bootstrap attendu, 20 556 diffèrent dès
  l'offset 41, adresse 0x80000029 : attendu 0x22, observé 0xa2.
- Les quatre fichiers source itcm0..3 reconstruisent exactement le bon binaire
  SHA `d8ab75277c4cb4eb2a4123fbdf269d96fa8a5cd44cb84eaa11c8e3fdf66d8ae8`.
  Il ne s'agit donc pas d'un décalage des lanes ou seulement du remplissage final.
- Les chaînes de l'ancienne démonstration GPU sont présentes dans la ROM publiée.

Le fichier `riscv_ae350_soc_ext/riscv_ae350_soc.v` inclus dans le candidat est
une **netlist chiffrée déjà synthétisée**, marquée GowinSynthesis V1.9.12 du
8 octobre. Modifier `gw_itcm_config.v` ne remplace pas ses INIT déjà compilés.
Le constructeur initial avait omis la régénération de l'IP AE350. Cette omission
explique les anciennes données ; les faits ne démontrent pas un bug du lecteur
PR ou de l'incrémental. `tools/build_gpu.py:249–266` et
`tools/build_console_neo.py:162–190` montrent la phase IP nécessaire.

Le parent a corrigé le constructeur et lancé R4 dans un nouveau dossier : IP
AE350 régénérée séparément avec les sources fournisseur, cfg et ROM du candidat,
part Pro Dock GW5AST-LV138FPG676AC1/I0. Aucune source commune ni référence G22r0
n'est remplacée. Le nouveau VO devra impérativement passer le contrôle ci-dessous.

## Timing publié : non fermé

| Mesure | G22r0 | R3 |
|---|---:|---:|
| Endpoints setup violés, résumé outil | 9 | 218 |
| Endpoints hold violés, résumé outil | 0 | 185 |
| Plus petit setup publié | −0,564 ns | −7,789 ns |
| Plus petit hold publié | +0,138 ns | −3,451 ns |
| Plus petite recovery publiée | +1,306 ns | −12,298 ns |
| Plus petite removal publiée | +0,470 ns | −2,265 ns |

Les 25 pires setup et recovery R3 publiés sont PHY_CLKOUT→bus80_clk. Les
25 pires hold sont bus80_clk→PHY_CLKOUT ; les removal incluent aussi
clk50→PHY_CLKOUT. Les destinations comprennent synchroniseurs, FIFO USB,
mailboxes et resets USB. Ce sont des traversées entre domaines à analyser
avec leur protocole CDC/reset, pas une preuve que le domaine DDR synchrone
ne satisfait pas sa période. Aucun chemin n'a été masqué par cet audit.

Le tableau TNS par horloge de R3 indique zéro pour tous les domaines. Les
Fmax publiées comprennent DDR UI 75,170 MHz pour 75,002 MHz contraints,
AHB 81,662 pour 80 MHz, PHY 65,591 pour 60 MHz et sclk 125,033 pour 120,005 MHz.
Ces résumés ne remplacent pas un contrôle CDC ni les détails de tous les
chemins ; les rapports globaux sont limités à 25 par type. Le nombre total
d'endpoints recovery/removal négatifs n'est pas publié : on sait seulement
qu'au moins 25 chemins distincts de chaque type sont négatifs.

La comparaison ne porte pas sur une STA strictement identique : G22r0 utilise
V1.9.12 (setup 0,855 V, hold 0,945 V), R3 V1.9.12.03 (setup 0,873 V, hold
0,927 V). Les cinq requêtes setup G22 ciblées sur une même horloge ont été
retirées de R3, qui publie les pires chemins globaux. Les contraintes elles-mêmes
sont inchangées. Le groupe contenant clk50 ne mentionne pas explicitement son
horloge générée PHY_CLKOUT avec bus80_clk. L'effet de la version et de la portée
des rapports doit être établi avant d'attribuer l'écart à un changement physique.

## Ressources, horloges et broches

| Ressource | G22r0 | R3 | Capacité |
|---|---:|---:|---:|
| Logique LUT+ALU | 83 485 | 83 453 | 138 240 |
| LUT | 63 487 | 63 488 | — |
| ALU | 19 998 | 19 965 | — |
| Registres | 53 481 | 53 318 | 139 140 |
| CLS | 58 105 | 58 078 | 69 120 |
| BSRAM | 287 | 287 | 340 |
| DSP, unités du rapport | 177 | 177 | 298 |
| IOLOGIC | 102 | 102 | 300 |
| PLL | 5 | 5 | 12 |

Les 18 lignes de réseaux globaux et leurs zones publiées sont identiques :
8 PRIMARY, 8 LW, plus les utilisations HCLK. Les trois PR1014 restent clk_d,
ae350_tck_d et rtc_clk, également présents sur G22r0. L'identité des zones
publiées ne prouve pas l'identité de toutes les pistes ou de leurs délais.

CST identique octet pour octet. Les 123 lignes physiques de broches affectées
(aux 121 ports, dont entrées différentielles) sont identiques dans les tables
complètes des deux versions : location, banque, type, direction et réglages.
187 broches inutilisées diffèrent uniquement par la colonne Drive : 8 dans
l'ancien rapport, OFF dans R3. Aucune broche affectée ne change. Le tableau
par nom de port G22 omettait deux lignes LVDS présentes dans sa table complète ;
cela ne doit pas être pris pour deux broches nouvellement connectées.

Les 128 fichiers de référence ont été vérifiés. Dans R3, seuls la configuration
ITCM et les cinq requêtes du SDC diffèrent parmi ces sources historiques.
L'IP CPU précompilée, les pins, PLL et RTL de référence étaient inchangés.

## Contrôle ROM réutilisable et preuves

`rom_check.py` expose `decode(text)` et `compare(image,binary)`, et une CLI :

```sh
python3 -B TESTS/prodock_new_20261028/r3_qualification_01/rom_check.py \
  --vo CHEMIN/du_candidat.vo --binary CHEMIN/sd_boot.bin --out DOSSIER_NEUF
```

Retour 0 uniquement si les octets du binaire attendu correspondent, 1 sur
mismatch, exception sur layout inconnu. La fin hors payload est observée et
comptée séparément. La preuve se limite aux INIT du VO ; le contrôleur matériel
doit encore lier VO, FS, carte exacte et essai de boot.

11 groupes de tests passent : limites de bits/lane/chunk/dernière adresse,
acceptation des lanes attendues encodées en fixture VO indépendante, rejet réel
de R3, identité reconstruite G22, altération d'un octet, taille invalide, largeur,
adresse, sortie, banque, paramètres INIT inconnus/doublons et port dupliqué.
`tests.json` et `tests.log` conservent ces résultats et les SHA du module.
`rom_r3/result.json` garde le premier refus CLI et l'image reconstruite.
`result.json` est l'audit final reproductible avec les fichiers d'entrée.

La lenteur de lecture PR observée dans l'audit précédent ne signifie plus une
compilation bloquée : R3 a finalement terminé après 39 min 42,52 s. Cet état
historique n'est ni effacé ni utilisé pour attribuer une cause au mauvais boot.

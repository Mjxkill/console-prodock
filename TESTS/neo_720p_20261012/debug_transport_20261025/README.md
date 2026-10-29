# Neo N56r10 : séparer transport JTAG et réponse du bloc dur

Le 25 octobre, quatre essais bornés ont été exécutés sous le verrou Neo.
Ils ne chargent pas de bitstream et ne créent pas de cible CPU OpenOCD :
aucun examen automatique, `halt`, reset CPU, accès DDR, SD ou GPU.
La Pro Dock est testée séparément par l'opérateur du jeu.

La dernière programmation enregistrée reste N56r10, SHA FS
`7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28`.
Cette identité provient du journal de chargement ; ce n'est pas une relecture
de la SRAM FPGA. ESP-Prog est sélectionné par sa description `Dual RS232-HS`
et sa position USB `3-4.4.2`, distincte du programmateur Neo `2025041420`
sur `3-4.4.1`. Chaque essai vérifie ces identités et l'absence d'autre sonde.

## Résultats

| Mesure | Résultat |
|---|---|
| IDCODE AE350, TCK 100 / 1 000 / 100 kHz | `0x1000563d` à chaque lecture |
| DTMCS, 12 lectures par essai | `0x00007071` : version 1, adresse 7 bits, idle conseillé 7, DMISTAT 0 |
| Une requête READ DMSTATUS, adresse DMI `0x11` | Réponse `0x004400000003`, statut BUSY |
| Une requête READ DMCONTROL séparée, adresse `0x10` | Réponse `0x004000000003`, statut BUSY |
| DTMCS après requête | `0x00007c71`, DMISTAT 3 |
| Écriture `0x10000` dans DTMCS, DMIRESET uniquement | DMISTAT revient à 0 |
| NOP DMI suivant, sans nouvelle requête de lecture | BUSY revient ; reproduit deux fois pour chacun des deux registres |

Après chaque READ, le banc attend 1 000, 10 000 puis 100 000 cycles TCK à
100 kHz. Les premières réponses BUSY sont mémorisées : **les NOP suivants
ne suffisent pas seuls à démontrer que la requête reste en attente**.
C'est la raison des essais séparés avec DMIRESET : après 100 000 cycles
supplémentaires, on efface uniquement le statut mémorisé, on constate son
effacement, puis on relit par NOP. BUSY réapparaît. Aucun `DTMHARDRESET`,
qui annulerait la requête en cours, n'est envoyé. L'initialisation du TAP
au début de chaque essai est consignée ; elle n'est pas un reset CPU.

Les zéros du champ données ne sont **pas** les valeurs de DMSTATUS ou de
DMCONTROL, puisque la transaction n'a pas abouti. En particulier on ne
connaît pas `dmactive`, `ndmreset`, `allhavereset` ou l'état du hart à partir
de ces réponses. La lecture DMCONTROL ne modifie aucun de ces bits.

Cette observation est indépendante du réseau de capture GAO. Elle confirme
un transport TCK fonctionnel pour ces opérations et une requête DMI qui
ne termine pas. Une ancienne erreur de transport mémorisée n'explique pas
seule le résultat. Elle ne prouve ni une absence d'horloge particulière,
ni l'équation interne de HRESETN, ni une défaillance DDR. Lire un registre
du module de debug ne constitue pas une lecture de la mémoire DDR externe.

Les déclarations locales Gowin précisent que HRESETN est synchronisé sur
AHB_CLK (`simlib/gw5a/prim_sim.v:17020`), PRESETN sur APB et DDR_RSTN sur
DDR_CLK. Le modèle AE350 de cette bibliothèque est vide : sa simulation
ne valide pas le séquencement interne du bloc dur. Le routage R10 relie
AHB/APB à 80 MHz ; GAO en voit l'activité mais ne mesure pas encore RTC
10 MHz ni la livraison du chemin cœur 800 MHz.

Une quatrième lecture GAO, après les essais JTAG, retrouve sur ses 4 096
points POR/HW et DDRinit à 1, HRESETN et le reset vidéo à 0. `vid_hclk`
présente 3 276 transitions et `gpu_clk` 4 095 ; ce sont des horloges
sous-échantillonnées, pas des mesures de leurs fréquences. Le CLI a encore
demandé le tampon « initial » : l'ordre temporel exact de son acquisition
n'est pas établi. Cette lecture concordante n'est donc pas présentée comme
un chronogramme synchrone des commandes DMI. Le CSV et son identité sont
archivés sous `../reload_r1_cold_20261022/gao_cli_research/r10_initial_read_04/`
et décodés dans `analysis.json`.

## Ce qui reste à discriminer

Le constat GAO précédent — POR/HW relâchés, HRESETN maintenu bas — reste
à confronter aux autres sorties de reset (`PRESETN`, `DDR_RSTN`) et à un
témoin divisé de RTC. Un signal constant correctement capturé ne devient
pas faux du seul fait d'un pire chemin en violation ailleurs dans GAO.
Les limites de l'instrument sont consignées, sans en faire une explication
du défaut du SoC.

La référence SDK Gowin attend 20 ms de stabilité de `ddr3_init_completed`
avant POR/HW. Notre wrapper utilise deux FF AHB. Cette différence existe
aussi sur N56r8, qui démarre, et Pro Dock : **20 ms est un exemple SDK,
pas un minimum constructeur établi ni une cause démontrée**.

Le module expérimental sous `../reset_sequence_20261025/` est seulement
simulé, sans synthèse, routage ou chargement. Il prépare un éventuel essai
court/20 ms dans un même bitstream, avec une impulsion commune et retour
confirmant le reset réellement appliqué. Un redémarrage à chaud n'est pas
une preuve du comportement au chargement FPGA. Avant construction, il faut
figer les observations discriminantes et le déclenchement de capture :

1. activité RTC et AHB indépendante du reset CPU ; état direct du reset PLL ;
2. POR/HW, HRESETN, PRESETN et DDR_RSTN corrélés ;
3. mode et accusé de réception de la commande, pour savoir si l'essai a eu lieu ;
4. comparaison court/long/court sur le même routage, sans forcer un reset
   sortant à 1 et sans modifier DDR 5.9/300 MHz ;
5. résultat négatif conservé : des horloges actives et un reset long sans
   réponse ne valideraient pas l'hypothèse d'une simple durée insuffisante.

Aucun nouveau routage n'est lancé dans cette étape.

**Suite de cette étape, après choix utilisateur :** le délai expérimental
est porté à 50 ms. La simulation RTL, la synthèse du séquenceur et sa
simulation mappée passent ; un candidat complet R15 est préparé dans un
snapshot Neo isolé. Voir [l'expérience 50 ms](../reset_sequence_20261025/README.md)
pour l'état de construction et les limites du futur essai. Les constats
de transport ci-dessus portent toujours sur N56r10.

## Reproductibilité

Les dossiers `read_01`, `dmstatus_01`, `clear_sticky_01`, `dmcontrol_01`
contiennent le Tcl réellement exécuté, le journal brut, ses empreintes,
l'identité USB et les métadonnées. `analyze.py` vérifie les empreintes et
décode les réponses dans `analysis.json`, sans accès carte.

La sémantique DMIRESET/DTMHARDRESET et les champs DTMCS proviennent des
définitions RISC-V du source OpenOCD local :
`/home/michael/openocd/openocd.git/src/target/riscv/debug_defines.h`,
lignes 61–129. Ne pas confondre DMIRESET, effacement du statut du transport,
avec un reset du CPU.

La campagne commune `TESTS/dual_board/20261025_neo_reset_sequence/` passe
les 11 groupes, entrées inchangées. Elle n'inclut pas le bloc dur AE350
comportemental absent des bibliothèques et ne qualifie pas N56r10 sur carte.

# N56r8 → R9 → N56r8 : DDRinit allumé, DMI bloqué sur R9

Le 24 octobre 2026, le même bitstream R9 qui échoue au démarrage annonce
**`ddr_init=1` sur la LED utilisateur V13**, avant toute interrogation DMI.
Le TAP AE350 répond ensuite avec IDCODE `1000563d`, mais les transactions
DMI expirent. Le retour au bitstream N56r8 rend le CPU accessible et la
mire visible. L'hypothèse « calibration jamais terminée, donc CPU tenu en
reset par DDRinit=0 » ne décrit pas cet essai.

| Phase | LED utilisateur | Écran via caméra | Accès CPU |
|---|---|---|---|
| N56r8 initial | Allumée ; identifiée par l'utilisateur | Mire visible | Garde JTAG valide, CPU arrêté dans le parking ROM |
| R9 | Allumée ; utilisateur confirme « Oui, allumée en continu » | Écran noir | TAP présent ; DMI timeout, délai total borné à 30 s |
| N56r8 restauré | Même LED allumée, observation caméra | Mire revenue | CPU accessible et arrêté ; compteur image +62, checksum `1ff8f800` |

## Identités et portée

- Neo : programmateur Sipeed `2025041420`, CPU via ESP-Prog `Dual RS232-HS`.
- N56r8 SG4 : `51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35`.
- R9 DMA C150 : `1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde`.
- Script relu R2 : `e59aa8eea8765787ce2798f5858bf9196c8df26fd6c3271333cdbe7f80f5877b`.
- Webcam locale Nuroum V21, série `AW32LCAA9091000389`, MJPEG 1920×1080.

Le RTL **et la netlist routée des deux bitstreams** vérifient le chemin
registre de completion DDR → inverseur → sortie V13 : `led_n = !ddr_init`.
La mesure est une observation optique de cette sortie, pas une lecture de
registre par le CPU. Les captures restent surexposées à l'emplacement de
la LED ; elles ne permettent pas d'analyser des glitches rapides.

Les captures sont [avant](n56r8_before_camera.jpg),
[R9 avant DMI](r9_camera.jpg) et [après restauration](n56r8_after_camera.jpg).
Leurs SHA et les limites d'interprétation sont dans
[camera_observations.json](camera_observations.json).

Le script figé demandait trois observations utilisateur. Pour la dernière,
l'utilisateur a demandé de se fier à la caméra (« tu le voies dans la cémera
non ? »). La vérification finale a donc été faite directement sur la capture.
Le [résultat brut](result.json) est conservé sans réécriture : son inférence
automatique limitée aux trois réponses utilisateur reste non concluante.
Le complément caméra distingue explicitement la provenance des observations
et complète la comparaison. Son résultat ne constitue pas une qualification
fonctionnelle du FPGA.

## Ce qui est établi et ce qui reste à mesurer

L'annonce de fin de calibration n'est pas absente sous R9 lors de cet essai.
Cela ne prouve ni la fiabilité des lectures DDR, ni le débit, ni l'arrivée
correcte de DDRinit à toutes ses charges. Le défaut antérieur de lecture
vidéo N56r8/R2 reste un problème distinct non résolu.

Le prochain diagnostic doit distinguer : lock filtré de PLL AE350, activité
du bus 80 MHz, sortie des deux étages de reset, puis réception des resets
par le bloc CPU. Ni le niveau de reset CPU ni le lock AE350 ne sont mesurés
par cet essai. L'absence DMI ne suffit pas à choisir entre eux. Les routes
de ces signaux doivent être étudiées sans assimiler délai de route et marge
STA.

R9 reste **FAIL** : setup −0,849 ns, recovery −0,360 ns, anomalie de routage
reset4/LW conservée. Aucun nouveau routage, aucune écriture framebuffer,
commande GPU, reprise CPU, lancement Linux ou écriture SD/flash n'a été
effectué. La Pro Dock n'a pas été touchée. La Neo est laissée sur N56r8,
mire interne visible et CPU arrêté. Le verrou Neo est libéré.

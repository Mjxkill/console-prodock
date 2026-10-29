# Contrôles USB sur N56r8 après changement de câble

La Neo conserve exactement N56r8 SG4, SHA
`51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35`.
Le CPU reste arrêté dans le parking ROM. Aucun nouveau bitstream, accès
DDR de données, commande GPU, reprise CPU, écriture SD ou flash.

## Énumération et diagnostic EP0

L'utilisateur remplace le câble SOFT-USB. Le journal du noyau rapporte à
18:14:47 une nouvelle connexion high-speed, port physique `3-10`, adresse
tentative 31. Aucun descripteur `359f:2011 / NEO00001` n'apparaît ensuite
pendant les contrôles. La sonde EP0 préparée n'est donc pas exécutée sur
un périphérique non identifié. Ceci ne mesure pas les PLL ni le reset AE350.
La caméra après changement de câble confirme la mire et la LED utilisateur
allumée : [capture](n56r8_new_cable_camera.jpg).

## Lecture AHB et deux essais de capture

La [lecture seule](n56r8_usb_readonly_01/readonly.log) trouve
`ID=55544e41, status=0, sequence=0`. Le diagnostic existe, n'est pas occupé
et son échange de libération des resets AHB/PHY est arrivé à terme.

Deux essais bornés écrivent uniquement `E900200C` : commande `1` armement,
puis `4` désarmement après un échec de contrôle. La commande `2` et l'attente
d'une seconde prévue ne sont jamais atteintes. Les contrôles restent
stricts et les deux essais sont **FAIL**, malgré un désarmement confirmé.

1. [Essai 01](n56r8_usb_capture_01/trial.log) : la séquence passe 0→1 après
   armement ; le premier en-tête échoue au contrôle. Ses valeurs exactes
   n'avaient pas été journalisées. Le désarmement passe 1→2, en-tête
   `55544e41, 1, 4`, compteur ticks `00891fa8`, état pré-désarmement armed=1.
2. [Essai 02 sans rechargement](n56r8_usb_capture_02_warm/trial.log) : le
   script révisé ajoute seulement les deux lectures brutes avant les mêmes
   contrôles. Séquence 2→3, les deux banques ARM sont identiques : en-tête
   **`55544e41, 1, 0`**, alors que la commande écrite est **1**. Le compteur
   pré-clear vaut `00891fa9`. Le désarmement passe 3→4 et renvoie correctement
   `55544e41, 1, 4`, ticks `008923f4`, armed pré-désarmement=1.

La version initiale du lecteur et ses dépendances sont archivées dans
`n56r8_usb_capture_01_source_archive/`. La révision ne transforme pas
l'en-tête inattendu en résultat acceptable.

## Interprétation limitée

L'armement a eu un effet et le compteur du domaine PHY a avancé. Ce domaine
n'est donc pas totalement sans horloge pendant ces observations N56r8 ;
sa fréquence et sa qualité ne sont pas mesurées. Les compteurs SOF,
RXERROR et reset restent à zéro dans ces fenêtres courtes, d'environ
150 ms **si** le PHY tourne à 60 MHz. Ce n'est pas la capture d'une seconde
prévue, ni la preuve d'une absence de toute activité électrique USB.

Le contrat RTL pré-clear conserve toujours l'identifiant, la version et la
commande courante dans l'en-tête ; il ne justifie pas l'écho zéro de la
commande 1. Les deux lectures identiques rendent visible une incohérence
stable de la banque rendue à l'hôte, sans localiser son origine. Le problème
n'est pas limité au tout premier transfert après reconfiguration.

La suite locale examine `command[0] → snapshot[64] → FIFO de réponse →
bank[2] → AHB`. Le registre routé `snapshot_64_s0` reçoit bien command[0],
sur phy_clk, avec enable `!sending && cmd_valid` et reset `ureset` ; ceci ne
prouve pas son fonctionnement physique. Aucune cause FIFO, routage,
contrôleur DDR ou outil Gowin n'est encore démontrée. Le lien éventuel avec
l'absence DMI de R9 ou le lecteur vidéo défaillant reste à établir.

La conclusion du [test LED R9](../r9_led_compare_trial/README.md) demeure
distincte : DDRinit annoncé à un sous R9, DMI en échec, retour N56r8 réussi.

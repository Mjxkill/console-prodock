# Recherche GAO — état du 24 octobre 2026

Recherche statique, sans accès matériel ni lancement de serveur. Les commandes
de capture restent à exécuter par l’opérateur root sous verrou, après
identification du câble Neo.

## Résultats établis

- Root a validé l’insertion post-synthèse sur N56r10 :
  `add_file -type gao {<configuration.gao>}` puis `run pnr`.
- Le manuel local SUG114-3.4.4E décrit Capture Initial Data comme la première
  capture après configuration du FPGA, avant Start. Attribut XML de AoCore :
  `capture_init_data_enabled="true"`.
- Le `main` du `/home/michael/gowin/IDE/bin/gao_sh` installé parse seulement
  `-gao`, `-out`, `-device`, `-cable`, `-location`. Il ne parse pas les options
  ajoutées dans le manuel 3.5. Les désassemblages sont conservés ici.
- Le test initial `gao_sh -h` n’a pas affiché une aide : il a essayé de se
  connecter au serveur JTAG et a échoué. Il ne doit pas être répété pour obtenir
  une aide lorsque le serveur est actif.
- Le chemin Start appelle `startDataTrigger`, mais ce nom était trompeur :
  l’analyse complète établit une branche dédiée à l’initiale, qui saute
  `startTrigger` lorsque l’attribut XML est vrai. Détails ci-dessous.
- Dans le manuel officiel 3.5, `-auto_run` attend un entier positif et répète
  les captures. `-auto_run 0` n’est pas un mode de lecture documenté.
- `-location` désigne le Port numérique affiché par Programmer dans USB Cable
  Setting. Ce n’est pas le numéro de série. L’opérateur doit établir la
  correspondance avec `2025041420`. Omettre la location sélectionnerait le
  premier câble détecté.

## Sources

- Manuel installé : `/home/michael/gowin/IDE/doc/EN/SUG114-3.4.4E_Gowin Analyzer Oscilloscope User Guide.pdf` ; extraction `gao_manual.txt`.
- Binaire installé : `/home/michael/gowin/IDE/bin/gao_sh` ; analyse `main.asm`
  et `GAO_GaoCmdStandardAnalyzer_*.asm`.
- [Manuel officiel SUG114-3.5E, 22 septembre 2026](https://cdn.gowinsemi.com.cn/SUG114E.pdf),
  pages 24 et 55–61. Son chapitre CLI récent ne décrit aucune option explicite
  de récupération de l’initiale sans nouvelle capture ; il ne constitue pas une
  preuve de compatibilité du binaire installé.

## Lecture initiale : preuve statique et limite matérielle

L’exécutable installé `gao_sh` possède bien le chemin initial :

1. `read_VER_2000`, adresses `46a9c3` à `46aa28`, lit
   `capture_init_data_enabled`, compare à `true` et stocke le booléen à
   l’offset `0x68` de `AoCore`.
2. `startDataTrigger`, `47b5ad`, teste ce booléen. S’il est vrai, la branche
   `47b570` marque l’état de lecture et saute l’appel `startTrigger`.
3. `checkState`, `47dda3`, choisit la branche initiale si `0x68` est vrai et
   le booléen Force (`0x69`) est faux.
4. Cette branche sélectionne le registre 3, opération
   `OP_SELECT_CAPTURE_INIT` à `47e2c8`, puis envoie
   `OP_READ_CAPTURE_INIT` à `47e439`. Elle ne commence pas une capture normale.

Le GUI utilise la même logique. Aucun bouton distinct « lire l’initiale » n’a
été identifié : Start/F1 entre dans cette branche lorsque l’attribut est vrai.
L’ouverture seule n’est pas établie comme une lecture automatique.

Cette preuve ne prouve ni la réponse du serveur ni le bon routage JTAG vers
Neo. `verify_static.py` réextrait les fonctions avec objdump, vérifie les
repères et écrit les SHA dans `static_evidence.json`. Ce script ne lance aucun
exécutable Gowin et ne touche pas au matériel.

## Commande candidate pour ce binaire précis

À exécuter seulement par root sous le verrou Neo, après correspondance prouvée
entre câble, canal, location et série 2025041420. Le placeholder LOCATION ne
doit pas être remplacé par une valeur supposée :

```text
/home/michael/gowin/IDE/bin/gao_sh \
  -gao /home/michael/console/tang/impl/console_neo_n56r10_gao_startup/source/tang/boards/neo/startup.gao \
  -device GW5AST-138C \
  -cable FT2CH \
  -location LOCATION_CONFIRMEE \
  -out /CHEMIN_NOUVEAU/initial
```

L’environnement doit provenir de `tools.gowin_toolchain.environment()`. Le
choix `FT2CH` reste conditionné à la vérification du câble ; cette commande
n’est pas encore une procédure matérielle Neo validée.

- L’ancien `-out` est un préfixe : sortie attendue
  `initial_core0_window0.csv`. Le binaire ajoute toujours ce suffixe et appelle
  `exportCSV`. Fournir `.gwd` ne choisit pas le format GWD.
- L’export est codé avec période 1 et unité `us` (`45ea73` à `45ea9c`). Les
  indices doivent être interprétés avec l’horloge réelle, ici 20 ns par point
  pour 50 MHz : 4096 points = 81,92 µs, prétrigger128 = 2,56 µs.
- Sans déclenchement DDRinit, cette ancienne CLI peut attendre ; ses options
  modernes `-force_trigger_timeout` et `-stop_timeout` sont ignorées.
- Un arrêt externe du processus borne l’attente mais ne constitue pas une
  capture forcée. Aucune interruption d’un processus n’a été faite ici.
- Aucun chemin GWD ni temporisation de force n’est exposé par ce main. Utiliser
  la GUI pour ces opérations après sauvegarde de l’initiale ou constat documenté
  de son absence. La capture forcée tardive doit rester distincte de l’initiale.

## Serveur réellement demandé

`initLocalServerListForgaosh` construit le chemin relatif
`applicationDir/../../Programmer/bin/jtagserver`, puis le lance avec `-local`.
Pour l’installation présente, cela désigne
`/home/michael/gowin/Programmer/bin/jtagserver`, et non le dossier SP1 séparé.
La session locale FT2CH s’appelle `gao1`. La commande CLI peut donc créer son
serveur ; elle ne constitue pas une simple connexion passive à un serveur
préexistant.

Le GUI possède aussi le mode serveur distant, port TCP36548 par défaut d’après
le manuel local. Ce mode est distinct du serveur local `-local` ; le vieux
`gao_sh` n’a pas d’option CLI hôte/port.

## Sélection BL616 : constat encore non résolu

Le scan exécuté par root, pas par cet agent, a donné :

```text
Gowin USB Cable(FT2CH)/0/12401/null
USB Debugger A/1/0/null
USB Debugger A/2/0/null
USB Debugger A/3/0/null
```

SUG502-2.5.1E pages45–46 indique la structure
`type/canal/location/UID`. Les nombres 1,2,3 ci-dessus sont donc des canaux.
La location12401 n’est pas identifiée comme Neo ; le root constate qu’elle
ressemble au chemin de l’ESP-Prog. Ne pas l’utiliser pour Neo.

Il n’y a pas de paramètre série dans le main de `gao_sh`. La location passe par
`QString::toInt(...,10)` puis est transmise dans `cable_location` avec
`cable_index`. Donner le numéro de série comme location ne contourne pas cette
limite. Le LocId D2XX Linux ne doit pas être assimilé au Port Gowin.

Le nom complet USB Debugger A est absent du GUI, mais son parseur
`GaoProgrammerModel::onScanCableFinishForFT2CH` recherche la sous-chaîne
`Debugger` (`4e45ed`) et la classe comme famille1, comme FT2CH (`4e4487`).
Il conserve canal/location/UID pour les listes. Il existe donc une prise en
charge générique de détection, sans preuve suffisante ici de sélection ou
communication GAO avec ce BL616. Trois entrées location0/UIDnull ne permettent
pas à elles seules de garantir la carte physique choisie.

## GUI de secours, après identification du câble

Paramètres reconnus du main : `-gao`, `-dir`, `-series`, `-device`, `-fs`.
Il n’accepte pas `-cable` ni `-location` en ligne de commande. Exemple à examiner
par l’opérateur, sans `-fs` pour ne pas demander le téléchargement intégré :

```text
/home/michael/gowin/IDE/bin/gao_analyzer \
  -gao /home/michael/console/tang/impl/console_neo_n56r10_gao_startup/source/tang/boards/neo/startup.gao \
  -series GW5AST -device GW5AST-138C
```

Pour Xvfb, reprendre l’environnement du module toolchain, puis remplacer
seulement DISPLAY par le serveur X isolé et QT_QPA_PLATFORM par `xcb`.

1. Choisir le serveur puis la famille de câble. Le manuel local p39 et la
   fonction `onCableChangedForGvc` affichent `Location:%1,SN:%2`.
2. Choisir l’entrée dont le rattachement à Neo est prouvé. Si SN reste null et
   les locations sont indifférenciées, la GUI n’apporte pas encore la preuve.
3. Avec le bitstream exact déjà chargé et l’attribut initial=true, F1 demande
   la lecture initiale par la branche statique ci-dessus. Ne pas utiliser F2
   (Auto Run) ou F3 (Force) pour cette première lecture.
4. Exporter d’abord le résultat obtenu en CSV et GWD ; la GUI supporte ces
   deux formats. Régler la période à 20 ns. Conserver configuration et SHA.
5. Seulement après archivage ou constat d’absence : F3 peut forcer une capture
   tardive ; F4 arrête l’acquisition. Cette deuxième trace a un autre sens.

L’automatisation graphique et l’échange matériel n’ont pas été testés ici.
Le flux généré N56r10 est de21bits (20sondes plus trigger capturé), pas20bits ;
conserver le décodage officiel/metadata au lieu de supposer un ordre brut.

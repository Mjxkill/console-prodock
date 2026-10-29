# Sélection du programmateur GAO — observation réelle

Commande de découverte seule exécutée sous `TESTS/neo_board.lock`, sans
autre `openocd`, `openFPGALoader`, `gao_sh`, `gao_analyzer` ou `jtagserver`
présent sur l'hôte :

```
/home/michael/gowin/Programmer/bin/programmer_cli --scan-cables
```

Code de sortie0. Résultat exact :

```
 Cable found:  Gowin USB Cable(FT2CH)/0/12401/null (USB location:12401)
 Cable found:  USB Debugger A/1/0/null (USB location:0)
 Cable found:  USB Debugger A/2/0/null (USB location:0)
 Cable found:  USB Debugger A/3/0/null (USB location:0)
 Cost 0.44 second(s)
```

Sur l'hôte : Neo/Sipeed =0403:6010, bus3 périphérique28, série2025041420 ;
ESP-Prog AE350 =0403:6010, bus3 périphérique7, produit `Dual RS232-HS` sans
numéro de série. Aucun scan TAP ni rechargement FPGA effectué par cette
commande. Les résultats ne suffisent pas à sélectionner un port GAO :
12401 pourrait désigner l'ESP-Prog ; il n'est pas accepté comme identité
du programmateur FPGA. Les trois lignes Debugger ont la même location0
et aucun SN. Le manuel SUG502-2.5.1E p45 décrit le premier nombre après
le type comme canal, pas comme location.

La lecture statique de la GUI par l'agent de revue trouve une prise en
compte de la sous-chaîne `Debugger` dans la liste FT2CH. L'absence du nom
complet dans le CLI ne démontre donc pas une incompatibilité générale.
La correspondance exacte entre sélection GAO et matériel reste à établir.

`inspect_gao_gui.py` prépare une inspection dans un écran Xvfb privé, sous
verrou Neo, sans argument bitstream et sans Start/Force automatique. Ce
script ne qualifie pas une capture et ne programme pas le FPGA.

## Inspections GUI réelles

`gui_01` : ouverture privée effectuée, erreur de connexion serveur JTAG.
Le processus GUI et Xvfb ont été arrêtés par le contrôleur ; leur nettoyage
est enregistré. Aucun Start/Force ni téléchargement demandé.

`gui_02` : lancement explicite de
`/home/michael/gowin/Programmer/bin/jtagserver -local` avec son environnement
normal, puis GUI avec les bibliothèques IDE. La connexion locale fonctionne,
mais les familles GWU2X puis FT2CH donnent « No Gowin devices found ».
La liste de location FT2CH reste vide ; aucune correspondance Neo n'est donc
établie. Les captures d'écran et journaux sont conservés dans ce dossier.
Le serveur, la GUI et Xvfb sont arrêtés ; `cleanup.json` et le contrôle des
processus hôte confirment l'absence de sonde résiduelle. La Neo n'a pas été
reprogrammée et aucune lecture GAO n'a été demandée.

La documentation [Sipeed Tang Console](https://wiki.sipeed.com/tangconsole)
recommande le Programmer autonome1.9.12SP1 pour sa compatibilité. La
[page firmware officielle](https://en.wiki.sipeed.com/hardware/en/tang/common-doc/update_debugger)
référence2025041420 pour Tang Console, identique au debugger présent.
Ces sources ne prouvent pas la cause du défaut de sélection de cette
installation et ne justifient pas une mise à jour de firmware à l'aveugle.

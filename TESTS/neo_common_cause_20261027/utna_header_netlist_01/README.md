# UTNA : vérification fonctionnelle des modules synthétisés

Le zéro du mot version observé sur R19 n'est pas reproduit ici : le chemin
synthétisé renvoie bien version1. Cette simulation ciblée n'est pas une preuve
du routage, des délais physiques, du reset réel ou de l'interface AE350/JTAG.

`exact_modules.v` extrait sans modification les modules `usb_idle_trace`,
`ddr_dcfifo` et `ddr_dcfifo_0` du netlist R19. Ces trois modules sont identiques
dans R21r2, comme vérifié dans `../utna_header_zero_review_01/provenance.json`.
Leurs primitives DFFRE/RAM16SDP/LUT utilisent la bibliothèque fonctionnelle
Gowin `Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v`. Le fichier de bibliothèque
porte lui-même l'étiquette1.9.11 ; son SHA est conservé dans `inputs.json`.

- `result.json` : trois couples de périodes/phases passent le protocole
  1/6/2/2 et la version1 ; le témoin négatif du tick final échoue comme attendu.
- `stage_result.json` : trois couples passent en ajoutant le RTL figé
  `video_bus_stage` et une réplique du mux `selected` de l'intégration Neo.
  Toutes les adresses de la banque valent0 avant commande. Un premier
  snapshot2 donne version1 et commande2 alors que le contrôle séquence vaut1.
  Les lectures distinguent donc correctement les deux fenêtres dans ce modèle.

Les deux testbenches sont adaptés du banc de protocole RTL déjà validé.
L'adaptateur relie les ports synthétisés (dont htrans/hsel et le décodage de
la fenêtre2) et expose `hready = !read_pending`. Les entrées UTMI restent
inactives : ce test porte sur le chemin de capture/lecture, pas sur le décodage
de paquets. Les périodes simulées sont des paramètres du test, pas des mesures
de fréquence sur carte. Aucun SDF n'est appliqué.

Les sorties détaillées sont dans `case_*.log` et `stage_*.log`. Les sources,
la bibliothèque, les binaires Icarus/VVP et les résultats sont liés dans
`inputs.json` et `manifest.json`. L'exécutable Icarus disponible localement
est `/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog`, avec
`-B /tmp/console-usb-sim-tools/extracted/usr/lib/x86_64-linux-gnu/ivl`.
L'absence initiale de `iverilog` dans PATH n'est pas un échec du test : la
compilation a ensuite réussi avec ce binaire existant, sans installation.

Aucun fichier de référence ni source RTL n'a été modifié, aucune compilation
FPGA lancée et aucun accès carte effectué. Le critère version1 reste inchangé.

# R22r1 : commande GPU terminée, erreur dans le contrôle de sonde

Analyse hors carte de `combined_gpu_usb_prepared_01/combined_20261028_133840`.
Le résultat matériel original reste **FAIL**, inchangé. Le R19 exact a été
restauré et son état frais contrôlé par root. Aucun FPGA n'est requalifié.

## Défaut démontré du test

Le registre NGDB `+08` expose `host_words` instantané. Le registre `+10`
expose `snapshot[287:256]`, donc le compteur reçu **au dernier snapshot**.
`cv_matrix` relisait ce dernier avant la demande GPU_AFTER_MATRIX : le zéro
était attendu. Le test logiciel initial renvoyait incorrectement la valeur
instantanée à cette adresse et n'a pas détecté l'erreur de la sonde.

| Lecture réelle | séquence | host | reçu | done |
|---|---:|---:|---:|---:|
| GPU_BEFORE | 1 | 0 | 0 | 0 |
| Lectures unitaires après commande, avant snapshot | 1 conservée | 8 | 0 conservé | 1 instantané |
| GPU_AFTER_MATRIX | 2 | 8 | 8 | 1 |
| GPU_FINAL | 3 | 8 | 8 | 1 |

Les trois snapshots GPU ont `mrst=3`, les douze bits `engine_resetn=1`,
`command_bad=command_lost=0` et l'état blitter IDLE. Après la commande,
les pointeurs blitter écriture/lecture sont tous deux 8 et opcode31 est
visible. Ce sont des observations instantanées, pas une preuve permanente
de stabilité des resets ou de validité de toutes les commandes GPU.

## Preuves exécutées

- `analyze.py` vérifie le SHA du résultat source, chaque journal référencé,
  compare les snapshots parsés aux lignes réelles, et réutilise la fonction
  pure de décodage existante. Sortie : `result.json`.
- `run_rtl_test.py` simule le **RTL gelé exact** neo_gpu_debug avec des horloges
  de périodes 10 et 14 ns : reçu reste 0 avant le snapshot puis vaut 8.
  Sortie : `rtl_result.json`, `rtl_1.log`.
- `test_old_controller.py` corrige uniquement le modèle de rétention du
  compteur. Le contrôleur original produit alors le même faux FAIL que la carte.
- `test_snapshot_fix.py` place le snapshot déjà prévu avant la comparaison,
  sans ajouter de demande. Neuf cas passent ; perte réelle, timeout,
  capture bloquée, vidéo figée et version invalide restent des échecs.
  Il ne crée aucun contrôleur matériel et ne modifie pas les scripts figés.

## Ce que l'essai permet de dire

Le trajet testé accepte huit mots hôte, les observe côté GPU et termine une
commande de configuration de matrice. L'hypothèse d'un GPU continuellement
bloqué par son reset n'est pas compatible avec ces observations sur cet essai.
Les quatre échanges UTW1 sont cohérents. Le compteur vidéo avance de 89
images entre T0 et T1200 ; les lectures JTAG prennent du temps en plus des
pauses Tcl, donc cela n'est pas un chronométrage de fréquence.

Le framebuffer était désactivé. Les snapshots scanout indiquent zéro requête
acceptée par la file, zéro acceptée par l'arbitre et zéro donnée retournée.
L'essai ne teste donc pas le chemin DDR d'affichage. Il ne teste aucun rendu
GPU, ni Linux. Le timing global reste en échec.

Aucun périphérique USB de l'identité attendue n'est présent dans l'inventaire
hôte ; aucun transfert hôte n'a été émis. L'observateur UTNA fonctionne dans
son domaine d'horloge, mais cela ne mesure ni sa fréquence, ni les 960 MHz du
PHY, ni la négociation HS. Une cause commune avec le GPU n'est pas établie.

## Prochaine séparation utile, sans nouvelle compilation

1. Conserver cet essai et corriger la sonde dans un nouveau dossier si elle
   doit être réutilisée. Il n'est pas nécessaire de rejouer la même commande
   uniquement pour faire disparaître ce faux FAIL : les snapshots réels
   contiennent déjà le résultat reçu.
2. Côté USB : une lecture non destructive des seuls registres UMSC identité,
   état et version (`e9003000`, `e9003004`, `e9003028`) peut distinguer la vue
   interne online/highspeed du simple inventaire hôte. Ne pas lire +08/+20,
   qui consomment des octets. Ce test reste à préparer et autoriser par root.
3. Côté GPU principal : la prochaine expérience discriminante doit faire
   intervenir un **petit** transfert DDR, avec une zone scratch explicitement
   protégée et contrôlée séparément par CPU puis GPU. La matrice seule n'en
   demande aucun. Ne pas confondre succès de cette configuration et succès du
   rendu ou du scanout. Aucun essai DDR n'est lancé par ce dossier.

La comparaison VO/SDF précédente établit l'identité logique de 85 cellules
du cône ancien de bank_version, mais le nouveau témoin et le mux modifient
réellement charges et trajets. Elle ne démontre ni un défaut silicium FIFO,
ni que seul le placement a changé.

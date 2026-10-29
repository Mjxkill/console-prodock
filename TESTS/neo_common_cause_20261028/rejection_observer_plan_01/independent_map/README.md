# Carte CSR R19 : contre-inventaire indépendant

Lecture seule du VG exact `dfac41d80eec…`, puis des sources figées et du
constructeur. Aucun matériel, nouveau RTL, constructeur ou bitstream. Le
script `inspect_map.py` vérifie les raccordements et publie leurs empreintes.
Il ne constitue pas une preuve d'équivalence de tous les LUT du décodeur.

## Raccordement effectivement présent

Le top synthétisé instancie `neo_gpu_debug_0 u_gpu_debug` (VG ligne1161559).
Ce module contient bien `neo_capture_bus u_capture_bus` (ligne22959), absent
du top RTL initial. Sa sortie remplace `debug_hrdata`; la sortie historique
est renommée `trace_legacy_data`. Le bus de lecture raccordé au helper ne
contient que les bits0..7 de l'adresse. Le port GPU complet reçoit les bits
0..7 et12..14, aucun des bits8..11 : chaque sous-page256B est donc un alias.
L'instance scan `neo_gpu_debug u_scan_debug` n'a pas ce helper NCP.

| Fenêtre canonique | Lecture | Écriture de commande |
|---|---|---|
| E9005000+00..40, pas4 | NGDB : identité, état, host live, séquence, snapshots, mots observés, méta | +04 bit0 demande snapshot historique |
| +44..7C, pas4 | aucun registre historique, zéro au mux décrit | aucune commande actuelle |
| +80 | NCP1, 4E435031 | aucune |
| +84 | état NCP, ready/busy/valid/rejected | bit0 ARM si prêt, sans commande en vol |
| +88 | nombre ARM | bit0 SNAP si prêt, sans commande en vol |
| +8C | séquence snapshot | aucune |
| +90/+94 | shadow64 cohérent | aucune |
| +98 | nombre de heartbeats synchronisés | aucune |
| +9C..FC, pas4 | default zéro du helper NCP | aucune commande actuelle |

Le helper choisit toute la moitié haute avec `read_latched[7]`, y compris
les offsets dont la lecture vaut actuellement zéro. Ajouter un observateur
dans cette moitié doit donc modifier explicitement ce mux existant ; un
second périphérique branché en parallèle pourrait être masqué.

## Alias et limites à conserver

- E9005100,5200…5F00 répètent les mêmes256B : ce ne sont pas des fenêtres
  libres. Le constructeur d'une extension doit conserver ces alias ou
  documenter et tester leur changement. Ne jamais écrire +5184 en pensant
  atteindre une nouvelle commande : il s'agit de l'ARM NCP actuel.
- L'index d'esclave ne dépend que de `haddr[14:12]`. Pour les diagnostics,
  E900D000 répète donc E9005000 dans la fabric. La portée complète du décodage
  amont AE350 n'a pas été redémontrée ici ; utiliser les adresses canoniques.
- La sélection7 n'est pas une page disponible sûre : le mux renvoie le
  scan-debug, mais le RTL ne sélectionne ce dernier que pour la page6.
  Une lecture de page7 peut ainsi présenter une ancienne réponse.
- Le pont EXTS utilise le bit24 pour séparer registres et vidéo. Cette revue
  n'affirme aucun espace global libre hors de l'ABI canonique E900xxxx.
- Le manifeste R19 et son constructeur déclarent `gao:false`; aucun ajout
  GAO n'apparaît dans le Tcl ni aucune instance nommée GAO dans le VO examiné.
  NCP est une instrumentation propre au design, pas un registre GAO caché.

Pour une extension de rejet, une réserve explicite **+A0..FC (24mots)** est
possible dans le mux NCP actuel, avec lecture non destructive et identité de
version distincte. Ce sont des offsets sans fonction dans l'implémentation
actuelle, pas une promesse ABI antérieure. Les captures opérandes/raison
doivent être prises au front causal et gardées jusqu'à une nouvelle capture.
Ne pas remplacer +90/+94 ou les compteurs historiques; conserver le bit0
des commandes +84/+88 et leur refus occupé. Un test exhaustif des256adresses,
des alias et des commandes historiques est nécessaire avant intégration.

Le source `neo_capture_bus.v` décrit le décodage ci-dessus; l'audit vérifie
son raccordement dans le VG final. Il ne remplace ni une simulation de ce
helper synthétisé, ni le contrôle de son délai de lecture après routage.

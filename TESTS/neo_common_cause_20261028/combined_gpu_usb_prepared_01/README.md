# Sonde combinée R22r1, préparée hors carte

État : prête à la revue root, `review_prepared_02.json`, hardware_ready=false.
Aucun matériel n'a été ouvert pendant cette préparation. Bitstream figé R22r1,
aucun nouveau routage. Les contrôleurs précédents sont conservés.

## Séquence réellement exécutée

1. Vérifier l'ancre de restauration B2, les SHA, l'identité Neo et le verrou.
   Vérifier R19 fraîche, CPU garé M-mode et ROM de parking inchangée.
2. Charger exactement R22r1 SHA `55601256…` et contrôler l'état frais.
3. Échantillonner scanout/GPU/NCP à T0, T100, T200 et T1200.
4. ARM UTW1, capture complète initiale avec tags et compteurs stricts.
5. Demander des snapshots NGDB GPU/scan ; si leurs sources sont prêtes,
   envoyer **un seul paquet matrix_row0** (`1f000000,0,65536,0,0,0,0,0`).
   Vérifier host_words/received_words +8, done +1, erreurs/rejets inchangés.
   En cas d'échec de snapshot, ne pas envoyer matrix ; conserver le défaut.
6. Fermer cette session OpenOCD. Lire l'inventaire sysfs de la console USB.
   Aucune ouverture USB si absente, ambiguë, non HS, ou chemin non autorisé.
   Au maximum une requête EP0 de diagnostic de 32 octets, uniquement si
   vitesse 480 et chemin exact lié par la revue root. Aucun reset/detach.
7. Nouvelle session OpenOCD : vérifier CPU et continuité UTNA seq1 ; faire
   DISARM, STOPPED, STABLE, snapshots finaux et lectures vidéo/NCP.
8. Restaurer exactement R19 dans finally, y compris après erreur/signal.

Le contexte de la seconde session est vérifié sans exiger les compteurs GPU
initiaux zéro puisque la commande matrix a pu se terminer. La continuité UTNA
reste stricte. Le contrôleur parent est copié sans changement de sa fonction
execute ; les nouvelles étapes IO ont leurs propres checkpoints de signaux.

Les écritures MMIO sont bornées à `e900200c`, `e9005004`, `e9006004`, `e9001010`.
Il n'y a ni Linux, ni reprise CPU, ni commande de rendu/DMA, ni écriture DDR
explicite. Le RTL gelé `gpu_geometry.v` lignes 269–272 et 307–317 traite opcode31
par mise à jour de la matrice puis FINISH ; les mots réservés valent zéro.
`gpu_accel.v:124` donne status1 = queue_full/busy_sync, donc zéro est l'état
attendu pour le garde idle. Ces intentions ne qualifient pas un matériel défectueux.

## Preuves locales

- 18 cas exécutant le Tcl exact et le décodeur réel sur MMIO simulé : sources
  arrêtées, timeout snapshot, timeout/perte GPU, vidéo immobile, version0,
  capture partielle/continuité invalide, ouverture USB interdite/HS liée.
- 52 injections POSIX héritées, 24 injections de signaux aux nouvelles frontières
  et 8 exceptions : restauration unique, erreurs conservées, aucun matériel.
- Fonction execute identique textuellement au parent éprouvé.
- Préflight final PASS. Toutes les preuves sont liées dans la revue préparée.

Le premier projet de revue a été refusé uniquement parce que le mot `resume`
figurait dans un commentaire du Tcl original. La garde ignore maintenant les
lignes de commentaire et continue à refuser les opérations exécutables interdites.
Les tests finaux sont `tests_local_04`, `signals_03`. Les dossiers précédents
restent des preuves intermédiaires, non les résultats finaux.

## Limites et exploitation

Le timing global reste FAIL : la commande GPU traverse notamment un domaine
avec le chemin busy_sync négatif déjà documenté. La sonde rapporte des faits
pour ce bitstream, elle ne valide ni DDR, ni rendu, ni USB HS complet. Les ticks
UTNA n'établissent pas une fréquence physique, et ne donnent pas les PLL_LOCK.
Les statuts PLL/board sont seulement dans l'EP0 de diagnostic lorsqu'il répond.

Les résultats de chaque domaine sont séparés. Absence USB est un constat
hôte, pas la preuve d'un reset actif. Un échec GPU reste dans combined_errors,
y compris si l'échange UTW1 est cohérent. Version zéro reste FAIL. Une observation
locale réussie conserve qualification_status=FAIL et hardware_qualified=false.

Cette version vise uniquement R22r1 puis restauration R19. Une comparaison des
mêmes nouveaux stimuli sur R19 demanderait un profil explicite, car son ABI UTW1
n'existe pas ; ne pas lancer ce contrôleur en prétendant que R19 est R22r1.

Commande root après copie/relecture de la revue et activation explicite :

```sh
python3 TESTS/neo_common_cause_20261028/combined_gpu_usb_prepared_01/controller.py --check-only --review <root_review.json>
python3 TESTS/neo_common_cause_20261028/combined_gpu_usb_prepared_01/controller.py --run --review <root_review.json>
```

`usb_ep0_allowed_path=null` interdit tout trafic USB généré par ce diagnostic.
Seule la lecture sysfs est effectuée dans ce cas.

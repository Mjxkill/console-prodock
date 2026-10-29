# FC1 — sept fenêtres, retour à FM4A

Préparation hors carte uniquement ; root doit relire le contrôleur et fournir une revue fraîche. Aucun transfert/receiver/FPGA/noyau/SD. Entrée exige la preuve de transfert complet du plan0fe854aa… et la même démoFM4A PID3940/start35705238 encore active.

Les six premières fenêtres sont exactement les argumentsR4, diagnostics désactivés explicitement. La septième reproduit le jardin fixe120images avec LUMA_SUBMIT_DIAG=1. Les premiers chargements restent séparés par le parseur d'origine. Une fenêtre diagnostique n'est pas mélangée avec la mesure normale : les4INFOioctl par lot perturbent le coût. Les deltasfeed/wait/cache sont des temps du pilote, lescyclesgéométrie incluent des attentes internes ; ils ne prouvent pas seuls le débit raster/DDR.

Avant arrêt : identitécomplètePID/startticks/argv/exe, CRChelper/base/cible, progressionGPU sans erreur, noyau/tmpfs,1MiBlibre et noms temporaires neufs. Après arrêt : les deux saves actives FM4A sont relues ; aucune fenêtre n'a d'argument save. À la récupération, mêmes saves exigées avant relanceFM4A et publication atomique de son nouveauPID dans /tmp/fm4live1.pid. La sauvegardeGM1 historique est contrôlée séparément ; GM1 n'est jamais relancé par cette phase.

Le suivi du lancement réutilise le Channel du contrôleur persistent : aucun octet envoyé autorise une restauration directe ; après émission incertaine unPID valide est requis avant de démarrer un autre processusGPU. Unétatinconnuéchoueferméet produit manual_review_required. Les signaux sont différés pendant cleanup. Après succès, le résultat donne la nouvelle ancreFM4A ; lePID3940 ne doit plus être réutilisé.

Tests horscarte : gardesrevue5, scénarios7, gardesdiagnostic7, récupération6 dont avantémission/émissionambiguë/PIDpublié/terminé/savechangée. Les six journauxR4 ont été reparsés par le contrôleur exact. Le transport et les opérationsPID restent les fonctions existantes ; ces tests ne prétendent pas simuler les ordonnanceursLinux sur carte.

Commande root après revue et transfertPASS :
```
python3 -B measure.py --run --expected-manifest MANIFEST_SHA --stage-result TRANSFER_RESULT.json --review ROOT_REVIEW.json --out NEW_RESULT_DIRECTORY
```
Sans --run : lecture/hachage locaux seulement. Nouveau démonstrateur laissé persistant après mesure : opération root distincte utilisant l'ancreFM4A retournée, jamais l'ancienPID.

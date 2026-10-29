# Essai RX2 seul — préparation sans carte

Par défaut `python3 -B trial.py --prepare-only` ne fait que vérifier le paquet.
Root seul exécutera éventuellement `--run --expected-manifest SHA --review
review.json --out NOUVEAU_DOSSIER` sur michael-AX15, après sa revue datée.

Ancre : santé réelle GM1 PID3158/start27508908 du28octobre, sauvegarde inchangée,
G22r0 attesté par continuité et référence externe, même noyau. Port SOFT-USB
explicite, fuser + TIOCEXCL + verrou `/tmp/prodock-diagnostic.lock`. Aucun arrêt,
signal ou lancement du jeu ; aucune écriture FPGA/SD/sauvegarde.

1. Shell ordinaire déjà confirmé par root, nouvelle ligne de contrôle seulement.
2. Identité/save/noyau/tmpfs/GPU/espace lus avant toute création ;32MiB libres.
3. Nouveau `/tmp/luma-rx2-probe1`, création exclusive, bootstrap printf octal
   à2ms/octet. Lecture intégrale `od -b -v`, SHA256 local puis chmod seulement.
   Ancien `/tmp/luma-rx` intact. Pas de readlink/wc/od avancé.
4. Fichiers temporaires neufs :0,513,16384octets ;513octets avec un payload CRC
   faux puis un NACK/retry ;1024octets avec STOP après512, nouvelle invocation
   reprenant à512. Chaque payload relu intégralement et comparé.
5. Après chaque récepteur, attendre son RETURN frais, annuler la ligne, vérifier
   le prompt avant tout texte. Silence/incohérence : attente passive bornée,
   aucune trame d'abandon. Une erreur non résolue exige revue root.
6. Identité/save/GPU/espace relus en cleanup si le shell est confirmé. Aucune
   récupération ne redémarre GM1. Fichiers/logs conservés pour diagnostic.

Le test ne mesure aucun FPS ni transfert de jeu. Un ELF16,6Mo/delta ultérieur
restera une autre opération. Le bootstrap représente environ63Ko de commandes
avec marqueurs et une lecture octale complète ; il prendra quelques minutes
sur la console active. Les mesures QEMU ne prédisent pas son débit matériel.

Une exécution interrompue peut laisser des fichiers partiels. Ne pas rejouer ce
paquet sur les mêmes noms : la création exclusive le refusera. Examiner d'abord
le résultat et préparer de nouveaux noms, sans retirer les preuves précédentes.

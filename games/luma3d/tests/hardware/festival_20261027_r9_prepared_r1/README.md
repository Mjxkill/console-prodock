# Essai Pro Dock Festival R9 préparé — aucun accès matériel effectué

Le contrôleur est `festival_trial.py`. Sans `--run`, il vérifie seulement les
fichiers locaux. L'exécution nécessite une revue root distincte, liée à
l'empreinte complète du manifeste et du contrôleur. Ce dossier ne remplace
ni G22r0, ni GM1, ni une qualification matérielle.

## Identités imposées

- Hôte d'exécution : `ax15`.
- UART : `/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00`.
- Verrou : `/tmp/prodock-diagnostic.lock`, exclusif et non bloquant ; UART
  ouverte avec `exclusive=True` seulement après acquisition du verrou.
- GM1 actif attendu : PID **3158**, startticks **27508908**,
  argv complet `/tmp/luma3d-gm1 --showcase`.
- ELF GM1 : `df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b`.
- Sauvegarde à préserver : `/tmp/op2-live.save`, SHA-256
  `2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6`.
- Noyau : `6.12.112-prodock-luma3d-g3d1-r1`.
- FPGA : continuité **G22r0** explicitement attestée par root, bitstream
  `fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f`.
- Candidat R9 exact : ELF RV32
  `6cdac82bb1b517c9d61680bf6542baec4b5fc586b2b202e8c3cf463615530f50`,
  13 521 232 octets, CRC32 `0c677450`.

L'ancre 3158 provient du résultat final MC1 copié dans `prior_result.json` et
du protocole BG1 `anchor_protocol.json`. Elle n'a pas été relue sur carte dans
cette préparation. Un autre PID/starttime/argv impose une nouvelle revue ; le
contrôleur ne réadopte jamais automatiquement un processus devenu différent.

La continuité G22r0 n'est pas démontrable par le seul identifiant G3D1 de l'IP.
Le contrôleur exige donc cette attestation séparée, puis vérifie réellement le
noyau, l'ABI GPU, l'absence d'erreurs, le scanout et l'identité du processus.

## Séquence et mesures

1. Vérifier intégralement les entrées et la revue avant ouverture de l'UART.
2. Sous verrou, vérifier noyau, `/tmp` en tmpfs, absence de montage SD, GM1,
   sauvegarde, absence d'erreurs et progression du nombre de présentations.
3. Garder GM1 actif pendant les transferts temporaires : helper CRC exact de
   MC1 puis nouveau delta R9. Vérifier le récepteur existant et relire le helper.
   Vérifier les ELF GM1 disque/processus, reconstruire R9 et contrôler ses octets.
4. Relire la même identité GM1 et la sauvegarde immédiatement avant le TERM
   ciblé. Le garde MC1 lie le TERM au PID et au starttime exacts.
5. Exécuter cinq fenêtres de 120 images, une par table et une dans le jardin,
   avec `--manual`, timeout 240 s par fenêtre. Exécuter ensuite 450 images de
   Festival automatique, timeout 600 s. Aucun `--save` ou `--festival-save`.
6. Restaurer GM1 **dans tous les cas**, y compris après succès. Vérifier son
   nouvel argv/PID/starttime, l'ELF, la progression effective et la sauvegarde
   identique. Garder verrou et UART jusqu'à la fin de cette récupération.

Les fenêtres `--manual` mesurent le **rendu au repos** avec son initialisation.
Certaines tables stables n'envoient plus de commandes de dessin après amorçage
des deux pages. Ces valeurs ne sont pas les FPS d'une partie animée. La fenêtre
automatique mesure le Festival global ; sa répartition entre scènes dépend des
FPS réels. Elle ne fournit donc pas non plus de FPS propres à chaque jeu.

Les journaux conservent FPS moyens, commandes, temps de soumission/présentation,
compteurs GPU et fenêtres périodiques disponibles. Le parser exige `hardware=1`,
le nombre d'images demandé, un temps positif, des FPS cohérents, aucun défaut
GPU/scanout et, pour les fenêtres manuelles, le mode demandé inchangé. Aucun
seuil de gain de FPS ou équivalence de compteurs MC1 n'est inventé.

**Aucun contrôle de pixels matériels n'est inclus ici.** Les helpers conservés
permettent des comparaisons ultérieures, mais les fixtures du jardin R9 et les
comparaisons visuelles restent une étape distincte du coordinateur.

## Intégrité du transport

`prodock_transport.py`, les imports transitifs, `build_delta.py`, le helper
host/RV32 et son source sont copiés à l'identique du bundle MC1 revu ; leurs
empreintes sont conservées. Le delta est généré depuis GM1 vers **R9**, pas R8,
puis reconstruit localement par le véritable helper et comparé au SHA-256 R9.
`reconstruction.json` contient cette preuve complète.

Le transport utilise CRC par paquet et sur le fichier complet. Les ELF
distants sont vérifiés par taille/CRC avec le helper, reliés aux SHA-256 locaux
figés ; **aucun SHA-256 ELF calculé sur la carte n'est prétendu**. La sauvegarde
est relue complètement et hachée. Le helper est lui aussi relu intégralement
avant utilisation. Le contrôleur refuse tout Python local non inventorié et
vérifie tous les imports avant leur chargement.

Les fichiers sont uniquement créés dans `/tmp` sur la cible. Aucun chargement
FPGA, noyau, accès JTAG, reset, écriture flash/SD ou modification de sauvegarde
n'est prévu. Le récepteur existant n'est pas remplacé.

## Interruptions et limites de récupération

SIGINT, SIGTERM et SIGHUP sont enregistrés par un handler qui ne lève pas
d'exception. Les points de contrôle arrêtent l'essai ; pendant la récupération,
les signaux supplémentaires restent enregistrés sans interrompre les étapes.
Le transport peut être interrompu à la limite d'un ACK puis abandonné par son
protocole de sortie. Le processus candidat est stoppé via son fichier PID propre,
avec contrôle du nom/starttime ; la référence ne reçoit jamais un kill global.

Une erreur de récupération est conservée séparément de l'erreur initiale.
Si le PID du candidat n'a pas été publié, si l'UART est perdue ou si le processus
ne peut pas être identifié/stoppé, le garde refuse de démarrer un second
utilisateur GPU à l'aveugle. Dans ce cas le résultat reste en échec avec
`cleanup_error` ; aucun reset ou reflash automatique n'est tenté. Une coupure
secteur, SIGKILL ou panne du PC reste hors de portée de ce nettoyage logiciel.

## Revue et exécution ultérieure par root

Vérification locale sans matériel :

```sh
python3 festival_trial.py
python3 test_trial.py
```

Créer **hors de ce bundle** un JSON de revue rempli avec les empreintes finales
mesurées et les valeurs d'identité ci-dessus :

```json
{
  "approved": true,
  "reviewer": "root",
  "manifest_sha256": "empreinte exacte de manifest.json",
  "controller_sha256": "empreinte exacte de festival_trial.py",
  "board": "prodock",
  "expected_identity": {"pid": 3158, "start_ticks": 27508908},
  "fpga": "G22r0",
  "fpga_sha256": "fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f",
  "continuity_confirmed": true,
  "kernel": "6.12.112-prodock-luma3d-g3d1-r1",
  "save_sha256": "2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6"
}
```

Après revue, sur ax15 seulement, avec une sortie encore inexistante :

```sh
python3 festival_trial.py --run --review /chemin/revue-root.json --out /chemin/resultat-neuf
```

Le préparateur n'a exécuté aucune de ces commandes avec `--run` et n'a ouvert
aucun port matériel. Les tests utilisent des backends factices, une vraie
contention de verrou local, et de vrais signaux envoyés au seul processus de test.

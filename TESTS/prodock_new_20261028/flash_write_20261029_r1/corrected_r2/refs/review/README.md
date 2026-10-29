# Préparation flash de la nouvelle Pro Dock — aucune opération carte exécutée

Cible unique : **FT2232 `2025071717`, GW5AST-138B / PG676**, sur ax15.
La Pro Dock `2023112818` et le J-Link `506005083` sont exclus de cette procédure.
Le candidat doit d'abord être essayé en SRAM par root. Le présent dossier ne
qualifie aucun bitstream, aucune flash, ni un démarrage après coupure secteur.

## Ce que les sources établissent

Source locale propre : `/home/michael/openFPGALoader-src`, commit
`24e46d13bb8f2bc9371e9ca8443ece2fafc4b20d`, binaire annoncé `v1.1.1`, SHA-256
`101c3c17456644f08217c3b11103aa78f8ab4debf4d2d133831c9c91c6d6d873`.
Les empreintes des fichiers effectivement lus figurent dans `provenance.json`.
Root a depuis relevé sur ax15 le **même SHA du binaire runtime** et la même
version. Le lanceur `bin/openFPGALoader` a pour SHA
`1c0c245f4bcad2c537b5fbaf77d055c5eccf6b3b17835a24c79be631cd218066` ; il
fixe `LD_LIBRARY_PATH` sur `runtime/lib`, puis exécute `runtime/openFPGALoader`.
Cette association est une mesure communiquée par root, pas une interrogation
effectuée par cet agent. Vérifier les deux SHA avant les opérations.

La documentation officielle annonce la flash externe pour GW5AST-138. La
ligne carte `tangmega138k`, elle, affiche encore Flash « TBD » : le support
logiciel de la famille ne vaut donc pas qualification de notre carte.
[Table FPGA](https://trabucayre.github.io/openFPGALoader/compatibility/fpga.html),
[table cartes](https://trabucayre.github.io/openFPGALoader/compatibility/board.html).

| Source du commit examiné | Constat précis |
|---|---|
| `src/part.hpp`, `src/board.hpp` | ID `0001081b` = GW5AST-138 ; `tangmega138k` utilise FT2232/SPI_FLASH. |
| `src/gowin.cpp:218` | GW5AST sélectionne automatiquement la flash externe. `skip_checksum` vise le checksum USER du FPGA, pas la comparaison SPI. |
| `src/gowin.cpp:342` | `programExtFlash()` efface/programme, puis `SPIFlash::verify(...,256)` si demandé ; une erreur propagée lève une exception. |
| `src/gowin.cpp:100`, `src/rawParser.cpp:19` | `.fs` → `FsParser(false)` ; `.bin` → `RawParser(false)`. Ce dernier copie les octets sans inversion ni en-tête ajouté. Les deux passent le même `getData(),getLength()/8` à la routine SPI. |
| `src/spiFlash.cpp:559` | La vérification SPI relit et compare chaque octet de la plage programmée. Elle ne prouve ni boot, ni fonctionnement Linux/GPU. |
| `src/gowin.cpp:1220` | **Préparer un accès flash efface la SRAM FPGA** sur GW5A. Le retour désactive SPI et réinitialise le FPGA. Détection et dump ont aussi cet effet. |
| `src/main.cpp:678` | Le booléen rendu par `dumpFlash()`/`detect_flash()` n'est pas exploité. Un exit 0 ne suffit pas. |
| `src/spiFlash.cpp:325` | Le dump vérifie les lectures SPI, mais pas les retours `fwrite()` et `fclose()`. D'où taille + SHA + deuxième lecture indépendante. |
| `src/spiFlash.cpp:207` | Effacement arrondi à 4 KiB ou 64 KiB selon le composant. La fin du secteur peut être effacée hors de la longueur du `.fs`. |

Références de code stables :
[Gowin](https://github.com/trabucayre/openFPGALoader/blob/24e46d13bb8f2bc9371e9ca8443ece2fafc4b20d/src/gowin.cpp),
[SPIFlash](https://github.com/trabucayre/openFPGALoader/blob/24e46d13bb8f2bc9371e9ca8443ece2fafc4b20d/src/spiFlash.cpp),
[main](https://github.com/trabucayre/openFPGALoader/blob/24e46d13bb8f2bc9371e9ca8443ece2fafc4b20d/src/main.cpp).

`--skip-reset` ne préserve pas la configuration dans cette implémentation
Gowin. Aucun `--bulk-erase`, `--unprotect-flash` ou accès OTP/security n'est
prévu. Un blocage de protection doit être examiné, pas contourné automatiquement.
La sauvegarde concerne l'espace mémoire SPI ordinaire ; elle ne capture pas
les fusibles, OTP, registres de protection ou registres d'état du composant.

## Séquence proposée à root

1. Finir l'essai SRAM du candidat exact et conserver son SHA et le résultat
   `target_serial=2025071717`, `configuration_completed=true`, `flash_writes=0`.
   Préparer ensuite l'arrêt contrôlé de ce Linux, s'il fonctionne. Tout accès
   flash ci-dessous interrompra cette configuration et pourra recharger le
   programme actuellement en flash. Il ne faut pas lancer le dump pendant une
   mesure ou une écriture SD du candidat.
2. Identifier le binaire ax15 par `sha256sum` et `--version` (pas de JTAG).
   Une version textuelle seule n'établit pas le commit. Conserver aussi son
   `--help` et l'identité du fichier `load_fpga.py` réutilisé.
3. Sous le verrou de diagnostic, détecter la flash de **2025071717**, conserver
   JEDEC/model/status et confirmer sa capacité dans la table `spiFlashdb.hpp`.
   La capacité n'est pas déduite du nom de la carte. Refuser un JEDEC inconnu,
   une erreur de log, un retour non nul ou une incohérence de taille.
4. Faire deux dumps complets indépendants vers deux noms neufs, de la capacité
   exacte. Contrôler les journaux, les tailles, les SHA et leur égalité ; garder
   les deux fichiers et leurs logs hors de la carte. Ne pas déduire le succès
   du seul code retour. Les deux fichiers doivent réellement provenir de deux
   invocations, pas d'une copie locale d'un unique dump.
5. Convertir hors carte le `.fs` **qualifié en SRAM** avec `export_fs`, vérifier
   le SHA `.fs` avant/après. Préparer `program.bin` avec `offline.py` : octets
   du nouveau `.fs` suivis des anciens octets jusqu'à la prochaine frontière
   de 64 KiB. Cela préserve la fin du secteur et les autres données flash.
   Le chemin `.bin` ne refait pas le contrôle IDCODE du `.fs` : vérifier le
   FPGA physique `0001081b` dans les preuves root et maintenir l'identité de
   la carte depuis l'essai SRAM. `raw_route_check` contrôle les deux parseurs
   sur les octets exacts avant programmation, sans JTAG.
6. Faire relire le plan concret : cible, bitstream, outil, JEDEC, capacité,
   sauvegarde, `program.bin` et leurs SHA. Programmer `program.bin` à l'offset
   zéro avec `--write-flash --verify`. Aucun essai automatique de rattrapage
   ne suit un timeout ou une erreur ; conserver l'état et les journaux.
7. Relire **toute** la flash dans un troisième fichier neuf. Comparer au SHA
   attendu par `offline.py verify`, incluant tous les octets hors du payload.
   Cette comparaison indépendante complète le `--verify` interne.
8. Root vérifie ensuite le boot autonome et le jeu. Un reset après programmation
   et une vraie coupure/réalimentation sont deux preuves distinctes. Le collecteur
   `../autoboot_validation/` peut recevoir ces logs ; un ancien marqueur n'est
   pas une nouvelle preuve de boot.

Si la programmation échoue, les dumps bruts permettent de préparer une
restauration **de cette même flash** avec le même ciblage et une vérification
complète. Il n'existe pas de restauration automatique dans ce dossier.

## Commandes exactes à envelopper par le garde

Les formes suivantes sont destinées à root sur ax15, jamais exécutées ici.
`N` est la capacité JEDEC validée en **octets** ; les chemins `NEW_*` doivent
être nouveaux et appartenir au dossier de preuve root. La syntaxe du dump est
documentée dans le [guide officiel](https://trabucayre.github.io/openFPGALoader/guide/advanced.html).

```sh
/home/michael/console-validation-20261001/bin/openFPGALoader --usb-serial-num 2025071717 -b tangmega138k --verbose --write-flash --detect
/home/michael/console-validation-20261001/bin/openFPGALoader --usb-serial-num 2025071717 -b tangmega138k --verbose --dump-flash --file-size N NEW_backup_a.bin
/home/michael/console-validation-20261001/bin/openFPGALoader --usb-serial-num 2025071717 -b tangmega138k --verbose --dump-flash --file-size N NEW_backup_b.bin
/home/michael/console-validation-20261001/bin/openFPGALoader --usb-serial-num 2025071717 -b tangmega138k --verbose --write-flash --verify program.bin
/home/michael/console-validation-20261001/bin/openFPGALoader --usb-serial-num 2025071717 -b tangmega138k --verbose --dump-flash --file-size N NEW_after.bin
```

Ne pas exécuter ces lignes seules en contournant le verrou. `target_guard.py`
fournit un contexte réutilisable, sans CLI matérielle :

```python
from target_guard import guarded_target, command
with guarded_target(tool, tool_sha, reviewed_load_fpga_py, loader_sha,
                    runtime=runtime_path, runtime_sha=runtime_sha) as identity:
    # Le contexte impose michael-AX15, /tmp/prodock-diagnostic.lock exclusif,
    # l'absence d'autres clients JTAG, et réutilise load_fpga.devices().
    # Root conserve identity et lance uniquement l'étape déjà revue.
    argv = command(tool, 'dump', output=new_dump_path, size=capacity)
    # subprocess.run(argv, stdout=exclusive_log, stderr=STDOUT, timeout=...)
```

Ce contexte n'est ni un contrôleur de flash complet ni une validation du
candidat. L'appelant doit conserver le verrou pendant sa phase, vérifier les
fichiers de sortie inexistants et les preuves de la phase précédente. Le
verrou n'empêche pas un programme externe qui l'ignore volontairement.

Commandes locales hors carte :

```sh
./export_fs EXACT_CANDIDATE.fs NEW_payload.bin
python3 -B offline.py prepare --payload NEW_payload.bin --backup-a backup_a.bin --backup-b backup_b.bin --capacity N --out NEW_prepared
./raw_route_check EXACT_CANDIDATE.fs NEW_prepared/program.bin
python3 -B offline.py verify --plan NEW_prepared/plan.json --dump NEW_after.bin
python3 -B test_offline.py -v
```

`export_fs` compile le vrai `FsParser(reverseByte=false)` du commit examiné,
pas une réécriture supposée équivalente. Le `.fs` texte ne se compare pas
directement à un dump SPI. La fixture G22r0 historique, utilisée uniquement
en lecture locale, produit 5 206 528 octets ; **ce n'est pas le candidat SD**.
Le test compare chaque octet à une conversion lexicale indépendante et
vérifie les refus de données invalides et d'écrasement d'un fichier existant.

## État de preuve

11 tests locaux passent : préservation du secteur, contrôle de toute la
flash, corruption hors payload, dumps tronqués/divergents/liens, limites,
sortie exclusive, serial strict, mauvais hôte, vrai parseur et entrée invalide.
Aucun fichier commun, noyau, RTL ou constructeur de carte n'a changé.
Il n'y a donc pas de nouvelle synthèse/régression matérielle revendiquée.

Restent à fournir par root : JEDEC/capacité réelle,
résultat SRAM du nouveau candidat, sauvegardes flash réelles, programmation,
readback intégral, boot autonome, GPU et essai après coupure.

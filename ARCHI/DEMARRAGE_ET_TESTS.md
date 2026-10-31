# Construire, charger et vérifier la console

Procédure d'entrée, revue le **31 octobre 2026**. Les contrats détaillés et
les références protégées restent définis dans
[COMPATIBILITE_CARTES.md](COMPATIBILITE_CARTES.md).

## 1. Identifier le résultat recherché

| Étape | Ce qu'elle établit | Ce qu'elle ne prouve pas |
|---|---|---|
| Compilation | Binaire produit pour les entrées indiquées | Comportement ou timing |
| Simulation / tests hôte | Cas testés, oracles et erreurs détectées | Fonctionnement physique |
| Synthèse / placement / timing | Mapping, contraintes et marges du candidat | Séquence réelle de démarrage ou comportement d'un périphérique externe |
| Essai sur carte | Comportement observé sur ce matériel et cette version | Validation automatique de l'autre carte ou d'une autre version |

Conserver séparément ces résultats. Un build `--candidate` reste un candidat,
même si les tests locaux passent. Une carte éteinte signifie que sa validation
matérielle est en attente.

## 2. Préparer le poste

Les commandes ci-dessous partent de la racine du dépôt. Il faut notamment :

- Python 3, `make`, GCC hôte, `patch`, `curl`, `dtc` et les dépendances des
  scripts de test ;
- le compilateur RISC-V utilisé par le port Linux ;
- les simulateurs et outils exigés par les bancs concernés ;
- Gowin installé avec une licence utilisable pour construire le FPGA complet.

Les versions et archives Linux sont fixées dans
[sources.json](../linux/sources.json) et
[le préparateur U-Boot](../linux/uboot/prepare.py).
La chaîne libre du [Workbench](../optimizer/README.md) complète l'analyse
et les essais de sous-ensembles ; elle ne construit pas encore la console
complète à la place de Gowin.

Ne pas arrêter les compilations d'un autre projet. Utiliser un nom de sortie
nouveau et conserver les manifestes, rapports et erreurs du candidat.

## 3. Tester avant de construire

```sh
# Inventaire des entrées et contrôle des références protégées.
python3 tools/board_contract.py --out TESTS/dual_board/inventaire_local_01.json

# Campagne complète, dans un nouveau dossier à chaque exécution.
python3 tools/run_board_regressions.py --out TESTS/dual_board/verification_locale_01

# Jeu sur le poste : logique, monde, rendu d'une image et référence.
make -C games/luma3d test

# Tests du port Linux ; voir ses prérequis de construction.
make -C linux test
```

La campagne des deux cartes comprend des vérifications AHB/DDR, CDC, USB,
géométrie/pixels, composition, texte, tableau de bord et jeu. Une entrée
modifiée invalide les résultats antérieurs qui la couvrent : relancer la
suite, corriger ou signaler les échecs, sans retirer de tests.

Les tests d'une expérience Neo sur une netlist figée complètent cette
campagne. Ils ne sont pas remplacés par le PASS du code commun.

## 4. Construire les logiciels

```sh
# Paquet Linux Pro Dock candidat.
make -C linux BOARD=prodock BUILD_ARGS=--candidate all JOBS=4

# U-Boot et premier étage SD.
make -C linux/uboot all JOBS=4
make -C linux sd-boot

# Exécutables du jeu, hôte puis RISC-V.
make -C games/luma3d all
make -C games/luma3d riscv
```

Ces commandes construisent les sources publiées. Elles ne reconstruisent
pas implicitement tous les candidats expérimentaux conservés sous
`games/luma3d/candidates/`. Le paquet Linux obtenu n'est pas la sauvegarde
binaire historique de NEBULA R17.

Pour Neo, utiliser le profil documenté dans
[PORT_NEO_720P.md](PORT_NEO_720P.md) et lire les options du constructeur.
Le nom `prodock-*` d'un pilote ne suffit pas à le rendre spécifique à une
carte : [ownership.json](../tang/boards/ownership.json) fait foi.

## 5. Construire et examiner un candidat FPGA

```sh
python3 tools/build_gpu_geometry.py --help
python3 tools/build_console_neo.py --help
```

Les constructeurs Pro Dock exigent `--candidate` lorsque les entrées ont
changé ; tous les nouveaux builds Neo restent candidats. Chaque construction
doit conserver ses sources et leurs empreintes, ses contraintes, sa version
Gowin et son `board_contract.json`.

Examiner ensuite les horloges, resets, contraintes appliquées, traversées de
domaines, mapping et rapports de timing. Un chemin absent du rapport n'est
pas nécessairement un chemin validé. Un timing positif n'explique pas à lui
seul un rejet de commande ou un démarrage manquant.

Les outils `check_*` comprennent **aussi des essais matériels** : leur nom
ne garantit pas un fonctionnement hors carte. Lire leur description et leurs
options avant exécution.

## 6. Chargement : trois opérations différentes

| Opération | Moyen | Effet |
|---|---|---|
| Configurer le FPGA | Programmateur de la carte, bitstream du bon profil | Remplace le système matériel ; SRAM et flash sont distinctes |
| Charger Linux ou un firmware en RAM | Procédure CPU AE350, généralement J-Link | Écrit un logiciel dans les mémoires de la carte ciblée |
| Utiliser le shell et les transferts applicatifs | SOFT-USB / console série du système chargé | Dépend d'un FPGA et d'un logiciel déjà fonctionnels |

Le SOFT-USB n'est pas un substitut universel au J-Link pour le chargement
initial du CPU. Une carte SD ne dispense pas non plus du bitstream et du
premier étage capables de la lire.

Avant chaque essai, associer explicitement le numéro du programmateur, la
sonde CPU, le port série et le SHA-256 du bitstream à la même carte. Les
deux Pro Dock ne doivent pas être choisies par un simple « premier périphérique ».
Respecter le verrou de diagnostic ; une seule session contrôle la carte.

Points d'entrée, **affichage des options uniquement** :

```sh
python3 tools/load_linux.py --help
python3 tools/load_uboot.py --help
python3 tools/neo/load_linux.py --help
```

Les options `--pack`, `--out`, `--build`, `--packed` et les modes de reprise
varient selon le chargeur. Préparer une commande liée au manifeste exact et
à l'état réel du CPU. Ne pas recopier une commande historique C37/USBDISK
pour une Pro Dock G22r0 ou R6 sans vérifier ses préconditions.

### Pro Dock de référence

Préserver G22r0 / NEBULA R17 et les archives listées dans
[reference.json](../tang/boards/prodock/reference.json). Une restauration
utilise ces fichiers exacts ; une recompilation est un nouveau candidat.

### Seconde Pro Dock, démarrage SD R6

Le premier étage, U-Boot, le paquet Linux et la SD doivent appartenir à une
chaîne compatible. Le démarrage a été observé avec le FPGA chargé en SRAM.
Le démarrage autonome après coupure reste à qualifier séparément.
Le noyau actuel de diagnostic et les jeux transférés en RAM ne prouvent
pas que la carte SD contient déjà leurs dernières versions.

### Neo

La carte reste en diagnostic. Sur R19, les commandes TARGET et SCISSOR sont
acceptées et COPY est rejetée, même injectée par le débogueur AHB avec le CPU
**volontairement arrêté**. Ce constat ne démontre ni un arrêt spontané du CPU,
ni une cause DDR, FIFO ou timing. L'observateur S400 doit préciser ce rejet.

## 7. Vérifier sur carte

Le protocole dépend du changement testé : mémoire CPU/GPU, image de référence,
animation, présentation, USB HS, lecture SD, console ou entrées. Prévoir le
résultat attendu avant l'essai, conserver les erreurs et vérifier les zones
de garde lorsqu'une écriture mémoire est impliquée.

Pour une mesure de débit, distinguer volume utile, volume réellement lu,
initialisation, transfert, attente, coût de l'observateur et charge concurrente.
La campagne SD du 31 octobre illustre cette nécessité : CRC corrects, mais
le noyau instrumenté est plus lent même quand le détail du chronométrage est
désactivé. Aucune mesure physique de SCLK n'est encore disponible.

Une fiche de test indique au minimum : objectif, carte, versions et SHA,
état initial, procédure, résultat attendu, résultat observé, journaux,
verdict et limites. Les nouvelles fonctions ne sont déclarées communes
validées qu'après leurs essais propres sur **les deux** plateformes.

Voir [PROJET.md](PROJET.md) pour les résultats récents et
[CLEANUP.md](CLEANUP.md) pour les règles de conservation des preuves.

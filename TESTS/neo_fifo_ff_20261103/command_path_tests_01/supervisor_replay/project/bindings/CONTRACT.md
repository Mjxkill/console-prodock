# Deux stockages de commandes Neo remplacés par des bascules

Cette variante est un choix d’implémentation demandé par Michael. Ce n’est
pas une preuve que le FPGA ou le modèle de FIFO est défectueux. Elle garde
la profondeur, les pointeurs, les resets, les horloges et le protocole existants.
Les lectures NGDB fournies par root montrent `received=32,last_word=1` après
le sentinel : au moins ce mot est arrivé à la sortie de la première FIFO.
Elles ne qualifient pas l’intégrité des autres mots ni de la seconde mémoire.

## Entrée figée et substitutions autorisées

VG : `tang/impl/console_neo_reject_20261102_r1/console_neo.vg`, SHA256
`76d56bd49776d12919c8051f5460bb5e7cadf73fb388ac2bd2cddea63c63b255`.
**Il s’agit du VG avant PNR**, pas des primitives scindées 16 bits du VO.
`MAPPING.json` contient chaque connexion, les six paramètres, le texte de la
cellule et l’identité de son module. Le lexer respecte les identifiants échappés.

| Emplacement | Module propriétaire | Instance locale | CLKA / CLKB | CEA / CEB | RESET |
|---|---|---|---|---|---|
| u_accel.u_commands | ddr_dcfifo_3 | `\g_inferred_storage.mem_g_inferred_storage.mem_0_0_s ` | vid_hclk / gpu_clk | `\g_inferred_storage.mem_10 ` / pop | n249_5 |
| u_accel.u_blitter | blitter | cmem_cmem_0_0_s | gpu_clk / gpu_clk | cmem_5 / VCC | GND |

Chaque instance est un unique SDPB, BIT_WIDTH_0=32, BIT_WIDTH_1=32,
READ_MODE=0, RESET_MODE="SYNC", BLK_SEL_0/1=000. OCE=0 et les sélecteurs
BLKSELA/B=000. ADA/ADB[13:12]=0 ; [11:5] contient les sept bits d’adresse ;
ADA[4:0]=01111, ADB[4:0]=00000. Les quatre octets sont donc écrits ensemble.
La capacité physique SDPB est 512×32 mais **seuls 128×32 sont adressables**
par chacun de ces deux raccordements. Le candidat conserve exactement ces
128 mots : 4096 FF de stockage + 32 FF de sortie par instance, soit
8192 FF de stockage et 64 FF de sortie pour les deux mémoires.

Les spécialisations `ddr_dcfifo_3` et `blitter` ne sont chacune instanciées
qu’une fois dans ce VG ; ce contrôle fait partie de `map_memories.py`.
Tous les autres SDPB, BSRAM, FIFO CPU/USB/DDR, caches et buffers restent intacts.

## Sémantique officielle utilisée

Référence primaire locale : `/home/michael/gowin/IDE/simlib/gw5a/prim_sim.v`,
SHA256 `7db6e9953af24f1233dbc8f58352a1673e91d01bb69656a16ae893a68089f85d`.
Module SDPB à partir de la ligne 1660 ; extrait exact dans `SDPB_REFERENCE.v`.
Les tests utilisent la bibliothèque complète originale, pas une réécriture.
Documentation : **UG300-1.3.6E**, §3.3, pages imprimées 24–27, tables 3-7/8/9,
fichier et empreinte dans MAPPING.json.

- En largeur 32, l’adresse de mot est ADA/ADB[13:5]. ADA[3:0] sont les
  validations d’octets. ADA[4] ne fait pas partie de l’adresse de mot.
- Écriture au front montant CLKA quand CEA et bloc A sélectionné ; chaque
  octet sélectionné reçoit DI. RESET ne bloque pas ce port et n’efface pas
  la mémoire. Les deux instances actives valident les quatre octets.
- READ_MODE=0 est **bypass du registre de pipeline supplémentaire**, pas
  une sortie combinatoire : DO est le registre `bp_reg_sync`, capturé à
  chaque front montant CLKB si CEB et bloc B sélectionné.
- RESET synchrone force DO à zéro au front CLKB, **même si CEB=0**. Sans
  RESET et sans CEB, DO est conservé. OCE ne commande que le pipeline
  inutilisé et n’intervient pas dans DO en READ_MODE=0.
- Aucun INIT_RAM explicite dans ces deux instances ; le modèle SDPB a des
  valeurs initiales par défaut nulles et une sortie initiale nulle. Les FF
  du candidat utilisent INIT=0, sans ajout de clear de la mémoire au reset.
- Le GSR de `console_neo` est relié à VCC. Une assertion GSR en cours de
  fonctionnement n’est **pas** un comportement équivalent des deux stockages :
  le SDPB conserve ses bits mémoire alors que le GSR remet les FF à INIT.
  Le contrat est donc le raccordement exact existant, GSR inactif après
  configuration. Les resets CPU/GPU locaux restent inchangés et sont testés.

## Helper et intégration

`implementation/neo_command_ff128.v` a exactement les ports SDPB et aucun
paramètre. Il instancie explicitement des DFFRE, avec RESET=0 pour les mots,
INIT=0 et CE local décodant la case et l’octet. Le mux de lecture alimente
les 32 DFFRE de DO sur CLKB, RESET prioritaire et CE=CEB. Cette structure ne
doit pas être reconvertie en RAM ; la netlist synthétisée doit être contrôlée.

La substitution autorisée change uniquement le type des deux cellules SDPB
en `neo_command_ff128`, puis retire **leurs six defparam exacts**. Garder
tous les noms d’instances, l’ordre et le texte brut de leurs connexions,
notamment l’espace terminal du nom échappé. Ajouter le helper synthétisé
sans resynthétiser l’application. Le journal inverse doit reconstruire le
VG original octet par octet ; aucun autre port, cellule, assign, paramètre,
contrainte ou réglage de compilation ne peut changer.

Les registres DO ajoutés remplacent les registres de lecture internes du
SDPB : **aucun cycle supplémentaire**. La FIFO asynchrone conserve sa tête
présentée avec `rd_valid`/`rd_ready` et la consommation définie par ses
pointeurs. Il ne s’agit pas d’un changement FWFT/standard. Une future
comparaison avec l’IP FIFO Gowin doit adapter son interface à ce contrat
exact et préserver latence, resets et capacité ; aucune IP n’est générée ici.

## Collisions : borne de la preuve

UG300 §3.3 interdit la lecture et l’écriture simultanées à la même adresse.
Le modèle numérique peut montrer l’ancien mot ; ce résultat n’est pas une
garantie physique de read-during-write. Le banc compare les opérations
définies et conserve explicitement le nombre de sorties de collision exclues.

Pour `u_commands`, le pointeur Gray synchronisé publie les écritures au
lecteur et retarde la réutilisation des cases. Ce mécanisme reste inchangé ;
la simulation du helper ne constitue pas une preuve CDC des pointeurs.
Pour `cmem`, CEB=1 en permanence : à vide, le premier mot écrit peut partager
l’adresse encore lue. La sortie n’est alors pas consommée comme commande :
M_IDLE attend fill>=8 avant M_F0..M_F7. On ne prétend donc pas supprimer ou
interdire toutes les collisions internes de l’ancienne implémentation.
Le remplacement FF a une sémantique numérique déterministe d’ancien mot à
un front commun, mais l’essai matériel reste nécessaire pour comparer les
commandes réellement consommées et les resets, sans attribuer d’avance la cause.

## Preuve attendue et état

1. Inventaire exact + unicité des deux spécialisations + adresses constantes :
   exécuté par map_memories.py, résultat MAPPING.json.
2. Helper RTL contre SDPB officiel **et** scoreboard indexé : tests de tous
   les 128 mots, valeurs variées, CE, reset avec CEB=0, écriture pendant reset,
   clocks proches et déphasées, arrêts d’horloges, même horloge.
3. Contre-tests par mutations : indice de lecture, bits de données, cycle
   supplémentaire, reset mal conditionné et reset qui efface la mémoire.
4. Après synthèse du helper : rejouer le même banc avec son VG ; inventorier
   FF/INIT/CLK/CE/RESET et absence de mémoire. Contrôler l’inversion exacte
   de l’assemblage. Ces étapes sont coordonnées avec l’agent constructeur.
5. Après routage : analyser timing, chemins data/CE/CLK des deux mémoires et
   CDC conservé. Puis essai Neo identifié et comparaison publique/rejet.

Cette livraison ne lance ni synthèse, ni routage, ni matériel. Elle ne
qualifie pas le timing applicatif, le fonctionnement physique des FIFO,
le GPU complet ou la Pro Dock. Les références et sources communes sont intactes.

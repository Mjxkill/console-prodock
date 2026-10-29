# MicroDMA R19 : payload prêt, essai réservé à root

Le binaire exact est `build_01/microdma.bin`, SHA-256
`3180912273bb65ae3b2df2bba48a772f1482033698f2a2b914e355e46a304fa2`.
Il mesure928octets. `listing.txt` contient le désassemblage. Aucun chargeur ni
accès matériel n'est exécuté par ce dossier.

| Ressource | Plage réservée | Usage |
|---|---|---|
| Code ILM | `0xa0004000..0xa000439f` | Instructions RV32 et2paquets GPU, aucune pile |
| Réservation code | `[0xa0004000,0xa0005000)` | Maximum4096octets ; pas de recouvrement journal |
| Journal ILM | `[0xa0006000,0xa0006200)` |128octets header +3images de128octets |
| Scratch DDR | `[0x12000000,0x12000080)` |32stores CPU, puis une écriture GPU32octets |
| Couleur | `[0x12000020,0x12000040)` |16pixels RGB565 `0x6b4d` |
| Canaris | Les96autres octets du scratch | Inclut Z, que CLEAR ne doit pas modifier |

Le scratch est hors anneau réel `[0x20000000,0x40000000)`, établi par les
paramètres ae350_soc/ddr_subsys. Le plan128octets antérieur reste l'autorité
sur les unités byte/mot16/mot32. Aucun accès DDR par `read_memory`, SBA ou
progbuf n'est utilisé pour la comparaison : c'est le CPU qui charge et copie
les données dans le journal ILM.

## Contexte mesuré, puis gardes à répéter

Root a mesuré R19 sansreflash dans
`TESTS/neo_common_cause_20261028/root_cpu_context_board_01/openocd.log` :
PC80000004, ROM10500073/ffdff06f, priv3, satp0, mstatus1800, mie0,
MILMBa0000001, MDLMBa0200001, MCACHE_CTL0, framebufferoff et GPUidle/done0.
L'identité FS R19 est issue de l'ancre de restauration, pas d'une lecture
physique du bitstream : SHA
`1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`.

Avant chargement, root conserve le verrou Neo et vérifie qu'aucune autre sonde
ne travaille, que cette ancre n'a pas été invalidée, que le CPU est toujours
arrêté dans le parking et qu'aucun Linux/payload n'occupe ces réservations.
Il répète les gardes cache/MILMB et protège code+journal contre tout autre
utilisateur. `load_image` et `verify_image` portent uniquement sur le code ILM.
Le journal est initialisé par le programme ; il est relu sur512octets après
arrêt, avec son adresse fixe et son identité MD12/version1.

Le payload revérifie cache==0, MILMB==a0000001, satp0, mie0/MIE0,
GPUidentity/BUSY/FULL/done/errors/lost/rejected0, framebuffer shadow/activeoff
et commit non occupé. Un garde échoué retourne sans store DDR ni commande GPU.
Il modifie mtvec temporairement et le restaure. Il ne modifie ni cache,
mstatus, mie ni satp. **Un trap matériel peut toutefois changer mstatus et
les CSR de trap** ; root les relève et restaure si nécessaire avant toute
reprise. Les registres généraux sont écrasés : seule la ROM de parking est
autorisée ensuite, aucun ancien programme ILM n'est repris.

Le SDK primaire `cache.c` indique que7cc=6 fait WBINVAL_ALL, et `csr.h`
définit MCACHE_CTL7ca/MILMB7c0. Ce payload ne le demande pas : les caches
sont déjà désactivés et un état différent est refusé. Cela évite qu'une
maintenance globale émette une écriture étrangère aux128octets autorisés.

## Séquence et critères

1. CPU : écrire32mots `adresse XOR 0xa5396c17`, fence, relire128octets.
2. Si exact : TARGET22 C12000020/Z12000040,16×1,strides32 ; attendre done1
   et idle, relire128octets inchangés. Ce contrôle n'effectue pas de DMA.
3. Si exact : CLEAR28 couleur seule6b4d,rectangle0/0/16/1 ; attendre done2
   et idle, relire128octets. Couleur32octets exacte,96canaris intacts.
4. Journal result1/phase10 seulement après les3comparaisons de32mots et
   absence d'erreurs GPU ; retourROM80000000. Tout échec saute les phases
   suivantes. Le journal conserve phase, première adresse/attendu/lu,
   nombre d'erreurs, compteurs, trap éventuel et3images CPU.

`decode_journal.py JOURNAL.bin` vérifie toutes les images et compteurs avant
PASS, pas seulement le drapeau. Résultats négatifs :−1garde,−2CPU,
−3attente/erreurTARGET,−4mémoireTARGET,−5attente/erreurCLEAR,−6mémoireCLEAR,
−7trap,−9FIFOcommande. Les détails restent dans le header.

Les boucles sont limitées à50000lectures de statut, mais un seul accès AHB
peut rester bloqué : `video_bus_stage` n'a pas de watchdog interne. Root doit
imposer un délai hôte absolu, arrêter la collecte à son expiration et garder
les preuves partielles. Aucun logiciel de ce dossier ne prétend réparer un
bus bloqué, ni ne lance automatiquement reset ou reflash. Aucune lecture UMSC
n'est incluse, donc aucun rechargement de son watchdog USB par cette sonde.

## Vérification locale

`payload_test_01.json` :10scénarios du binaire RV32 exact exécutés dans un
interpréteur borné : sain, corruption CPU, TARGETtouchantmémoire, deux
timeouts, CLEARabsent, canariécrasé, trap, cacheon et ILMinvalide. Le sain
fait32stores CPU et2paquets GPU ; les négatifs interdisent toute phase aval
inappropriée. Les adresses sont contrôlées à chaque accès du modèle.

Cela valide le contrôle du payload et son empreinte prévue, **pas le cœur
dur AE350, la DDR physique, la STA ou le fonctionnement sur carte**.
Le modèle GPU applique la sémantique TARGET/CLEAR attendue ; le banc RTL
antérieur de next_discriminant contrôle séparément le footprint d'une rafale.
La suite existe pour détecter une faute de programmation ou de décodage,
sans transformer un modèle fonctionnel en preuve matérielle.

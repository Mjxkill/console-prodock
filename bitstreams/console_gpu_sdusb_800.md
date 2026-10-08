# GPU V1 + SD/USB — C22

Archive historique C22 conservée. Les corrections de la revue du 8 octobre
sont qualifiées dans [C37](console_gpu_sdusb_guard_800.md), désormais chargé.

Qualification des 7–8 octobre 2026 sur Tang Mega 138K Pro Dock FPG676,
FTDI 2023112818, PC ax15. Build `gpu_sdusb_c22`.

Cette version conserve tout le GPU V1 et ajoute le matériel SD SPI et le
périphérique USB composite CDC + stockage. Elle corrige les trajets de
reset, les chemins critiques du GPU et les purges USB entre deux horloges.
ORBITAL R6 utilise les mêmes ressources et le même programme téléchargé.

- AE350 800 MHz, AHB 80 MHz, GPU/DDR 75 MHz, LCD 35 MHz ; USB HS 480 Mbit/s.
- Zéro violation setup/hold ; pire marge **+0,009 ns** (GPU), AHB +0,047 ns,
  PHY 120 MHz +0,150 ns. Les fréquences et contraintes temporelles ne sont
  pas abaissées. La marge reste étroite : un nouveau build doit repasser
  l'ensemble du contrôle de timing.
- Audit CDC MSC : 84 trajets Gray et 5 trajets de purge, tous présents et
  sous le budget de 6,25 ns ; maxima respectifs 1,109 et 0,906 ns.
- Trois rechargements SRAM, chaque fois une nouvelle énumération HS,
  1 632 300 octets d'échos binaires exacts ; 300 requêtes EP0 passées.
- Suite GPU complète passée : pixels, profondeur, composition LCD, copies,
  gardes mémoire, 16 couches, 64 sprites, tuiles, affine, perspective et V1.
- SD : 2 × 8 Mio lus, CRC identique, 0,90 Mio/s ; aucune écriture sur la SD.
  Douze interruptions READ10 suivies de BOT Reset donnent toutes la même
  relecture. Zéro timeout, perte ou resynchronisation.
- Disque DDR : 8 Mio écrits à 5,56 Mio/s, relus à 7,14 Mio/s ; CRC32 PC et
  firmware `cef0ebe5`. Les lectures hors capacité sont correctement refusées.

ORBITAL R6 : **51 images de référence exactes**, 520.7 s d'endurance, **28 549 images** (deux boucles complètes), **54.83 images/s**, 3264 octets d'écho USB exacts. Zéro underflow, erreur de dessin ou commande rejetée. Dessin maximal 16.348 ms ; composition maximale 1007/2556 cycles par ligne. Le périphérique USB conserve la même adresse et le mode HS. L'utilisateur confirme C22 : « Oui, correcte et fluide ». ORBITAL reste en lecture automatique.

Occupation de **l'ensemble du FPGA**, pas du GPU isolé :

| Ressource | Utilisée | Disponible | Taux |
|---|---:|---:|---:|
| Logique (LUT + ALU) | 67 603 | 138 240 | 48,90 % |
| Registres | 45 699 | 139 140 | 32,84 % |
| CLS | 49 385 | 69 120 | 71,45 % |
| BSRAM | 251 | 340 | 73,82 % |
| DSP | 83 | 298 | 27,85 % |
| Horloges PRIMARY | 8 | 8 | 100 % |

Firmware GPU incorporé : 63 832 octets ITCM, 29 184 octets BSS.
USBDISK C3 téléchargé : 20 024 octets ILM, 5 664 octets BSS. ORBITAL R6 :
45 056 octets ILM et 5 781 728 octets de ressources DDR.

## Chargement et preuves

SHA-256 : `aacb08e0bca7d8948606cf497b2f2ba113476afd0e23adb80156ef89c7bfdadc`.
Les 121 sources figées sont décrites par le `.sources.json` et conservées
avec les options et audits dans
[`c22_sources.tar.gz`](../TESTS/reprise_20261007/c22_sources.tar.gz).
Le `.validation.json` lie les résultats et leurs empreintes au bitstream.
La référence R31 `console_gpu_v1_800.fs` reste archivée séparément.

Charger le présent `.fs` en SRAM après identification du FTDI 2023112818,
avec `openFPGALoader --busdev-num BUS:DEV -b tangmega138k -m FICHIER.fs`.
Le firmware incorporé propose les commandes GPU historiques. Pour ORBITAL,
lancer ensuite `tools/load_orbital.py --fast --out DOSSIER_NEUF` ; ne pas
utiliser `--reload`, qui restaure spécifiquement R31.

Pour le stockage, télécharger `TESTS/reprise_20261007/usbdisk_c3.bin` via
`tools/load_ilm.py`, entrée `0xa000000c`. Le disque servi est la SD si elle
répond, sinon la DDR ; `d` sélectionne explicitement la DDR et `m` retrouve
la SD, une fois le volume démonté et les transferts terminés. Cette
application remplace ORBITAL dans l'ILM ; les deux ne tournent pas ensemble.

Limites de qualification : les écritures et le retrait physique de la SD
ne sont pas exercés sur carte. À la restitution volontaire du disque, une
commande hôte arrivant exactement au même instant peut demander un reset
BOT de récupération. Aucun démarrage autonome depuis la SD n'est intégré.
La flash n'a pas été modifiée ; les chargements sont volatiles.

[Fiche de reprise et preuves](../TESTS/TESTS_REPRISE_20261007.md) ·
[Contrat SD/USB](../ARCHI/SD_USB_DISQUE.md) ·
[Démo ORBITAL](../assets/orbital/README.md).

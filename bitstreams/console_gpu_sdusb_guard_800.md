# GPU V1 + SD/USB corrigé — C37

Qualifié les 8–9 octobre 2026 sur Tang Mega 138K Pro Dock FPG676,
FTDI 2023112818, PC ax15. Build `gpu_sdusb_c37`.

Cette version conserve le GPU V1 complet et ajoute le garde BOT : une
commande USB invalide bloque EP1 jusqu'au reset hôte. Le firmware USBDISK
R4/C4b vérifie les champs CBW/CDB, le statut final des écritures SD (CMD13)
et les erreurs d'arrêt CMD25. Les chargeurs et le calcul de débit ORBITAL
ont également été corrigés. [Rapport détaillé](../TESTS/CORRECTIONS_REVUE_20261008.md).

- AE350 800 MHz, AHB 80 MHz, GPU/DDR 75 MHz, LCD 35 MHz ; USB HS 480 Mbit/s.
- Zéro violation setup/hold, marge minimale **+0,071 ns**. Contraintes
  d'horloge inchangées ; toute nouvelle compilation doit repasser le timing.
- 166 liaisons de passage d'horloge auditées : 94 MSC, 44 PHY, 12 AHB,
  16 GPU. Les audits numériques ne constituent pas une preuve de MTBF.
- Trois rechargements SRAM avec nouvelle énumération HS, 1 632 300 octets
  exacts, 300 requêtes EP0 et suite GPU complète passés.
- SD : 2 × 8 Mio lus et comparés, CRC `fd8d135d`, environ 0,90 Mio/s ;
  compteur d'écritures resté nul.
- DDR : 8 Mio écrits à 5.58 Mio/s, relus à 7.19 Mio/s ;
  CRC PC/firmware `a8b03134`. Neuf commandes malformées refusées sans
  modification du secteur témoin ; douze reprises READ10 exactes après reset.

ORBITAL R6 : **51 références exactes, 28,546 images en
520.828 s réelles, 54.808924 images/s**. Le compteur passe de
7 à 28553. Échos USB : 3264 octets exacts.
Zéro underflow, erreur ou rejet ; dessin maximal 16.351 ms,
composition maximale 1021/2556 cycles par ligne. La lecture automatique
est relancée et acquittée après le test. Vérification automatique du rendu ;
aucune nouvelle confirmation visuelle humaine n'a été demandée pour C37.

Occupation de l'ensemble du FPGA, pas du GPU isolé :

| Ressource | Utilisée | Disponible | Taux |
|---|---:|---:|---:|
| Logique (LUT + ALU) | 68088 | 138240 | 49.25 % |
| Registres | 45894 | 139140 | 32.98 % |
| CLS | 49690 | 69120 | 71.89 % |
| BSRAM | 251 | 340 | 73.82 % |
| DSP | 83 | 298 | 27.85 % |
| Horloges PRIMARY | 8 | 8 | 100.00 % |

## Chargement et preuves

SHA-256 : `6f47a8cdab5857a0b652f791ff61fbed9a26c3c7ba7f4f30de01da95f0c076e2`.
Les 125 fichiers figés, la netlist de synthèse et la référence de
placement incrémental sont archivés dans
[`c37_sources.tar.gz`](../TESTS/corrections_20261008/c37_sources.tar.gz).
Le `.validation.json` relie les preuves au bitstream. La référence historique
[C22](console_gpu_sdusb_800.md) est conservée avec son empreinte initiale.

Charger ce `.fs` en SRAM après identification du FTDI 2023112818 :
`openFPGALoader --busdev-num BUS:DEV -b tangmega138k -m FICHIER.fs`.
Le firmware incorporé reste le programme de diagnostic GPU. Pour ORBITAL,
lancer `tools/load_orbital.py --out DOSSIER_NEUF` sur ax15, sans `--reload`
(cette option restaure R31). Les ressources sont téléchargées et relues.

Pour le stockage, utiliser
[`usbdisk_c4b.bin`](../TESTS/corrections_20261008/usbdisk_c4b.bin) avec
`tools/load_ilm.py --bin FICHIER.bin --entry 0xa000000c --expect 'USBDISK READY' --out DOSSIER_NEUF`.
Ce firmware fait 20 304 octets et exige ABI=1 du garde matériel. Il sert la
SD si elle répond, sinon la DDR ; `d` sélectionne la DDR et `m` la SD, après
arrêt des transferts et démontage du volume. USBDISK remplace ORBITAL dans
l'ILM ; les deux applications ne tournent pas ensemble.

## Limites restantes

- Écritures et retrait physique SD non testés sur carte ; erreurs de programmation validées en modèle.
- Restitution volontaire du disque simultanée à un CBW : reset BOT parfois nécessaire.
- Attentes MMIO du contrôleur SPI non bornées si le périphérique matériel se bloque.
- Qualification numérique et essais bornés ; aucune preuve analogique de MTBF.
- Chargements SRAM/ILM/DDR volatiles ; ORBITAL et USBDISK sont des applications ILM distinctes.

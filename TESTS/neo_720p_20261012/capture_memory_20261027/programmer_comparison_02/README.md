# Comparaison de programmation R19 / R21, hors carte

`analysis.json` est produit par `../analyze_programmers.py`. Aucun FPGA
n'a été programmé. Les conversions officielles utilisent `--svfcreate` ;
leur trace système ne contient aucune ouverture USB ou UART. La première
tentative sous sandbox a échoué sur ptrace avant lancement du programme et
reste dans `../programmer_comparison_01/`.

Les FS ciblent GW5AST-138C / PG484, outil V1.9.12.03 (86714), CRC ON,
Compress OFF, Encryption OFF, SecurityBit ON et LoadingRate 2,5 MHz. Les
seules différences d'en-tête sont CheckSum, UserCode et date.

| Mesure | R19 | R21r1 |
|---|---:|---:|
| CheckSum/UserCode annoncé dans le FS | `4CB0` | `D1F6` |
| Somme FsParser calculée et journalisée au chargement | `3395` | `80D4` |
| Bits du FS brut transférables | 42 160 128 | 42 138 720 |
| Dernier morceau openFPGALoader en bits | 217 088 | 195 680 |
| Trames de configuration principales | 21 872 | 21 872 |

Toutes les lignes sont binaires et alignées à l'octet. Aucun fichier ne
finit sur la frontière exacte de 524 288 bits ; la condition finale
`remains < chunk` prend la même branche dans les deux cas.

R19 a une ligne de 21 904 bits commençant par 0x98 entre le bloc principal
et les lignes de 496 bits. R21 n'a pas cette ligne mais possède une ligne
de 496 bits supplémentaire. La signification de cette différence n'est
pas déduite sans documentation.

## Séquences

Le binaire openFPGALoader utilisé est identique au binaire local de build,
SHA `101c3c17456644f08217c3b11103aa78f8ab4debf4d2d133831c9c91c6d6d873`.
L'arbre source propre est au commit `24e46d13bb8f2bc9371e9ca8443ece2fafc4b20d`.

- `gowin.cpp:384` : reset/reload GW5, un million de TCK, effacement SRAM,
  transfert. `checkCRC()` est désactivé pour GW5.
- `gowin.cpp:778` : CONFIG_ENABLE, INIT_ADDR, XFER_WRITE 0x17, tous les
  octets du FS brut, puis 0x0A avec la somme recalculée, 0x08,
  CONFIG_DISABLE, NOOP et lecture du statut DONE.
- `fsparser.cpp` remplit le buffer transféré avec toutes les lignes avant
  de réduire sa copie de travail pour le calcul de somme. Cette réduction
  ne tronque donc pas le transfert SRAM.
- Le SVF officiel V1.9.12.03 (2712) utilise 0x3B et des SDR de 1 513 bits,
  puis 0x0A avec le UserCode du FS, 0x08, CONFIG_DISABLE, NOOP et contrôle
  statut `TDO=6020, MASK=602F`. Son préambule comporte des attentes plus
  longues et la commande 0x3F.

Ces différences ne prouvent pas un défaut du loader : R19 fonctionne avec
le même code et les deux chemins n'ont pas été comparés sur carte. DONE
ne constitue pas une relecture complète de SRAM.

Le guide officiel local **UG704-1.0.7E**, fig. 3-12 p.22, décrit exactement
le transfert `0x15 → 0x12 → 0x17 → bitstream MSB → 0x3A → 0x02` employé
par openFPGALoader. Le terme « brut » de son buffer ne doit donc pas être
confondu avec le mode CLI 16 nommé JTAG 1149.

Le même guide §4.3-4.4 p.51-52 précise que le **CRC matériel par segment**
reste contrôlé pendant le chargement ; une erreur empêche normalement DONE.
`skip_checksum` dans openFPGALoader omet sa comparaison logicielle finale,
pas le CRC matériel transporté dans le FS. Le guide confirme également que
SecurityBit ON empêche le readback SRAM après configuration. Le texte extrait
est `UG704_107E.txt`; l'original local est
`/home/michael/gowin/Programmer/doc/EN/UG704-1.0.7E_Arora Ⅴ 138K&75K FPGA Product Programming and Configuration Guide.pdf`.

## Limites et essai discriminant éventuel

Les conversions hors ligne en opérations 2 et 16 produisent des fichiers
identiques pour chaque FS. Elles ne prouvent pas l'identité des chemins
live. Le guide SUG502-2.5.1E §4.7 réserve l'opération 16 aux fichiers sans
CRC/chiffrement/compression ; nos FS CRC ON ne doivent pas utiliser ce mode.

Le SVF comporte 21 873 SDR longs pour R19 et 21 872 pour R21, sans séquence
séparée identifiée pour les lignes de 496 bits. Il n'est pas proposé comme
chargeur de remplacement : sa fidélité aux initialisations mémoire n'est
pas établie. Un contrôle officiel éventuel doit employer directement le FS
en mode SRAM 2, après identification du câble et revue parent.

Le contrôle supplémentaire `vendor_svf_frame_mapping` dans `analysis.json`
compare les 21 872 lignes principales bit par bit dans chaque build : zéro
écart, selon `SDR1513 LSB-first = FS1584[7:-64]`. Le SDR supplémentaire R19
correspond à la ligne FS 21911 de 21 904 bits, à l'offset 20 327, soit les
1 513 bits précédant ses 64 bits finaux. Ce constat n'attribue pas encore
une sémantique à la commande 0x98 et ne décrit pas le programmeur live.

La liste des opérations GW5AST du guide ne promet pas SRAM Program-and-Verify.
Le changement d'outil ne prouve pas une relecture complète. Aucune option
SecurityBit ou CRC n'a été changée.

Un essai discriminant éventuel comparerait le même FS en mode officiel 2
et avec openFPGALoader à la même fréquence. Changer outil et fréquence
simultanément sans témoin empêcherait l'attribution. Aucun essai lancé ici.

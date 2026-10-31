# SD en SPI : mode High Speed et diagnostic du débit

Analyse des sources du **31 octobre 2026**, sans modification de pilote ni
nouvel essai matériel. Ne pas confondre le mode SD High Speed avec USB
SuperSpeed, ni SDHC (capacité/adressage) avec un réglage de débit.

## Ce que prévoit le protocole

La commande **CMD6 / SWITCH_FUNC** permet d'interroger les fonctions de la
carte, puis de sélectionner High Speed dans le groupe des modes d'accès.
Il faut vérifier le support et le résultat du changement avant d'augmenter
l'horloge. Cette sélection appartient à l'initialisation, pas à chaque
lecture de secteur. Ce n'est pas ACMD6, qui sélectionne la largeur du bus SD.

La spécification SD Physical Layer v6.00, §7.2.13 et §7.2.14, prévoit CMD6
et High Speed en SPI. Les plafonds du mode standard et du mode High Speed
sont respectivement 25 et 50 MHz, sous réserve des capacités de la carte et
des contraintes électriques de l'hôte. Voir le
[texte de la SD Association, copie consultée, page 216](https://www.taterli.com/wp-content/uploads/2017/05/Physical-Layer-Simplified-SpecificationV6.0.pdf#page=234).

Une ancienne documentation de carte peut ne pas supporter ce mode ; ce
n'est pas une raison pour généraliser cette restriction à toutes les SD.
Les modes UHS et leurs débits sur bus SD natif ne sont pas une promesse de
débit pour notre liaison SPI.

## Configuration trouvée dans le projet

| Élément | Constat dans les sources |
|---|---|
| Device tree Linux | `spi-max-frequency = <20000000>` ; pas de `cap-sd-highspeed` |
| Contrôleur SPI Linux | `max_speed_hz = 20000000` |
| Pilote amont `of_mmc_spi` | Ajoute `MMC_CAP_SD_HIGHSPEED` si la propriété `cap-sd-highspeed` est présente |
| Cœur MMC Linux `mmc_sd_switch_hs` | Ne sélectionne pas High Speed sans cette capacité hôte et le support carte |
| Device tree U-Boot | SPI limité à 20 MHz |
| Contrôleur SPI U-Boot | Plafond supplémentaire à 20 MHz dans `set_speed` |
| Cœur MMC U-Boot utilisé | Le chemin SPI quitte la sélection des modes en restant `MMC_LEGACY` |

Sources publiées : [device tree Linux](../linux/prodock-linux.dts),
[pilote SPI Linux](../linux/drivers/prodock-spi.c),
[device tree U-Boot](../linux/uboot/overlay/arch/riscv/dts/prodock-console.dts),
[pilote SPI U-Boot](../linux/uboot/overlay/drivers/spi/prodock_spi.c).

Le contrôle des sources amont a porté sur :

- `games/luma3d/candidates/mmc_latency_20261031_r1/build_01/source/drivers/mmc/core/sd.c` ;
- `drivers/mmc/host/mmc_spi.c` et `of_mmc_spi.c` du même arbre ;
- `linux/build/uboot/src/drivers/mmc/mmc.c` et `mmc_spi.c`, U-Boot 2025.10.

Ces constats sont une lecture du code. Ils ne constituent pas une capture
de CMD6 sur la carte actuellement branchée ni une mesure de SCLK.

## Pourquoi cela ne suffit pas à expliquer la lenteur

À **20 MHz**, sérialiser 64 Kio sur un fil prend :

```text
65536 × 8 / 20000000 = 26,2144 ms
```

C'est le temps des données seules : commandes, jetons, CRC, attente carte
et interruptions d'horloge s'ajoutent. Les observations de l'ordre de
0,91 à 1,47 s restent très éloignées de ce plancher. Le passage à High Speed
autorise une horloge supérieure ; il ne prouve pas que ces délais disparaîtront.

Le calcul actuel du diviseur est `SCLK = 80 MHz / (2 × N)`. Avec cette
configuration, le palier supérieur à 20 MHz serait **40 MHz**, pas 50 MHz.
Cela reste à qualifier sur les broches et avec la carte, même après
acceptation de CMD6. À 40 MHz, les données seules prendraient 13,1072 ms.

## Prochaine mesure discriminante

Conserver d'abord une référence à 20 MHz : mode/capacités carte, fréquence
demandée, registre diviseur, fréquence physique si observable, temps de
commande à premier jeton et temps de transfert des 512 octets. Séparer les
pauses entre octets, entre blocs et le coût des mesures.

Un essai High Speed ultérieur doit contrôler CMD6 et sa réponse, modifier
les plafonds cohérents de l'hôte, puis comparer les mêmes secteurs et CRC.
Linux et U-Boot doivent être testés séparément. Ne pas annoncer le mode
actif sur la seule présence d'une option dans le device tree.

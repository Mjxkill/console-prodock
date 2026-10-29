# Modifier une initialisation ROM après routage — recherche du 29 octobre 2026

**Une procédure Gowin existe, mais son application directe au G22/AE350
n'est pas établie.** `merge_bit.exe` remplace le logiciel dans un bitstream
matériel figé. Les guides officiels PicoRV32 et EMPU_M1 le décrivent ; EMPU_M1
inclut GW5A/T/ST/S-138 dans sa liste. Cela prouve le support de la famille,
pas celui du mapping AE350 utilisé ici. Aucun outil Gowin n'a été exécuté,
aucun bitstream modifié, aucune compilation ni opération carte effectuée.

## Commandes réellement documentées

```text
merge_bit.exe bin-file fs-file itcm_size posp-file
```

Syntaxe positionnelle, sans options inventées. `itcm_size` est en Ko (64
pour64Kio), `bin-file` le logiciel, `fs-file` le bitstream initial, `posp-file`
le placement BSRAM produit avec le design. Le guide indique de garder ce
matériel figé et de refaire seulement la fusion quand seul le logiciel change.
Référence : [IPUG913-1.8E](https://www.gowinsemi.com/upload/database_doc/873/document/68dc3bf6ea8f4.pdf),
§3.1–3.3, pages imprimées7–8 (PDF14–15), §3.6 p11 (PDF18).
[IPUG532-2.5E](https://cdn.gowinsemi.com.cn/IPUG532E.pdf), §3 p7–9, confirme
la procédure et la liste comprenant GW5A/T/ST/S-138. Le binaire documenté
est `tool/merge_bit/bin/merge_bit.exe`, distinct des exécutables IDE.
Aucun binaire merge_bit trouvé dans les répertoires IDE/SDK examinés.

```tcl
set_option -gen_posp 1
```

SUG1220-2.0E p33 (PDF40) décrit la génération du `.posp` **par le PNR** ;
il contient seulement le placement BSRAM. Aucune commande documentée
trouvée dans ce guide pour l'extraire d'un `.pr` existant sans PNR.
`run` n'y propose que `syn`, `pnr`, `all` (p16–17).
`-bit_incl_bsram_init` et `-bsram_init_print_mode` (p51–52) contrôlent
l'inclusion des valeurs d'initialisation lors de la génération ; ce ne sont
pas des commandes documentées de remplacement après routage.
SUG100-4.4.6E p65–67 décrit l'éditeur `.mi`, destiné à la génération IP,
et p43–44 les options CRC/initialisation. Son bouton Update modifie le
contenu de l'éditeur, pas un bitstream routé.

## Pourquoi ce n'est pas encore une recette valable pour G22

- Le `.posp` manque dans le dossier G22 **et dans son archive de référence**.
  `build.tcl` n'activait pas `-gen_posp`. `.p`, `.pr`, `.db`, `.vo`, `.fs`
  existent, mais aucune équivalence documentaire entre ces fichiers et
  l'entrée `.posp` de merge_bit n'a été établie.
- G22 active `AE350_EMB_ITCM_EN`, `ITCM_SIZE14`. Sa netlist contient32SP,
  tous `BIT_WIDTH=1`, adressés par ILMADDR[15:2] : organisation64Kio en plans
  de bits. Les noms sont `u_gw_itcm/u_vc_ilm_ram/memA_memA_0_N_s`.
  Le logiciel20936octets tient dans cette capacité ; cela ne valide pas le
  mapping de fusion ni le firmware. Preuve exacte : `g22_inventory.json`.
- [MUG1031-1.3.1E](https://www.gowinsemi.com/upload/database_doc/2725/document_ja/69811021aaeed.pdf)
  §8.2.2 p30–32 (PDF38–40) décrit AE350 avec quatre fichiers `itcm0`…`itcm3`
  générés par `example/Emb_TCM/tool/make_hex`. Ce flux initialise l'IP.
  Aucune procédure merge_bit AE350 trouvée dans ce manuel. Le SDK local
  fournit make_hex.exe/ReadMe Windows ; cela ne prouve pas un outil de
  remplacement après routage.
- La documentation examinée ne précise pas comment merge_bit reconnaît
  ces noms/ce mapping AE350 ni les contraintes exactes CRC/compression de
  ce G22. L'option CRC de l'IDE ne constitue pas une spécification suffisante
  pour recalculer soi-même le bitstream.

## Conclusion exploitable

Demander à Gowin la variante de merge_bit validée pour AE350/GW5AST-138B
et la méthode officielle d'extraction du placement BSRAM du `.pr` G22 déjà
routé. Fournir le nom hiérarchique et la largeur1bit ci-dessus. Si cette
méthode existe, la première validation devra être une fusion sans changement
sur copie isolée, puis une preuve que seules les initialisations visées et
les contrôles associés changent. Le SHA protégé G22 reste
`fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f`.

**À ce stade : méthode officielle générale confirmée ; procédure sans
reroutage applicable à cet AE350/G22 non démontrée.** Aucune promesse de
compatibilité à partir du seul numéro de FPGA. Les chemins, empreintes et
pages sont consignés dans sources.json/page_index.json ; la contrelecture
Beam est conservée séparément, sans autorité de qualification matérielle.

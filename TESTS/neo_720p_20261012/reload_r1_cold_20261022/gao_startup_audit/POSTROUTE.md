# N56r10 GAO : audit des sorties terminées

**Qualification FAIL ; insertion physique intégralement vérifiée : non.**
Le [résultat indépendant](postroute_result.json), SHA
`823e84070891b920e7e0bf5663189748a6f442e06f8fdc79bfcea152f204566e`,
conserve les identités avant/après lecture. Aucun matériel, constructeur ou
fichier du candidat n'a été modifié par cet audit.

Le bitstream natif est `impl/pnr/ao_0.fs`, SHA
`7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28`.
Son en-tête déclare le bon FPGA et `GAOCRC: 0101011010100000`.
Root a conservé le premier refus du qualificateur pour absence de
`console_neo.fs`, puis créé une copie exacte sous ce nom, avec provenance.
Les dix audits applicatifs du parent sont tous présents dans la qualification.

| Timing | R9 | R10 GAO |
|---|---:|---:|
| Setup | −0,849 ns | −0,849 ns |
| Hold | +0,124 ns | **−0,384 ns** |
| Recovery | −0,360 ns | −0,364 ns |
| Removal | +0,196 ns | +0,196 ns |

Les 13 violations hold ajoutées appartiennent au domaine JTAG `tck_pad_i`
contraint à20MHz, TNS−2,020ns. Elles ne concernent pas l'horloge d'échantillonnage
`clk50`. Les [treize lignes structurées](gao_hold_paths.json) et leurs
[chemins détaillés](gao_hold_paths.txt) sont conservés intégralement.

| Départ → arrivée dans GAO | Front départ/arrivée | Slack ns |
|---|---|---:|
| icon `enable_reg_1` → `enable_reg_0/D` | F/F | −0,384 |
| `address_counter_4` → RAM4 `ADB[6]` | R/R | −0,348 |
| `address_counter_4` → RAM1 `ADB[6]` | R/R | −0,342 |
| `address_counter_4` → RAM2 `ADB[6]` | R/R | −0,194 |
| `address_counter_4` → RAM3 `ADB[6]` | R/R | −0,178 |
| `address_counter_6` → RAM4 `ADB[8]` | R/R | −0,151 |
| `data_register_35` → `internal_register_select_14/D` | R/R | −0,083 |
| `operation_2` → RAM4 `CEB` | R/R | −0,081 |
| `data_register_34` → `internal_register_select_13/D` | R/R | −0,072 |
| `address_counter_5` → RAM4 `ADB[7]` | R/R | −0,065 |
| `address_counter_2` → RAM4 `ADB[4]` | R/R | −0,052 |
| `address_counter_6` → RAM2 `ADB[8]` | R/R | −0,051 |
| `address_counter_9` → RAM1 `ADB[11]` | R/R | −0,018 |

La cause STA locale est une arrivée des données trop précoce par rapport à
l'horloge de capture : par exemple le premier chemin affiche skew−0,956ns
et délai données0,539ns. La contrainte concerne deux fronts de même sens :
ralentir TCK ne suffit pas à démontrer une correction de hold. Les neuf
chemins vers `ADB` concernent l'adressage de lecture BSRAM par JTAG, un autre
touche son activation `CEB`, deux les registres de sélection et le pire le
contrôleur de sélection du cœur. Ils limitent la confiance dans une future
lecture de capture ; une éventuelle corruption matérielle n'a pas été mesurée.

Le manuel fournisseur SUG114-3.4.4E p24, conservé dans
[gao_manual.txt](../gao_cli_research/gao_manual.txt), lignes1039–1043, indique
que `Force Trigger by Falling Edge` déplace certains registres internes
pilotés par TCK vers le front descendant pour améliorer leur timing.
L'option actuelle est fausse. Un candidat séparé avec cette unique option
serait une expérience pertinente pour les douze chemins R/R, **sans garantie**
sur les registres réellement changés ni sur le chemin F/F déjà défaillant.
Le futur résultat devra montrer les fronts des treize chemins, toutes les
marges, les contrôles d'origine et les changements physiques applicatifs.
Aucune option n'a été modifiée ici ; aucune contrainte n'est relâchée.

Les vingt sondes et `clk_d` sont raccordés dans les sources GAO générées,
dont le SHA est bien celui consommé par `cmd.do`. Le rapport final chiffre
le GAO à567logiques (552LUT+15ALU),354registres et6BSRAM, contre556LUT dans
la synthèse initiale. Les rapports distinguent ces ressources de celles de
l'application ; ce chiffre ne mesure pas leur effet sur le routage.

Le VO public est **exactement identique à R9 après le seul en-tête de date**,
SHA du corps `d19f300292b1727cbb569b67680f3fec1c1d90f3e7f037c23d3c44fa81f48cec`.
Les primitives, paramètres, INIT et connexions applicatives, y compris la
chaîne PLL/reset/AE350, sont donc conservés. Mais le VO et le SDF excluent
les primitives GAO. Les fichiers P/PR sont protégés et le DB binaire ; leurs
internes n'ont pas été déchiffrés ni devinés.

Le [TR expose cinq chemins de données](capture_path_witnesses.txt) :
`vid_hrstn`, les deux `ae350_rst_sync`, `u_soc/init_sync[0]`, `soc_dbg[0]`,
aux bits8,14,13,12,11 attendus. Il expose aussi `ddr_init` vers le registre
du comparateur de trigger. Tous ces récepteurs sont cadencés par
`clk_ibuf/O` → `clk50`, indépendamment de l'horloge CPU/DDR. Les quinze
autres chemins de données ne figurent pas dans les chemins limités du TR :
leurs raccordements générés sont prouvés, leur terminaison physique complète
reste non vérifiée indépendamment. La disposition brute mémoire21bits n'est
pas extrapolée depuis ces cinq témoins.

Les avertissements PR1014 `clk_d` et `ae350_tck_d` existaient déjà sur R9 ;
R10 les imprime deux fois. Les tables globales et localisations sont
identiques, avec huit PRIMARY et sept LW. Le nouveau FAIL
`timing_closure` pour les huit PRIMARY prétendument absents vient du parseur
qui impose la section6 : le tableau GAO supplémentaire la décale à7.
`gpu_reset_tree` présente le même problème de section et ne doit pas être
considéré corrigé par cette absence de lecture : le reset4 reste bien LW
dans le tableau réel. La qualification initiale et ces erreurs sont conservées.

L'égalité du VO ne signifie pas égalité des délais : le
[diff SDF complet](application_sdf_delta.json) contient5 467arcs applicatifs
modifiés, tous avec les mêmes extrémités. Les IOPATH et timingchecks des
primitives sont identiques. Sur52branches du80MHz, le maximum augmente
d'environ0,372–0,373ns ; sur4 586branches du75MHz, d'environ0,436–0,437ns.
Les sondes de reset/lock ajoutent généralement quelques picosecondes aux
délais rapportés. Ces différences sont des délais de connexion et ne sont
ni des slacks complets ni une preuve de cause du défaut de démarrage R9.

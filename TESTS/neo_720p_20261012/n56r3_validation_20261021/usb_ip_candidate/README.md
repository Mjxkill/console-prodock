# Préparation USB HS Neo isolée

Aucune synthèse ni génération d'IP n'a été exécutée. Les fichiers dans
`prepared/` sont des copies officielles et des configurations XML à relire.
R4 conserve intégralement ses anciennes IP pendant son expérience GPU.

Manifeste préparé : `prepared/manifest.json`, SHA-256
`16c9e83657994df6a206998f17ce38ab7ae3cf3bb6ebd2d1a6264a8231aa01e1`.

- USB Device Controller **3.3**, High Speed, UTMI, descripteur64, même
  SELFPOWERED et mêmes quinze endpoints IN/OUT bulk que G22r0.
- USB SoftPHY **3.5**, UTMI, GW5AT, TX_DELAY_0_BIT, mode **V_120** comme G22r0.
- Cible XML : **GW5AST-138C / PBGA484A / GW5AST-LV138PG484AC1/I0**,
  identique au projet de synthèse Neo N56.
- Sources vendor du Gowin V1.9.12.03 installé : les six fichiers sont
  identiques octet par octet aux entrées archivées C28. Les macros sont
  identiques à celles de C28 **et** de G22r0.
- Options de synthèse et outil repris de `tools/build_gpu.py` et des XML
  C28 ; seuls cible et chemins locaux sont adaptés. Le contournement
  FreeType reste limité à l'environnement de chaque sous-processus.

Après revue seulement :

```sh
python3 TESTS/neo_720p_20261012/n56r3_validation_20261021/usb_ip_candidate/generate_usb_neo.py --generate-reviewed 16c9e83657994df6a206998f17ce38ab7ae3cf3bb6ebd2d1a6264a8231aa01e1
```

Cette commande vérifie l'intégrité du manifeste, des sources, de l'outil,
des macros et des XML ; réexécute la garde commune ; puis synthétise les
deux IP successivement dans `generated/`. Elle exige la fin normale de
GowinSynthesis, la présence des netlists et l'absence de modification des
entrées officielles. Elle archive les empreintes et les journaux.

Elle ne crée pas de bitstream console, ne remplace aucun fichier partagé,
n'accède à aucune carte et ne modifie ni R4, ni broches, ni PLL. Une génération
réussie serait seulement `GENERATED_NOT_INTEGRATED` : l'intégration dans un
candidat Neo figé, son routage, le timing et l'énumération USB resteraient
des étapes distinctes à vérifier.

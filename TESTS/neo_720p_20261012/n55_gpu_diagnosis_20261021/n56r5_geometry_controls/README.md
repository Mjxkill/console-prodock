# N56r5 préparé, compilation en attente de revue

Manifeste SHA-256 :
`187eab97d98b341bd1a177543d1a00d77c8b2c156ddac7df15c1f47fd369c2fa`.

Parent exact : `tang/impl/console_neo_n56r3`, bitstream
`77a76cdc6d16aaa34a939296cc74ed7f6e29980682ac2756b6b2658ae443fbe2`.
La garde commune aux deux cartes passe à la préparation et sera rejouée avant
le lancement. Aucune compilation ni aucun accès matériel n'est réalisé par
`--prepare-only`.

Les seuls ajouts au CST sont :

```tcl
CLOCK_LOC "u_accel/u_v1/n57378_3" LOCAL_CLOCK;
CLOCK_LOC "u_accel/u_v1/n59467_5" LOCAL_CLOCK;
```

Il s'agit des captures CAMERA et FACE. Les preuves vérifient respectivement
204 et 246 charges CE : 198/240 DFF et six entrées DSP dans chaque cas. Les
ports vectoriels sont déroulés bit par bit. Aucun pin CLK n'est chargé par
ces deux nets. Les drivers, INIT, connexions, cellules chargées et paramètres
des DSP sont conservés pour comparaison après routage.

Les sept placements de R4 ne sont pas repris. RTL, netlist synthétisée, DDR,
SDC, fréquences, broches, options PnR et fichiers d'initialisation restent
ceux de R3. Le constructeur vérifie les copies et refuse tout autre écart.

L'inventaire de tous les CE GPU/scanout/observateur est joint. D'autres nets
peuvent être promus vers LW ; les protections proposées pour le contrôle de
snapshot et `v1_pending` restent hors de ce candidat. Reset4 dispose déjà
d'une contrainte locale dans R3, malgré son LW effectif : son routage devra
être vérifié séparément après PnR.

Après revue seulement :

```sh
python3 TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021/build_geometry_controls.py --build-reviewed 187eab97d98b341bd1a177543d1a00d77c8b2c156ddac7df15c1f47fd369c2fa
```

Puis qualification complète avec `tools/check_neo_timing.py` et contrôle
local `audit_geometry_controls.py` : ce dernier couvre aussi les CE DSP du
matériau déjà corrigé, les quatre contrôles antérieurs et reset4, ainsi que
les nouveaux nets globaux. Un succès de compilation ou d'audit ne remplace
ni le timing complet ni les essais matériels.

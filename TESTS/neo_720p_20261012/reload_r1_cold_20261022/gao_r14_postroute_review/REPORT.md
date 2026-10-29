R14 n'apporte aucun changement physique par rapport à R10 : le fichier de configuration binaire est identique octet par octet, et les sorties de routage ne diffèrent que par leurs métadonnées. La contrainte GAO `CLOCK_LOC "control0[0]" BUFG = CLK;` a été acceptée, mais n'a eu aucun effet observable sur cette construction. Charger R14 ne fournirait donc pas une comparaison matérielle avec une nouvelle distribution TCK.

L'audit statique reste **FAIL**. Le code de retour 0 et l'état `ROUTED_NOT_QUALIFIED` attestent la fin du routage, pas sa qualification. Aucun accès carte, nouveau build, modification des entrées ou alias de bitstream n'a été effectué par cet audit.

| Contrôle | R10 | R14 |
|---|---:|---:|
| Setup minimum | −0,849 ns | −0,849 ns |
| Endpoints setup violés | 64 | 64 |
| Hold minimum | −0,384 ns | −0,384 ns |
| Endpoints hold violés | 13 | 13 |
| Recovery minimum | −0,364 ns | −0,364 ns |
| Removal minimum | +0,196 ns | +0,196 ns |
| Largeur d'impulsion, marge minimum | +1,375 ns | +1,375 ns |
| PRIMARY | 8/8 | 8/8 |
| LW | 7/8 | 7/8 |

La [comparaison complète des artefacts](physical_comparison.json) enregistre chaque ligne différente, les SHA bruts et les règles de normalisation. `ao_0.bin` est strictement identique : 5 270 016 octets, SHA-256 `d6890a96535160d4ace5d27f2bb2fa8ec8c1ec59580ce5e13a30bb46d73f7534`. `console_neo.db` et `console_neo.timing_paths` sont également identiques octet par octet. Les fichiers BINX contiennent exactement le même BIN à l'offset 639 ; seule la date de leur en-tête diffère.

| Artefact | Toutes les différences R10 → R14 |
|---|---|
| `ao_0.fs` | Date de création, ligne 25 |
| `console_neo.vo` | Date de création, ligne 5 |
| `console_neo.sdf` | Date de création, ligne 8 |
| `console_neo.tr` | Trois préfixes de chemins, lignes 52–54 ; date, ligne 59 |

Aucune donnée de configuration, cellule, connexion, position, délai SDF ou valeur de timing n'a été normalisée. Le SHA brut du FS R14 est `ed468985d0e4669d8c5d68d7c727258d62920f5fd3dadda781ae10f1b613528c` ; sa différence avec le SHA R10 ne traduit ici que la date du commentaire. Le journal final a le SHA `4a178c1a8eb42fb24e5e3e0fac61302865dd0b913dd9ae0e39626bf36fdcbe06`, contient les marqueurs de fin attendus et aucune occurrence de `ERROR`, recherchée partout sans ancrage de ligne.

Les [tables de ressources](complete/resource_tables.txt) et les [chemins TCK](complete/tck_clock_path_rows.txt) restent ceux de R10. Les huit PRIMARY applicatives sont conservées, aucune route globale n'est ajoutée ni retirée. `control0[0]`/TCK ne figure pas dans cette table. Le segment après `u_gw_jtag/tck_o` conserve 250 charges, contre une charge sur le segment amont. Les treize endpoints hold GAO, leurs fronts et leurs marges sont inchangés ; le pire reste `u_icon_top/enable_reg_1_s0` → `enable_reg_0_s0`, descendant → descendant, −0,384 ns. Les avertissements PR1014 sur `clk_d` et `ae350_tck_d` existaient déjà dans R10.

GAO conserve 567 éléments logiques (552 LUT et 15 ALU), 354 registres et 6 BSRAM. Les vingt connexions logiques générées et les paramètres d'acquisition sont identiques à ceux du parent : `clk_d` à 50 MHz selon la contrainte, 4 096 échantillons, capture initiale activée, déclenchement `ddr_init == 1`, position demandée 128. Le rapport de timing expose cinq témoins physiques de capture (`ae350_rst_sync[1:0]`, `u_soc/init_sync[0]`, `soc_dbg[0]`, `vid_hrstn`) et le chemin de déclenchement DDR, avec l'horloge attendue. Les blocs GAO protégés ne sont pas développés dans le VO public : cela ne constitue pas une vérification physique indépendante de chacune des vingt liaisons.

Les dix audits structurels hérités ont tous été exécutés, sans exemption :

| Audit | Résultat |
|---|---|
| Copy | PASS |
| Scanout | PASS |
| Réplication du propriétaire GPU | PASS |
| Contraintes de fermeture timing | PASS |
| FIFO CPU/DDR en registres | PASS |
| Arbre des resets GPU | **FAIL : Reset 4 still uses a global routing resource** |
| Masque pixel, synthèse | PASS |
| Masque pixel, routage | PASS |
| Sélecteur pixel, synthèse | PASS |
| Sélecteur pixel, routage | PASS |

Le FAIL reset correspond à `gpu_debug_state[48]` sur LW. Le PASS de l'audit des contraintes signifie que les garde-fous de contraintes sont présents ; il n'annule pas les violations numériques de timing. Les 57 contraintes actives, les fréquences attendues et le profil DDR sont contrôlés dans le [résultat complet](complete/result.json).

L'agrégateur initial ne parcourait que la section 3.3 des chemins détaillés, alors que les témoins de capture se trouvent aussi en 3.7. Son [résultat initial](result.json) est conservé intact ; ses champs de visibilité des sondes ne sont pas la conclusion finale. La [révision complète](complete/audit.py) couvre les deux sections et a réexécuté les dix audits. Son résultat a le SHA `b4fefb1d36c174b1254f9ae96bd53ffc10174083ca1957cc742749b500d94a98`. La comparaison physique séparée a le SHA `e90a0d402487db3062a2bbf5b77107ddcecb2d2bd42bfe1a55ea01e5a1a3c5a6`.

R14 vise l'instrumentation GAO. **Aucune causalité hold GAO → reset AE350 bloqué n'est prouvée.** Les résultats présents ne localisent pas la cause du défaut de démarrage, ni la raison interne pour laquelle la contrainte acceptée est restée sans effet. Même un démarrage après un futur reroutage différent ne suffirait pas, à lui seul, à démontrer cette causalité. Aucun autre routage ou essai matériel n'est proposé automatiquement par ce résultat.

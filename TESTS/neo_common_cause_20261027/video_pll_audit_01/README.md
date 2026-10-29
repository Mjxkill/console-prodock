# PLL vidéo : différence réelle, cause non établie

Lecture des sources figées et des netlists routées R19, R21r2 et G22r0.
Les paramètres et ports sont extraits dans `result.json`, avec SHA et lignes.
Aucune recompilation ni mesure matérielle.

| Paramètre | Neo R19 / R21r2 | Pro Dock G22r0 |
|---|---|---|
| DYN_ICP_SEL / DYN_LPF_SEL | TRUE / TRUE | FALSE / FALSE |
| Entrées ICPSEL / LPFRES / LPFCAP | Toutes zéro | Toutes zéro, contrôle statique sélectionné |
| Paramètres ICP_SEL / LPF_RES | X / X, non sélectionnés en mode dynamique | X / X, calcul automatique par Gowin en mode statique |
| RESET PLL | GND | GND |
| VCO / sortie vidéo nominale | 743,75 / 74,375 MHz | 1050 / 35 MHz |

UG306-1.0.9E, tableaux 5-2 et 5-3, définit le choix statique/dynamique :
le code ICPSEL zéro donne le courant minimal, LPFRES zéro la bande passante
la plus large. Les X des paramètres statiques demandent un calcul automatique
par Gowin ; ils ne représentent pas une entrée physique inconnue.
Source primaire : https://cdn.gowinsemi.com.cn/UG306E.pdf
Copie officielle locale lue :
`/home/michael/logic_analyser_wifi/UG306-1.0.9E_Arora V Clock User Guide.pdf`.

Cela prouve une configuration analogique différente de la PLL vidéo, pas un
paramètre interdit ni une PLL physiquement instable. La documentation consultée
ne donne pas une borne permettant de déclarer ces codes zéro invalides pour
743,75 MHz. Les modèles numériques ne valident pas cette boucle analogique.

Contrepoint essentiel : le fichier vidéo de l'analyseur L31r8 figé est strictement
identique au fichier Neo R19/R21r2, SHA
`0f70154da8757fcc14bbaa578659c48db07121ca2db3bc8208d57bbc892b9ef8`.
Son `la_top.v:507–508` branche aussi ces trois entrées à zéro. L31r8 et R19
ont affiché une image ; la configuration n'empêche donc pas systématiquement
le fonctionnement. Une sensibilité conditionnelle n'est pas exclue.

Le top Neo libère `pixel_up[2]` après trois fronts pixel de LOCK haut,
environ 40 ns, sans qualification continue 2 ms de ce signal. UG306 demande
2 ms d'observation avant de confirmer le verrouillage. C'est une lacune de
qualification du démarrage HDMI. Le reset du scanout est une autre chaîne,
issue de `vid_hrstn`, et la séquence CPU attend 50 ms : ne pas les confondre.
Cette lacune n'établit pas que le PLL LOCK ait glitché pendant nos essais,
ni qu'elle explique le compteur scanout nul, le GPU ou l'USB.

Prochaine vérification utile : comparer cette configuration aux paramètres
calculés par le générateur officiel pour la même cible et les mêmes fréquences,
et obtenir une observation indépendante de pixel_clk / LOCK / resets. Une
différence de paramètres seule ne justifie pas de lancer une série de routages.

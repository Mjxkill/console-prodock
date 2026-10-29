# Contre-revue du pack global — 28 octobre 2026

La rédaction couvre les demandes utilisateur. Un défaut concret du contrôleur
de chemins a été reproduit puis corrigé avec l'autorisation de root. La revue
ne qualifie ni l'installation globale ni l'exécution des modèles : ces opérations
appartiennent aux autres responsables.

## Défaut corrigé : racine différente après normalisation

Avant correction, `--project PROJECT/alias/..` était accepté lorsque `alias`
pointait vers `OUTSIDE/deep`. Le système de fichiers désigne alors `OUTSIDE`,
mais `os.path.abspath` normalisait lexicalement vers `PROJECT` avant le contrôle
des liens. Contre-exemple réel en répertoire temporaire : `OUTSIDE/src/a.c`
contient 1 001 lignes, `PROJECT/src/a.c` une seule ; le contrôleur répondait
PASS et mesurait une ligne dans le mauvais arbre.

`no_symlink` refuse désormais tout composant `..` avant `abspath`. Ce refus
concerne la racine et le manifeste, même sans lien symbolique. Les chemins
des entrées étaient déjà contrôlés de cette façon. Aucun fichier audité n'est
lu dans ces cas refusés.

Preuves : `code_size_tests.json` et `code_size_tests.log`, **8 groupes PASS**,
dont quatre contre-cas nouveaux (racine/manifeste, lien/chemin ordinaire).
Les anciens résultats à sept groupes sont conservés et ne prouvent pas les
nouveaux octets. Empreintes finales :

- `check_code_size.py` : `71ab07385c0a7d096a534909ffbc379a29e6e87365d181c3128164dc459c9ab0`.
- `test_code_size.py` : `d2447effe15cc2f55a1ee899bc3aeef053412c1a5842c1a84a97c41473b1293a`.

## Conformité des documents aux demandes

| Demande | Présence vérifiée et limite |
|---|---|
| Codex chef de projet, architecture et arbitrage | Explicite dans les deux documents ; propriétaire unique et critères de délégation définis. |
| OpenCode et quatre modèles exacts | DeepSeek V4.1 Flash, GLM 5.3 Flash, Minimax M3.1 Flash et Beam nommés ; indisponibilité tracée, Claude facultatif. |
| Continuité de tâches utiles | File, dépendances, reprises bornées, absence de double lancement et vérification des processus exigées ; pas de travail inventé. |
| Temps et qualité par tâche | Attente, exécution, revue, correction séparées ; domaine/type/difficulté et contexte exact conservés ; notes avec preuves et attribution des écarts. |
| Comparaisons équitables | Sorties non évaluées sans note, échecs d'outil distingués ; cohortes comparables et seuil minimal documenté. |
| Maximum 1 000 lignes | Code généré compris ; dette existante recensée ; exemptions fournisseur/archive déclarées et visibles. |
| Commentaires, modularité et réutilisation | Contrats, unités, invariants, choix délicats et limites cités ; refus du découpage artificiel/minification. |
| Plusieurs plateformes | Source commune unique, profils et adaptateurs ; snapshots de preuve distingués des branches maintenues. |
| Nettoyage | Vérification des usages et dépendances, conservation des preuves/références/travaux d'autrui ; pas de nettoyage aveugle. |
| Fiches de tests | Objectif réfutable, empreintes, procédure, attendu/observé, cas adverses, plateformes et limites présents dans le modèle. |

Aucun autre manque concret identifié dans ce périmètre. Le contrôleur de taille
ne vérifie volontairement ni la qualité des commentaires, ni la modularité,
ni l'exhaustivité/honnêteté d'un manifeste fourni : ce sont des obligations de
revue. Un PASS doit rester rattaché à cette liste explicite, jamais présenté
comme une conformité de tout le dépôt. Les règles globales ne rendent pas
l'ancien code conforme par leur seule installation.

## Périmètre et conservation

Revue locale sans carte, réseau, installation ou suppression. Seuls le
contrôleur autorisé et son test ont été corrigés ; les sources du jeu,
références, fichiers FPGA et snapshots n'ont pas changé. Les tests ciblés du
contrôleur vérifient cette modification indépendante des entrées de construction
des deux cartes. Le rapport séparé `LUMA_DEBT.md` inventorie la dette Luma.
`review_inputs.json` lie la revue aux octets lus.

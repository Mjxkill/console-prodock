# Documentation et nettoyage du dépôt — 31 octobre 2026

## Objectif et périmètre

Ajouter une entrée claire au projet, une description complète et un guide
de construction/test, puis nettoyer les déchets identifiés sans perdre les
références ni les travaux en cours. Base Git :
`329df855f6de4d3ecf0c2cf306336a42d6726e40`, branche `master`.

Livrables : `README.md`, `ARCHI/PROJET.md`, `ARCHI/DEMARRAGE_ET_TESTS.md`,
`ARCHI/CLEANUP.md`, compléments ciblés de `.gitignore` et cette fiche.
La question suivante sur CMD6 est consignée dans `ARCHI/SD_SPI_HIGH_SPEED.md`.
Les modifications du terminal, de `AGENTS.md`, du catalogue des cartes et
de `TESTS/dual_board/latest.json` préexistaient ; elles ne font pas partie
de ce commit documentaire.

## Délégation et revue

Mission OpenCode `repo_docs_cleanup_minimax_20261031_01`, modèle exact
**minimax-m3.1-flash**, mode exécution, type implémentation documentaire,
difficulté moyenne. Périmètre isolé, six livrables possédés, sans Git,
suppression ni accès matériel.

| Mesure | Résultat |
|---|---|
| Durée d'exécution | 530,981 s |
| Requêtes modèle | 62 |
| Appels d'outils | 73 |
| Commandes de test observées | 4 : 2 agent, 2 superviseur |
| Échecs de test | 1 au contrôle initial du superviseur ; contrôle final réussi |
| Verdict de livraison | Candidat produit, revue nécessaire |
| Revue / correction Codex | Durées séparées non mesurées ; aucun temps reconstruit artificiellement |

La revue a exigé des corrections importantes :

- confusion entre la version 6.0 de l'IP DDR3 et une génération de mémoire ;
- rotation affine attribuée à tort aux sprites du compositeur ;
- fusion de statuts C37, G22r0 et candidats en cours ;
- instabilité du CPU déduite à tort d'un essai avec CPU volontairement arrêté ;
- Linux/U-Boot et chemins de chargement historiques mélangés ;
- dossiers de builds proposés trop largement comme supprimables, alors
  qu'ils contiennent des sauvegardes et sources uniques ;
- chemins absents de l'index limité de la mission déclarés à tort absents
  de GitHub. L'index fourni ne permettait pas cette conclusion.

Le plan de suppression n'a pas été exécuté. Codex a repris le README, le
guide et le plan de nettoyage, et corrigé la description détaillée. Le
rapport original reste conservé localement ; ce n'est pas le livrable publié.
La mise à jour « S400 en routage » est un changement d'état après le brief,
pas une faute attribuée au modèle.

## Nettoyage constaté

- Inventaire initial : 29 693 fichiers suivis, 30 706 non suivis.
- Suppression vérifiée : **165 caches Python, 2 093 082 octets**.
- Sources, références, résultats matériels et builds Gowin : aucune suppression.
- Aucun formatage SD, accès carte ou chargement FPGA pour ce lot.

Les règles ajoutées ignorent les caches Python/outils et les fichiers de
verrou. Elles ne masquent ni `TESTS/` entier, ni les archives protégées.
Elles ne constituent pas une autorisation de supprimer les fichiers ignorés.

## Validation

Contrôles exécutés, résultat **PASS**, conservés dans le dossier local
`TESTS/repo_cleanup_docs_20261031_01/` :

1. Résolution des liens relatifs des nouveaux documents, y compris leur
   présence dans Git ou dans le lot explicitement publié.
2. Vérification des commandes contre les Makefiles, options des scripts et
   sources ; aucune commande de chargement exécutée pour la documentation.
3. Contrôle des règles d'ignor avec exemples positifs et négatifs, dont les
   archives protégées et les sources communes.
4. Garde des références Pro Dock et validité de la campagne locale existante.
5. `git diff --check` et revue de la liste exacte des fichiers à committer.

Les nouveaux documents ne changent aucune entrée RTL, pilote, constructeur
ou banc de la campagne des deux cartes. Vérifier son empreinte suffit ici ;
il ne faut pas présenter cette vérification comme une nouvelle simulation.
La dernière campagne locale liée est
`TESTS/dual_board/20261031_dashboard_review_projection_02/result.json`,
**11 groupes PASS**, sous réserve du contrôle de validité enregistré.

Preuves détaillées et empreintes : `validation_01.json`,
`cache_inventory_01.json`, `cache_cleanup_01.json` et `review_01.json` dans
le dossier local du lot. Les preuves locales non publiées sont distinguées
des liens vers les sources versionnées.

## Limites

La documentation reprend des résultats datés ; elle n'ajoute aucune
qualification matérielle. Neo reste en diagnostic, le boot flash autonome
n'est pas démontré, le débit SPI et la fluidité du parcours 3D restent ouverts.
Les fichiers de code anciens de plus de 1 000 lignes et les gros artefacts
irremplaçables demandent encore un inventaire ciblé ; aucun nettoyage aveugle
ni réorganisation de leurs chemins n'a été effectué.

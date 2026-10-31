# Organisation et conservation des fichiers

Inventaire et nettoyage documentaire du **31 octobre 2026**.

## Organisation

| Zone | Contenu à y conserver |
|---|---|
| `tang/rtl`, `tang/boards` | RTL, IP fournisseur, profils, contraintes et inventaire |
| `fw_console`, `linux`, `games` | Sources des logiciels et jeux |
| `assets` | Ressources utilisées par les applications |
| `tools`, `optimizer` | Construction, analyse, diagnostics et tests d'outillage |
| `ARCHI` | Contrats, architecture et guides |
| `TESTS` | Bancs, fiches, manifestes, journaux et observations |
| `bitstreams` | Fiches et empreintes des versions conservées ; archives protégées |
| Dossiers de build | Sorties intermédiaires, candidats et parfois références figées |

Les sources communes ne doivent pas être recopiées dans deux arbres maintenus
indépendamment pour Pro Dock et Neo. Les snapshots d'expérience sont des
preuves datées, avec un manifeste ; ils ne deviennent pas une seconde source
de développement.

## Nettoyage effectué

L'inventaire initial relevait **29 693 fichiers suivis** et **30 706 fichiers
non suivis**, dont 29 236 sous `TESTS`. Ce nombre ne mesure pas la quantité
de déchets : il comprend des sources de candidats et des preuves nécessaires.

**165 fichiers de cache Python ont été supprimés**, après inventaire et
vérification d'empreinte, soit **2 093 082 octets**. Les répertoires de cache
devenus vides ont été retirés. Aucune source, archive de référence, preuve
matérielle ou sortie Gowin en cours n'a été supprimée.

Le README racine, la description du projet et le guide de construction sont
ajoutés. Les règles Git sont complétées pour les caches et verrous temporaires.
Les modifications antérieures du terminal, des règles d'agents, du catalogue
des cartes et du dernier résultat de régression restent hors de ce lot.

Preuves locales :
`TESTS/repo_cleanup_docs_20261031_01/cache_inventory_01.json` et
`cache_cleanup_01.json`. La fiche publiée est
[REPO_DOCUMENTATION_20261031.md](../TESTS/REPO_DOCUMENTATION_20261031.md).

## Ce qui doit rester protégé

- G22r0 / NEBULA R17 et les empreintes de
  [reference.json](../tang/boards/prodock/reference.json).
- Les archives `bitstreams/prodock_g22r0_reference_20261021.tar.gz` et
  `bitstreams/prodock_r17_sources_b2b1ba8.tar.gz`, même lorsqu'elles ne sont
  pas suivies par Git.
- La sauvegarde binaire historique sous `linux/build/golden_nebula_r17`
  et son archive de restauration.
- Les snapshots Neo et leurs netlists utilisés pour les comparaisons.
- Les candidats logiciels qui contiennent encore des modifications absentes
  des sources principales, ainsi que leurs manifestes.
- Les campagnes, rapports de timing et captures qui justifient une conclusion.
- Les travaux en cours et les compilations appartenant à d'autres sessions.

**Un dossier ignoré par Git n'est pas nécessairement régénérable.**
Une reconstruction avec une autre version de Gowin ne reproduit pas forcément
le bitstream validé. Il est donc incorrect de déclarer `linux/build/`,
`tang/impl/` ou `games/luma3d/candidates/` supprimables dans leur ensemble.

## Suite du rangement

Avant toute suppression plus large :

1. Inventorier chemin, taille, propriétaire, empreinte et usages.
2. Distinguer source unique, référence, preuve, candidat et cache.
3. Vérifier les dépendances statiques **et** les processus qui utilisent le
   dossier ; un fichier non suivi n'est pas nécessairement inutilisé.
4. Archiver les entrées et résultats irremplaçables avant de retirer une
   sortie intermédiaire.
5. Vérifier les références et relancer les tests affectés après nettoyage.

Le découpage des fichiers de code existants de plus de 1 000 lignes reste
un chantier séparé. La limite s'applique au code maîtrisé et à son code
généré ; les IP fournisseur et les archives figées sont identifiées à part.
Ce lot documentaire ne prétend pas avoir résorbé cette dette ni avoir
audité tous les fichiers anciens comme du code mort.

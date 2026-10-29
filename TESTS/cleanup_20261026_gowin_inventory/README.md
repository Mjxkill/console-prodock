# Nettoyage du 26 octobre 2026

Nettoyage exécuté : **1 070 fichiers**, **11 798 530 603 octets logiques**
(10,99 Gio), soit **11 801 214 976 octets alloués** retirés.
Les fichiers étaient tous des sorties régénérables de `tang/impl`.

| Sorties retirées | Nombre | Copie utile conservée |
|---|---:|---|
| Encodages `.bin` / `.binx` | 452 | Bitstream canonique `.fs`, haché |
| Rapports HTML redondants | 516 | Rapport texte correspondant |
| Caches de placement/routage `.p` / `.pr` / `.db` | 102 | Sources, netlists, bitstream et rapports |

**Aucun `.fs` canonique n’a été supprimé** : 340 fichiers ont été vérifiés
par SHA-256 avant et après le nettoyage. Les 103 builds protégés par une
référence ou un consommateur statique restent entiers, notamment tous les
diagnostics N56/N57, N56r19 chargé sur Neo, N56r8 et G22r0 Pro Dock.
Les archives de référence Pro Dock restent intactes.

Les 654 entrées de la campagne des deux cartes sont inchangées ; la preuve
locale courante reste celle de `20261026_r20r1_scalar_observer` (11 groupes
PASS). Le nettoyage ne constitue ni une nouvelle validation matérielle ni
une qualification de timing. Aucun compilateur ni autre projet n’a été arrêté.

## Preuves

- [Résultat exécuté](applied_20261026_230035/result.json)
- [Contrôles avant suppression](applied_20261026_230035/preflight.json)
- [Fichiers retirés, tailles et SHA](applied_20261026_230035/deleted_manifest.json)
- [Journal des suppressions réellement effectuées](applied_20261026_230035/journal.jsonl)
- [Inventaire initial des 488 dossiers](build_inventory.json)
- [Dépendances statiques examinées](dependencies.json)
- [Bitstreams et doublons identifiés](bitstreams.json)

La liste contrôlée avait SHA-256
`f80ff6cd4c7aaca64477c88b618efa5f117f55f8e4f7311f0aba4b4f7f1fec7e`.
Le contrôle à blanc a réussi avant l’exécution. Le script refuse une liste
différente, un fichier modifié, une source non conforme, un fichier suivi par
Git, un lien symbolique ou un compilateur actif.

Les 34 anciens builds dont les caches PnR ont été retirés ne peuvent plus
reprendre directement depuis ces caches ; un reroutage complet serait nécessaire.
Le bitstream mesuré et les preuves de leur ancienne exécution sont conservés.

## Organisation

Le nouveau [point d’entrée par carte](../../ARCHI/CARTES/README.md) distingue
247 entrées communes, 161 Pro Dock et 103 Neo, avec catalogues de sources et
de builds. Les sources communes restent uniques. Les chemins des snapshots
figés restent stables car des scripts, Tcl et preuves les référencent.

Les dossiers `games`, les paquets Linux, les ressources artistiques et les
preuves sous `TESTS` n’ont pas été nettoyés. Les travaux en cours y restent
disponibles. Le rapport HDL est accessible depuis la carte du dépôt.

## Archivage éventuel, non appliqué

[227 bitstreams historiques](bitstream_archive_review.json) pourraient être
regroupés dans une archive compressée vérifiée, pour un gain supplémentaire.
Ils sont cités par des preuves historiques : aucune suppression de ces `.fs`
n’a été faite. Leur retrait exigerait d’abord un index de restauration et une
vérification complète de l’archive. Cette proposition reste séparée du
nettoyage effectivement réalisé ci-dessus.

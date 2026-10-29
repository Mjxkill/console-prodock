# Carte du dépôt : commun, Pro Dock, Neo

Cette navigation sépare les responsabilités sans dupliquer les sources ni déplacer
les snapshots figés. L’inventaire machine de référence reste
[ownership.json](../../tang/boards/ownership.json).

| Ensemble | Entrées | Point d’entrée |
|---|---:|---|
| Commun | 247 | [GPU, bus, pilotes et outils partagés](commun/README.md) |
| Pro Dock | 161 | [Sources, référence protégée et builds LCD](prodock/README.md) |
| Neo | 103 | [Sources, substitutions et builds HDMI](neo/README.md) |
| Historique non classé | — | [Catalogue conservé](archives/README.md) |

Les sources de développement, les copies figées de construction et les preuves
de test sont trois ensembles distincts. Un fichier de snapshot Neo peut différer
du source commun : le catalogue ne prétend pas les rendre équivalents.

Références protégées : Pro Dock **G22r0 / NEBULA R17**. La Neo **N56r19** reste
un diagnostic avec mire et JTAG fonctionnels ; son GPU complet et son timing
ne sont pas qualifiés. N56r8 reste un repli HDMI.

- [Règles de compatibilité](../COMPATIBILITE_CARTES.md)
- [Revue des grands fichiers HDL](../../TESTS/hdl_inventory_20261026/analysis/REVIEW.txt)
- [Nettoyage exécuté et journal](../../TESTS/cleanup_20261026_gowin_inventory/README.md)

Les chemins des sources et snapshots restent ceux des constructeurs. Les caches
PnR retirés des anciens builds imposeraient un reroutage complet pour les reprendre ;
leurs sources, netlists, timing, bitstreams et rapports restent disponibles.

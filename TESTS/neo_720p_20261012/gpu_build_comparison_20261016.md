# Comparaison des essais GPU Neo du 16 octobre 2026

Les marges setup et hold ci-dessous sont séparées et extraites des tableaux du rapport Gowin. La réussite du timing ne vaut pas validation matérielle. Les chargements à timing négatif sont des diagnostics SRAM, CPU arrêté.

| Variante | Setup min (ns) | Hold min (ns) | Recovery / removal (ns) | Violations setup / hold | Audits structurels | Résultat carte |
|---|---:|---:|---:|---:|---|---|
| n36r0 | -4.866 | +0.140 | +1.990 / +0.287 | 97 / 0 | PASS | Remplissages corrects ; rendu couleur incorrect |
| n37r0 | -0.523 | +0.139 | +1.514 / +0.311 | 5 / 0 | PASS | Non chargé |
| n38r0 | +0.259 | +0.129 | +2.175 / +0.404 | 0 / 0 | PASS | Timing conforme ; clipping et pixels incorrects |
| n38r1 | -0.055 | +0.129 | +2.175 / +0.404 | 4 / 0 | FAIL | Non chargé : reset GPU sur LW |
| n38r2_newide | -3.577 | +0.165 | -6.510 / +0.355 | 262 / 0 | PASS | Non chargé |
| n38r3_primary | +0.259 | +0.129 | +2.175 / +0.404 | 0 / 0 | FAIL | Non chargé : demandes PRIMARY non appliquées |
| n39r0 | -1.172 | +0.142 | +1.149 / +0.393 | 15 / 0 | PASS | Blocage CLEAR |
| n39r1 | -2.225 | +0.138 | +0.361 / +0.394 | 92 / 0 | PASS | Même blocage CLEAR, netlist identique à N39r0 |
| n40r0 | -2.083 | +0.138 | +1.887 / +0.352 | 112 / 0 | PASS | Onze commandes terminées mais rejetées ; aucune écriture pixels |

N40r1 a été rejeté avant placement pour doublons de contraintes ; N40r2 est en cours avec les alias de resets corrigés.
Les captures historiques et leurs limites restent dans `../NEO_720P_20261012.md`.

# Essai matériel du témoin UTW1 — 28 octobre

R22r1 a terminé son routage avec la licence renouvelée. Le bitstream exact est
`55601256120915adbb08279c0b6bd42caabf8deff261bf87b8a7b8d8cbf9c8aa`.
Les 402 registres du témoin et les 32 mux de lecture sont structurellement
conformes. Les 2 604 requêtes setup/hold ciblées sur D/CE/RESET ont toutes des
marges positives. Le timing global reste **FAIL** : setup −1,013 ns et
recovery −0,212 ns sur d'autres destinations. La revue root autorise seulement
une collecte diagnostique bornée, pas le fonctionnement complet du système.

Le premier lancement sous sandbox a échoué à `libusb_init`, avant la garde
initiale et avant tout chargement. Le journal `capture_20261028_105428` est
conservé. Les deux essais matériels hors sandbox ont ensuite terminé :

| Version | Acquisition | Mot version banque | Mot version témoin | Restauration |
|---|---|---|---|---|
| R19 historique | activity_20261028_000942 | 0, quatre phases | absent | R19 vérifiée |
| R22r1 | capture_20261028_124213 | 1, quatre phases | 1, quatre phases | R19 vérifiée |
| R19 | activity_20261028_124422 | 0, quatre phases | absent | R19 vérifiée |
| R22r1, même fichier | capture_20261028_124454 | 1, quatre phases | 1, quatre phases | R19 vérifiée |

Les acquisitions R19 sont sous
`TESTS/neo_common_cause_20261027/utna_activity_prepared_01/` ; les acquisitions
R22r1 sont dans ce dossier. Chaque phase comprend deux lectures cohérentes.
Les commandes ARM/DISARM/SNAPSHOT/SNAPSHOT et les relations des compteurs
sont contrôlées. Les observations R19 demeurent FAIL, même si leur anomalie
était attendue. Les observations locales R22r1 passent leur contrat ; la
qualification globale du FPGA demeure FAIL.

La différence est reproductible mais sa cause n'est pas établie. R22r1 ajoute
des prises de mesure, des registres et des mux : le placement/routage et les
charges changent également. Ce n'est pas une expérience où seul un paramètre
physique varie. Le succès du témoin ne qualifie ni l'USB, ni la DDR, ni la
lecture vidéo ; il faut rapprocher ces observations du blocage principal.

Après les essais, la Neo porte de nouveau le R19 exact
`1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`,
CPU garé, registres GPU/NCP/UTNA frais et mire interne sélectionnée. La garde
JTAG a été vérifiée ; aucune nouvelle confirmation visuelle n'est revendiquée.
La Pro Dock n'a pas été touchée par ces expériences Neo. Aucun flash ni SD
n'a été écrit, aucun Linux ni charge GPU/DDR n'a été lancé sur la Neo.

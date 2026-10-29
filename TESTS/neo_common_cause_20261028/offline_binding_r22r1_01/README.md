# Décodeur UTW1 lié à la normalisation R22r1

Prêt aux tests locaux et à la relecture root. Aucun accès matériel.

`offline_capture.py` est la façade à importer par le collecteur. Elle conserve
les noms de fonctions et constantes du décodeur gelé : `collect_jsonl`, `decode`,
`strict_json`, `NET_SHA`, `BASE`, `PHASES`, etc. Le SHA accepté est le SHA réel
normalisé `0eb5638a…`, et non le SHA original `fa018540…`.

`decoder_bound.py` est une copie byte pour byte du décodeur original, avec une
seule substitution de la constante NET_SHA. La comparaison inverse retrouve
exactement le fichier gelé. Le schéma, les contrôles, les données et les statuts
ne changent pas. Aucune conversion des données capturées vers une fausse identité
originale n'est effectuée. Le fichier original n'a pas été modifié.

La façade vérifie les SHA du décodeur original, de la netlist, du graphe de
sérialisation, de l'assemblage, des simulations et du lancement avec rapports.
Elle vérifie également les octets de la copie avant import et avant décodage.
La provenance est ajoutée au **résultat**, jamais aux clés du paquet strict.
Une déclaration de bitstream attendue reste obligatoire séparément pour une
capture d'origine matérielle ; ces déclarations ne sont pas des attestations
physiques. L'identité réelle et le SHA du `.fs` devront être fournis par le
contrôleur matériel revu, après le routage.

Les 85 tests hérités et 18 tests de binding passent : identité ancienne rejetée,
identité arbitraire rejetée, copie modifiée après import refusée, modification
de dépendance refusée, résultats sémantiques identiques et version zéro toujours
FAIL. `tests_inherited_02` est la preuve finale. `tests_inherited_01` a été
supplanté par le renforcement de la vérification du fichier après import.
Un premier lancement du harnais a refusé son dossier extérieur à l'ancien
snapshot ; le harnais local a été adapté sans modifier les tests sémantiques.

`binding.json` lie exactement les fichiers et résultats. Le collecteur doit
épingler ce manifeste et la façade/copie. Aucun PASS de ce décodeur ne qualifie
le FPGA ; `hardware_qualified` reste faux, y compris pour une observation cohérente.

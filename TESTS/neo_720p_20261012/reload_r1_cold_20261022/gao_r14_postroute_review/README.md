# Audit indépendant R14

Ce dossier reçoit l'analyse en lecture seule de `tang/impl/console_neo_n56r14_gao_tck_cst_seeded`. Le constructeur, les entrées et les sorties du candidat ne sont jamais modifiés par cet audit. Aucun outil FPGA ni accès matériel n'est lancé.

Le routage est exécuté par root. `audit.py` attend l'existence de `route_result.json` avant de lire les sorties PNR. Il contrôle le code de retour, les marqueurs de fin, les SHA du résultat et du journal, puis tous les artefacts natifs attendus. Le callback du wrapper peut concaténer les messages : la recherche `ERROR` porte sur tout le journal, sans ancrage en début de ligne.

Les contrôles préparés couvrent :

- Identité du candidat préparé, source applicative et GAO, composant et bitstream natif.
- Setup, hold, recovery, removal et largeur d'impulsion ; nombres d'endpoints violés et groupes.
- SDC actif complet, fréquences imposées inchangées, commande PNR intégralement comparée au parent plus le CST GAO séparé.
- Huit PRIMARY applicatives, table globale complète, ressources GAO et lignes des chemins TCK.
- Les dix fonctions d'audit structurel sélectionnées par le manifeste, sans exclusion ni exemption.
- Comparaison des treize violations hold GAO R10 ; absence d'un chemin dans le rapport fini distinguée d'un slack positif.
- Vingt liaisons logiques des sondes, configuration d'acquisition héritée et témoins physiques réellement visibles ; aucun décodage des blocs protégés.

Les tests du parseur sur le rapport R10 terminé retrouvent ses treize holds GAO et ses dix-huit lignes globales. Les tableaux absents/malformés et le cas d'un `ERROR` concaténé sont couverts dans `parser_fixture_test_r3.json`. Ce test ne lit aucune sortie R14 en cours d'écriture.

Le paquet backend n'a pas de `build.tcl`, et la sortie native GAO peut s'appeler `ao_0.fs`. L'audit appelle directement les fonctions existantes au lieu d'ajouter des fichiers artificiels pour satisfaire le CLI historique. Il écrit son propre résultat ici, sans écraser `qualification.json` ni les preuves R10/R13.

La présence de ce dossier ou d'un test de parseur PASS ne qualifie pas R14. Le fichier `result.json` n'est produit qu'après contrôle des sorties terminées. Un résultat de timing ne prouve pas une correction du démarrage et ne remplace aucun essai matériel.

R14 vise l'instrumentation GAO et la distribution de son TCK. **Aucune causalité entre les violations hold GAO et le reset AE350 bloqué n'est prouvée.** Même si un futur chargement R14 démarrait, ce succès après reroutage ne suffirait pas à démontrer cette causalité : le placement et les délais physiques de plusieurs réseaux peuvent avoir changé. Les observations de reset et la fiabilité de lecture GAO restent deux sujets distincts à documenter.

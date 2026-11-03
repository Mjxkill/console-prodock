# Fiche — assemblage et préparation du candidat bancaire

Objectif : substitution limitée des deux mémoires, sans synthèse applicative,
modification des horloges/reset/CE/latences ou des contraintes.

Entrées : manifeste helper `banked_storage_01/DELIVERY.json`, qualification et
VG exacte ; netlist/contraintes REJECT R1 ; constructeur original figé. Chaque
entrée est hachée et refusée si elle change. Les sources communes ne sont pas
éditées ; les références Pro Dock sont contrôlées par la garde existante.

Vérifications exécutées par assemble.py :

- Helper qualifié et empreintes de toutes ses preuves.
- Réutilisation de replace_memories : exactement deux SDPB remplacés,
  douze defparam retirés, toutes les connexions conservées.
- Inverse de l'application exacte ;153modules dont151 entièrement identiques.
- Deux instances du helper, un seul module ajouté ; aucune autre RAM remplacée.
- Contraintes REJECT/S400 identiques, aucune des190INS_LOC ne vise les deux
  primitives remplacées.
- Trois contre-tests du graft exact refusés : modification d'un autre octet
  applicatif, du helper, puis de l'horloge CLKA d'une mémoire.

Contrôle à blanc séparé : gardes du moteur, preuves et régressions locales,
comparaison TCL avec REJECT R1 (trois chemins différents uniquement), absence
création du futur dossier de routage. Résultat dans DRY_RUN.json.

Résultats helper réutilisés, pas rejoués inutilement :6casRTL+5mutantsdétectés,
6casVGmappés, INIT/Q/D/CLK/reset des4128FF. Aucun essai matériel ni PNR dans
cette préparation. Les fichiers de rapports sont des archives de preuve ; les
netlists produites par Gowin sont des artefacts fournisseur, pas du code maintenu.

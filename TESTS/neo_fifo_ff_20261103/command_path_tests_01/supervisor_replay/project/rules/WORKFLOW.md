# Travail multi-modèles de Michael

Version 3 — 2 novembre 2026. Ce document complète les instructions globales
`~/.codex/AGENTS.md`, sans remplacer les règles locales du projet.

## Répartition des responsabilités

Codex est le chef de projet technique. Il garde l'analyse difficile, le choix
des expériences discriminantes, les interfaces, la planification, la revue et
la décision d'intégrer. Il donne aux agents des tâches suffisamment précises
pour produire un livrable vérifiable. Plusieurs agents peuvent travailler sur
un même sujet sous des angles différents, avec des fichiers de sortie distincts.

OpenCode est le point d'exécution des deux modèles Ollama autorisés :
`deepseek-v4.1-flash` et `glm-5.3-flash`. Michael a retiré MiniMax et Beam
le 2 novembre 2026. Les nouveaux lanceurs et files refusent ces modèles ;
les anciens résultats et évaluations restent conservés sans changement de nom.
La liste commune est définie dans `workflow_common.py` (`OLLAMA_MODELS`).
Lorsque quatre tâches indépendantes sont prêtes, la répartition demandée est
de quatre sessions OpenCode : deux DeepSeek et deux GLM, chacune avec son
contrat, ses fichiers possédés et ses mesures. Le nombre de modèles distincts
ne limite pas le nombre de sessions. Ne pas créer de travail artificiel.
Claude n'est pas nécessaire ; son emploi éventuel exige un choix explicite.

Le mode **exécution** est utilisé pour déléguer l'implémentation et les tests :
OpenCode peut lire et modifier la copie de tâche, appeler ses outils de test,
observer leurs résultats puis corriger dans la même session. Les commandes
de test sont définies dans le contrat ; la copie et ses outils sont isolés
du projet vivant, des périphériques, du réseau et des secrets du fournisseur.
Codex inspecte les modifications et les preuves avant intégration. Une absence
d'outils ou d'isolation est un blocage explicite, pas un passage silencieux
au mode avis. La fin d'une session ou une auto-déclaration de réussite ne
prouve pas que les tests ont passé.

Le mode **avis**, demandé explicitement avec `runner.py --mode review`, fournit
uniquement le paquet préparé, sans outils. Il convient aux contre-revues et
aux analyses textuelles ; il ne doit pas être présenté comme une exécution.
Pour les transferts et les opérations matérielles, le responsable garde le
verrou de la ressource et vérifie la commande. Ne transmettre ni identifiants,
ni secrets, ni fichiers hors du périmètre utile.

## Contrat d'une tâche

Renseigner avant de lancer : identifiant stable de tâche, identifiant unique de
tentative, tâche parente, projet, domaine, type, difficulté, paquet et empreinte,
livrable, critères d'acceptation, dépendances et modèle exact. Décrire les limites
de ce que l'agent peut conclure et les vérifications encore à la charge de Codex.

Exemples de domaines : `fpga`, `linux`, `game`, `graphics`, `usb`, `tooling`.
Exemples de types : `diagnosis`, `implementation`, `test_design`, `test_execution`,
`review`, `documentation`, `transfer_preparation`, `cleanup`.
La difficulté est fixée avant résultat : `low`, `medium`, `high`, ou `unspecified`.
Garder un vocabulaire stable et une même famille de tâches pour les comparaisons.

Le moniteur ne remplace pas la conduite du projet : Codex prépare la file,
vérifie les résultats, formule la tâche suivante et donne ses critères. Une
fin de génération n'est pas une acceptation. Une dépendance à une réponse
validée doit être explicitement matérialisée par le responsable. Les fins en
erreur sont visibles ; ne pas laisser un dépendant indéfiniment « en cours ».
Reprendre une tâche avec un nouvel identifiant de tentative et un nombre de
reprises limité, en conservant la cause et les résultats précédents.

## Mesure du temps et de la qualité

La durée d'exécution provient d'une horloge monotone ; les dates UTC permettent
de relier les événements entre sessions. Distinguer : temps dans la file, temps
du processus modèle, revue, corrections, et durée jusqu'au résultat exploitable.
Les tâches parallèles ne s'additionnent pas pour prétendre à un temps mural.
Enregistrer le mode d'exécution et distinguer le nombre de missions, les
requêtes modèle observées, les appels d'outils, les tests exécutés et leurs
échecs. Une session OpenCode peut effectuer plusieurs requêtes ; une tâche
simple n'a pas à être rallongée artificiellement. Les anciennes métriques
non qualifiées restent `legacy_unspecified` et ne sont pas réécrites. Les
comparaisons séparent les modes avis et exécution.
Une panne réseau, un arrêt demandé et une limite de sortie doivent être
identifiés séparément d'une réponse technique fausse.

Codex évalue le livrable après vérification. Quatre notes de 0 à 5 donnent
un score sur 100 : exactitude 40 %, pertinence 25 %, complétude 20 %,
utilisabilité 15 %. Échelle commune : 0 inutilisable/faux, 1 défauts majeurs,
2 reprises importantes, 3 utilisable après corrections, 4 bon avec corrections
mineures, 5 satisfait les critères vérifiés. Justifier les notes et les adapter
au contrat du type de tâche, pas au style de rédaction.

| Type | Preuves utiles pour le jugement |
|---|---|
| Diagnostic FPGA/USB | Faits versus hypothèses, lecture exacte des registres/docs, expérience discriminante, contre-exemple, reproduction |
| Implémentation | Tests comportementaux, intégration, cas limites, modularité, réutilisation, commentaires et régressions |
| Tests/revue | Défaut réellement détecté, tests échouant avant correction, absence de faux positif et de test qui copie le code |
| Graphisme/jeu | Captures comparables, lisibilité, cohérence visuelle, animation et mesures FPS sur la cible si disponibles |
| Documentation | Fidélité aux sources, limites explicites, instructions reproductibles, absence de revendications non vérifiées |
| Transfert/nettoyage | Intégrité avant/après, dépendances, cible exacte, restauration et absence d'impact sur un autre travail |

Verdicts : accepté directement, accepté après modifications, rejeté,
inconclusif. Enregistrer séparément le résultat des tests et l'identité de
l'évaluateur. Une sortie incomplète ou un échec d'outil n'obtient pas une note
de qualité technique par défaut ; son taux de livraison incomplet reste visible.
Une réponse non évaluée n'a pas de note. Une seconde IA peut proposer une
contre-revue ; Codex reste responsable du jugement final et des preuves.

Comparer le résultat au paquet effectivement transmis, pas à un contrat défini
après coup. Attribuer explicitement les écarts : réponse du modèle, ambiguïté
des consignes, contexte insuffisant, changement d'interface ou panne d'outils.
Une réponse écartée à l'intégration peut avoir correctement suivi un ancien
contrat. En cas d'ambiguïté qui empêche un jugement fiable, garder la note vide,
expliquer le problème, puis proposer un nouvel essai avec un contrat précis.

Conserver l'historique des évaluations, les empreintes de la réponse et des
preuves. Une note ne s'applique pas silencieusement à une réponse modifiée.
Pour les anciens travaux, importer uniquement les mesures effectivement
présentes dans les journaux ; ne pas reconstituer artificiellement le temps
de correction ou la difficulté d'une tâche après avoir vu son résultat.

## Statistiques et orientation

Afficher les nombres de tentatives, tâches distinctes, résultats évalués,
attentes de validation, erreurs, troncatures, acceptations directes et après
correction. Afficher note moyenne, médiane et p90 des durées, et temps de revue
et correction lorsque mesurés. Exporter JSON/CSV et un rapport HTML lisible.

Regrouper par domaine, type, difficulté et modèle. Séparer les configurations
ayant des budgets/paramètres différents lorsque cela influe sur la comparaison.
Ne comparer ni un diagnostic difficile à une mise en forme, ni des tests locaux
à des tests sur carte. Les taux de livraison et le temps nécessaire à obtenir
un résultat utile comptent autant que la note des seules réponses réussies.

Les premières observations servent à répartir les essais. Une suggestion
d'orientation n'est considérée qu'avec au moins 10 évaluations et 3 tâches
distinctes pour la cohorte concernée ; c'est un seuil pratique, pas une preuve
statistique de supériorité. Une comparaison sur les mêmes tâches est préférable.
Conserver des essais sur les autres modèles pour éviter de figer un classement
sur un échantillon biaisé. Aucun changement automatique de modèle à partir
de notes non vérifiées ou d'un unique résultat.

### Règle d’or — code simple et erreurs visibles

Cette règle s’applique à tous les projets, domaines et travaux délégués : RTL,
firmware, pilotes, applications, jeux, outils, tests et constructions.

- Une fonction remplit son contrat et sa responsabilité explicite. Séparer
  configuration, travail normal, diagnostic et récupération. Aucun effet de
  bord caché pour compenser une erreur située ailleurs.
- **Pas de correctif pour une erreur dont la cause n’est pas établie.** Avant
  de corriger, identifier le défaut par la documentation, une observation
  discriminante ou une reproduction ; expliquer le mécanisme causal et prévoir
  une vérification qui échoue avant et réussit après. Une hypothèse ne suffit pas.
- Si la cause reste inconnue, poursuivre le diagnostic. Ne pas empiler conditions,
  états mémorisés, délais, reprises, resets, verrous ou changements de routage
  pour donner l’apparence d’un succès. Une amélioration observée sans explication
  reste un résultat de diagnostic, pas une résolution.
- Identifier séparément l’instrumentation expérimentale : question testée,
  observations attendues, effets possibles, limites et retrait prévu. Ne pas
  la présenter comme une correction ni multiplier les variantes sans hypothèse.
- Propager les erreurs avec leur contexte ; ne pas convertir un échec en succès,
  ignorer silencieusement un paramètre, masquer un résultat négatif ou contourner
  un test. Refuser explicitement les demandes non prises en charge.
- Privilégier le code le plus simple qui respecte le contrat. Chaque protection,
  verrou, reprise ou abstraction doit répondre à une nécessité identifiée ;
  supprimer les mécanismes inutiles après vérification de leurs usages.
- Évaluer séparément fonctionnement et qualité de conception. Des tests PASS
  ne suffisent pas si le contrat est contourné ou si la cause reste inexpliquée.
  Cette règle fait partie des critères d’acceptation des missions des agents.

## Code, plateformes et environnement

Maximum 1 000 lignes physiques par fichier de code produit/maîtrisé par le
projet, y compris le code généré sous son contrôle. Recenser explicitement
les IP/bibliothèques fournisseur et archives de preuve ; les exemptions sont
visibles et justifiées. Les tables de données peuvent être organisées en
ressources cohérentes, sans minification pour contourner la règle.

Un module porte une responsabilité claire, des interfaces documentées et des
composants réutilisables. Commenter les contrats, invariants, unités, domaines
d'horloge/reset, durée de vie des ressources et raisons des choix délicats.
Le code propre aux plateformes réside dans des profils/constantes ou des
adaptateurs, avec une seule implémentation commune. Éviter les copies maintenues.

À la livraison, rechercher les chemins morts, anciens scripts et artefacts
devenus inutiles. Vérifier les références statiques et les usages dynamiques
avant suppression ; conserver les références validées, les preuves et les
travaux des autres sessions. Nettoyer les temporaires appartenant à la tâche,
documenter ce qui est conservé et contrôler les régressions après nettoyage.
Une règle nouvellement installée ne signifie pas que l'existant est déjà conforme.

## Fiche de tests minimale

Utiliser `TEST_RECORD_TEMPLATE.md` pour chaque lot. La fiche lie les attentes
et les observations aux entrées exactes. Les échecs restent des échecs. Une
plateforme non disponible reste « en attente », même si les tests locaux passent.
Ne pas fabriquer des tests sans pouvoir réfuter un comportement incorrect.

## Portée de l'installation

Ces consignes résident dans le répertoire Codex de l'utilisateur. Elles sont
chargées au démarrage d'une nouvelle exécution/session selon la découverte
AGENTS.md ; une session déjà active doit les lire explicitement. Un autre
`CODEX_HOME` ou un `AGENTS.override.md` peut modifier cette portée. Voir la
[documentation officielle](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
L'installation préserve les consignes existantes et ne modifie pas le modèle
principal, les permissions, les clés ou les projets des autres sessions.

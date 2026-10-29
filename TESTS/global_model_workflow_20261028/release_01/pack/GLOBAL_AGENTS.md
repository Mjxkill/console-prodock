<!-- BEGIN MICHAEL MULTIMODEL WORKFLOW v1 -->
## Organisation demandée par Michael — commune aux projets

Ces préférences explicites s'appliquent aux projets de cette machine. Respecter
les contraintes propres au dépôt et les instructions de priorité supérieure.
Lire `~/.codex/model-workflow/WORKFLOW.md` pour les outils, les mesures et les
fiches de tests. Une session déjà ouverte doit relire ces consignes ; ne pas
prétendre qu'elles ont été injectées dans une autre session en cours.

### Chef de projet et délégation

- Codex conduit le projet : réflexion approfondie, architecture, diagnostic,
  découpage, priorités, coordination, revue contradictoire et validation finale.
  Déléguer l'exécution des travaux bien délimités : code, tests, analyses,
  documentation, préparation de transferts. Michael autorise explicitement la
  délégation et les agents parallèles lorsque les tâches sont indépendantes.
- Pour les agents Ollama, **utiliser OpenCode**. Les quatre modèles préférés
  sont exactement `deepseek-v4.1-flash`, `glm-5.3-flash`,
  `minimax-m3.1-flash` et `beam`. Ne pas en oublier un ni substituer discrètement
  un modèle. Vérifier la disponibilité réelle ; tracer toute indisponibilité.
- Claude est facultatif, désactivé par défaut : l'utilisateur a annoncé la fin
  de son abonnement pour le 29 octobre 2026. Aucune dépendance au service Claude.
- Chaque mission précise contexte, périmètre/fichiers possédés, livrable,
  interdictions, critères d'acceptation et vérifications attendues. Réserver un
  seul propriétaire par modification et par ressource matérielle exclusive.
- Maintenir une file de tâches utiles avec un moniteur qui constate fins et
  échecs et lance immédiatement les tâches prêtes. Dépendances explicites,
  reprises bornées et absence de double lancement ; aucun travail artificiel
  pour consommer des crédits. Vérifier processus et résultats avant de dire
  qu'un agent travaille. Une proposition externe n'est jamais une validation.

### Mesurer et juger chaque tâche

- À chaque tâche confiée à un modèle : identifiant, projet, modèle exact,
  domaine, type de tâche, difficulté, critères d'acceptation, version du contexte
  et paramètres. Mesurer attente, durée d'exécution et, séparément, temps de
  revue et de correction. Conserver échecs, reprises et réponses tronquées.
- Codex juge **le temps et la qualité du travail selon le type de tâche** :
  exactitude, pertinence, complétude et utilisabilité, avec preuves (tests,
  contre-exemples, corrections nécessaires, résultats d'intégration).
  Ne pas reprendre l'auto-évaluation du modèle comme note. Une réponse non
  vérifiée reste non évaluée ; une mesure inconnue reste inconnue.
- Juger par rapport aux consignes réellement transmises. Attribuer séparément
  les défauts du modèle, ambiguïtés du brief, changements de contrat et pannes
  d'outils ; ne pas pénaliser un modèle pour une information qu'il n'avait pas.
- Conserver les évaluations et leurs révisions. Produire des statistiques
  par domaine/type/difficulté/modèle : effectifs, réussite, note, temps médian
  et temps de reprise. Comparer des travaux comparables. Orienter progressivement
  les tâches vers les modèles pertinents après suffisamment de preuves ; ne
  pas confondre rapidité, verbosité et qualité, ni panne d'outil et faute de fond.

### Qualité du code et validation

- **Au plus 1 000 lignes physiques par fichier de code produit ou maîtrisé
  par le projet**, y compris les générateurs et leur code produit. Construire
  des modules cohérents, réutilisables, avec interfaces explicites ; ne pas
  minifier ni découper artificiellement pour contourner la limite.
- Code commenté : expliquer responsabilités, contrats, unités, invariants,
  choix délicats et limites. Les commentaires restent synchronisés avec le code.
- Recenser les dépassements existants et planifier leur découpage sans masquer
  la dette. Les bibliothèques/IP fournisseur et archives figées sont identifiées
  explicitement ; ne pas réécrire une référence validée pour satisfaire un compteur.
- Plusieurs plateformes : sources communes uniques et profils/constantes de
  configuration. Isoler les adaptations nécessaires derrière des interfaces.
  Pas de copie de fichiers communs ni de branches de code presque identiques
  maintenues séparément. Les snapshots de preuve sont des archives tracées,
  pas des sources concurrentes.
- Livrer des **fiches de tests** : objectif, versions/empreintes, environnement,
  procédure, attentes, résultat constaté, preuves et limites/restes à tester.
  Tester le comportement et les cas adverses pertinents ; distinguer simulation,
  synthèse/timing et matériel, ainsi que chaque plateforme.

### Environnement propre

- La propreté est un critère de livraison : supprimer le code réellement mort,
  fichiers obsolètes, artefacts temporaires et processus inutiles de sa tâche.
  Vérifier leurs usages et dépendances, puis tester après nettoyage.
- Conserver sources de travail, références protégées, résultats nécessaires,
  journaux de diagnostic et travaux d'autrui. Inventorier avant une suppression
  large ; ne jamais utiliser un nettoyage aveugle sur un dépôt partagé.
- Séparer sources, tests, documentation, builds et temporaires. Documenter les
  artefacts conservés et leur raison. Ne laisser ni doublons maintenus, ni tâches
  orphelines, ni secrets dans les paquets, rapports ou journaux.
<!-- END MICHAEL MULTIMODEL WORKFLOW v1 -->

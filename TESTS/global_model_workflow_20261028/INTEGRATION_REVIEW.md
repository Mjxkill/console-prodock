# Relecture d'intégration hors fournisseur et hors carte

Relecture séparée du runner et de la file par l'agent métriques/installation,
28 octobre 2026. Ce document n'attribue aucune note automatique de qualité.

## Constats concrets

- Le runner est limité à un paquet texte préparé et un dossier de sortie neuf.
  Il désactive outils et configuration projet du modèle. Le secret est transmis
  par environnement, ses occurrences connues sont masquées dans les sorties.
- La première version vérifiait la taille seulement après `communicate()`.
  Ce n'était pas une borne réelle de mémoire de capture. Le module ajouté
  `process_io.py` lit les deux pipes avec `selectors`, vérifie la borne avant
  accumulation et renvoie les seules données partielles bornées en cas d'erreur.
- Le runner conserve les pannes de commande, délais et réponses tronquées.
  Les durées sont monotones ; les tokens absents restent inconnus. L'import
  du résultat dans le registre est distinct d'une évaluation de qualité.
- L'importeur métriques accepte maintenant aussi `tokens:null` en cas d'échec
  avant décodage, sans le convertir en zéro. Les coûts OpenCode sans devise
  restent une observation sans devise ; ils ne sont pas renommés en dollars.
- La file prend un verrou par session, persiste la revendication avant Popen,
  ne réutilise pas un dossier de sortie et ne relance pas un état ambigu.
  `on_success` désigne une génération achevée, pas une validation humaine.
  Une dépendance exigeant une validation doit être matérialisée par le responsable.
- Deux écarts de préflight ont été signalés au propriétaire : option de
  raisonnement hors DeepSeek et format parent_task_id. Ces gardes doivent être
  alignées avec le runner avant de geler la version distribuée.
- La file est une exécution d'un document chargé au démarrage. L'ajout de
  tâches est vérifié lors de la prochaine exécution de la session ; ce n'est
  pas un abonnement continu aux modifications du fichier.

## Vérifications exécutées

La version lue a passé les 10 tests runner et 11 tests queue existants, avec
des processus locaux factices, sans fournisseur ni matériel. Les tests
métriques et installation ont également été exécutés. Les empreintes finales
et journaux doivent être attachés au manifeste gelé, car les modules du runner
étaient encore en cours de finition pendant cette relecture.

## Installation

`install_workflow.py` ne publie que sa liste explicite de code et trois documents.
Il n'inclut ni paquets, ni prompts, ni secrets, ni tests, ni résultats. Les fichiers
de données déjà présents dans la destination ne sont ni remplacés ni supprimés.
Les consignes existantes sont conservées hors du bloc géré ; un override existant
reçoit ce même bloc et fait l'objet d'un signalement explicite.

L'atomicité est **par fichier**, avec manifeste en dernier, sous verrou. Il ne
s'agit pas d'une transaction multi-fichier. Un échec au milieu d'une mise à jour
peut laisser un mélange de versions : les sauvegardes sont conservées et le
prochain contrôle refuse les divergences de SHA au lieu de les masquer.
L'installation complète doit être vérifiée par root avant son utilisation.

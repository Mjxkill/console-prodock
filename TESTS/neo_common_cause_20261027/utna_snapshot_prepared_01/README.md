# R19 : comparer les lectures individuelles et groupées après SNAPSHOT

Préparation seulement. Aucun matériel n'a été ouvert par le préparateur.
Le RTL et les bitstreams restent inchangés. R21r2 est exclu de cet essai.

L'ancre est la lecture sans commande `utna_readonly_prepared_01/read_20261027_231817` :
contrôle `[0x55544e41,0,0]`, banque initiale nulle pour les adresses testées.
Elle affaiblit l'hypothèse d'un alias permanent, sans trancher le défaut après capture.

Le contrôleur vérifie fichiers, identité USB, verrou Neo exclusif, CPU parqué,
GPU/NCP inactifs et UTNA neuf. Il envoie **une seule commande SNAPSHOT=2**,
attend exactement l'acquittement 1, puis effectue deux passages identiques :

1. Lectures individuelles de `+00/+04/+08` et `+40/+44/+48`.
2. Lecture de trois mots, puis de 32 mots, à `+40`.
3. Retour aux six lectures individuelles, vérification contrôle inchangé.

Les huit en-têtes sont conservés, y compris lorsqu'ils sont erronés. Le contrat
reste strict : chacun doit être `[0x55544e41,1,2]`. Les deux blocs de 32 mots
doivent être identiques. Une erreur de contenu produit FAIL après conservation
des valeurs et déclenche le même retour à R19 que toute erreur/interruption.
Le marqueur `SNAPSHOT_READS_DONE` signifie fin des lectures, jamais validation.

Après la première possibilité de mutation, le contrôleur tente exactement une
restauration du R19 SHA `1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`,
puis vérifie CPU, GPU, NCP et UTNA frais. Les handlers enregistrent SIGINT,
SIGTERM et SIGHUP ; les checkpoints ne peuvent interrompre la restauration.
Les erreurs primaires, erreurs de restauration et erreurs d'écriture du journal
restent distinguées. Aucun accès UART, DDR, SD ou flash, aucune commande GPU.

Les IO OpenOCD et programmation sont celles du contrôleur v3 déjà relu ;
timeout 30 s par observation et 120 s pour le programmeur. Le processus enfant
utilise le même groupe isolé et le même nettoyage à expiration. La restauration
peut redémarrer la ROM ; le CPU est ensuite contrôlé dans sa boucle de parking.

La revue préparée garde `hardware_ready=false`. Une revue root distincte est
nécessaire avant exécution. L'identité R19 repose sur la dernière programmation
enregistrée et la continuité de la carte, pas sur une lecture de configuration.
Le diagnostic ne qualifie pas USB HS, la fréquence des horloges ou la vidéo.

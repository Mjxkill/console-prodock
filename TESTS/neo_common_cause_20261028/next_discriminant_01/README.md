# Prochain diagnostic Neo, sans nouveau routage

Deux plans préparés et relus sur le snapshot exact R22r1 :

- [UMSC : six lectures bornées](USB_READ_PLAN.md), décodeur local prêt.
- [MicroDMA128octets](DDR_MICRODMA_PLAN.md), **conditionnel** : aucun
  payload d'écriture tant que l'isolation ILM/DDR et les caches ne sont pas
  établis. Un CLEAR16×1 doit émettre une rafale de32octets.

La [contre-vérification](INDEPENDENT_CHECK.md) détaille ce qui a été retenu
ou corrigé après quatre avis OpenCode indépendants. Leur exécution est
enregistrée dans le registre projet ; aucune note qualité n'a été inventée.

`local_checks_01/result.json` : 12 tests offline PASS et simulation du RTL
gelé PASS. Le contrôle négatif a reproduit qu'un CLEAR de taille nulle
peut incrémenter done sans accéder à la DDR : cette recette externe a été
corrigée avant tout essai matériel.

**État matériel : aucune action de cet agent.** Root conserve le verrou,
les contrôleurs et la restauration R19. La dernière collecte combinée
établissait un trajet de commande GPU fonctionnel ; elle ne testait pas
la DDR du GPU et son USB restait absent côté PC. Le bitstream reste en
échec STA global documenté. Ces plans ne constituent pas une correction
ni une qualification de la Neo.

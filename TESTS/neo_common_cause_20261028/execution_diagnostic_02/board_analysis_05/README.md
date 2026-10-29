# CLEAR flags0 : résultat matériel confirmé

Le programme distinct d9ad3f70… termine phase10/result1, done2 et busy0.
Les trois vérifications CPU de32mots retrouvent le motif initial, aucun défaut
ou perte signalé. R19 a été restauré. Le binaire ne diffère de BIN02 que par
les flags et l’attente finale de mémoire : offsets432 et900.

Comparaison ciblée : la branche sans transaction du même opcode termine,
alors que la branche couleur non vide reste bloquée. Selon le RTL cette
bifurcation se situe dans RECT_SETUP. Le défaut ne peut plus être décrit comme
un blocage général du transport de commande ou du retour done. Il peut rester
dans la génération native propre au CLEAR, son transport ou l’interface DDR ;
les états internes non exposés n’ont pas été directement mesurés.

Prochain contrôle unique proposé, pas exécuté : COPY565 vers la même adresse,
décrit avec preuve RTL dans ../copy_probe_01/PLAN.md. Aucun nouveau bitstream.

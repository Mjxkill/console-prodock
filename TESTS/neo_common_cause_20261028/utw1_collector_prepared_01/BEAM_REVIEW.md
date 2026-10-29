# Contre-avis Beam et vérification locale

Avis reçu : `TESTS/assisted_reviews_20261026/utw1_collector_beam_20261028_r2/answer.txt`.
L'appel r1 avait échoué sur DNS ; r2 a bien utilisé OpenCode/Ollama hors du
bac à sable, uniquement avec le paquet de texte. Le paquet est antérieur
au raccord de l'adaptateur de provenance et au champ d'identité initiale
séparé. Ce n'est donc pas une certification de tous les octets finaux.

1. **Entrées supplémentaires de `proof_files`** : comportement accepté.
   Toutes les dépendances requises doivent être présentes ; une preuve
   supplémentaire réelle et correctement hachée peut aussi être épinglée.
   Elle est alors vérifiée, pas ignorée. L'affirmation de l'avis selon
   laquelle un fichier fictif passerait est fausse : son ouverture échoue
   au rehash. Les tests `extra_real_pinned_proof_allowed` et
   `extra_fictitious_proof_rejected` reproduisent les deux cas. Une égalité
   stricte n'apporterait pas de garde utile ici et rejetterait les preuves
   supplémentaires de revue.

2. **Deux images, EC, tags et compteurs** : la limite était celle du paquet
   de l'avis, qui ne contenait pas le décodeur complet. Le collecteur
   appelle bien ce décodeur strict figé. Les tests Tcl `unstable`,
   `unstable_ext`, `changed_control`, `ec`, `tag`, `total`, `status`,
   `frame`, `rawid`, `rawcommand` confirment le rejet par le chemin réel
   collecteur → façade de provenance → décodeur. EC non nul est rejeté
   même avec F0 normal. Aucune duplication de ce code n'est nécessaire.

3. **Signal pendant retour à R19** : le signal est effectivement différé.
   C'est le comportement voulu, afin de ne pas interrompre la restauration.
   Un rapport peut contenir à la fois `error=KeyboardInterrupt` (l'essai a
   été interrompu) et `left_startup_verified=true` (le nettoyage a réussi).
   Ces deux résultats décrivent des étapes différentes et ne sont pas
   contradictoires. Les cas `event:restore_r19`, `event:restored_guard`,
   `cleanup_save`, `after_cleanup`, `all_cleanup` le vérifient avec de vrais
   signaux POSIX et des IO simulées. L'IO héritée borne une programmation
   à 120 s et une observation OpenOCD à 30 s ; le paquet de l'avis ne
   justifiait pas son estimation unique de 30 s.

Aucune modification du protocole ou réduction des gardes n'est retenue
sur ces trois propositions. Le refus sans revue exacte, la restauration
après échec et les limites matérielles restent explicites. L'avis ne
remplace ni l'audit du routage ni le futur essai sur Neo.

# Contre-revues du cache — décisions locales

DeepSeek `game_deepseek_mesh_cache_code_r1` et Beam
`game_beam_mesh_cache_lifecycle_r1` ont reçu les sources complètes et les
preuves R2. Les deux réponses sont des avis, distincts des tests exécutés.

- **Accepté et corrigé en R3** : réutiliser un cache avec une autre adresse
  de mapping pouvait ignorer une publication nécessaire. Le test actuel échoue
  sur le module R2 conservé (`tests/review_counterexample_r1/old.log`) et passe
  avec R3. Changer la base ou la taille invalide les bits de validité. Le rendu
  actuel utilise un cache neuf par ouverture : ce cas n'était pas un défaut
  observé dans GM1 ou sur carte.
- **Tests ajoutés** : échec d'agrandissement après données valides, échec de
  création de la deuxième banque, réentrée immédiate dans la même activité
  après BACK. Les 80 images sélectionnées conservent exactement commandes,
  mémoire complète et codecs, sur les deux profils.
- **Pas de correction justifiée** : l'échec d'ouverture laisse temporairement
  `active`, mais main appelle `l3_render_close` sur cet échec ; close libère les
  allocations et retire `active`. Aucun défaut de ce chemin n'a été reproduit.
- **Portée de l'atomicité** : l'allocation précède toute écriture d'un appel
  `publish`. Deux appels sommets/faces ne forment pas une transaction atomique ;
  un échec du second arrête le rendu avant DRAW/PRESENT. Aucune promesse de
  restauration de la mémoire de la page inactive en cas d'échec.
- **Écrivain unique** : seules les publications dynamiques de `maze_render`
  écrivent les banques relatives 26 et 27 MiB. Eau/oiseaux restent sous 14 MiB,
  puzzles sous 15 MiB, UI 20–24, meshes statiques 24–25, shooter 28–32.
  Un futur écrivain de 26–28 devra invalider le cache. Aucune comparaison ne lit
  la VRAM ; le contexte privé n'est pas un framebuffer ou un atlas GPU.
- SUBMIT synchrone, flush final, TARGET/CAMERA et PRESENT restent inchangés.
  Les propositions antérieures de supprimer un flush ont été réfutées et ne
  font pas partie de ce candidat.

Strict et ASan/UBSan passent ; LeakSanitizer reste désactivé à cause du ptrace
du sandbox, comme documenté dans le rapport initial. Aucun FPS matériel déduit.

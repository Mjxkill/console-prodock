# PP1 — arrêt conservé, SC1 rétabli

Essai matériel FAIL avant la visite animée. ELF R6 `d8f65131f8ad4834501850d39354be98a666e484822085004dea13c8fd1c0a48`. Première image, circuit, blocs, formes, fusion1024, maison3D et Simon : comparaisons exactes PASS, compteurs GPU nuls.

La fixture boss a échoué lors de la comparaison globale des4MiB28–32 :2335228octets différents, CRC réel`d05a6c9c`, attendu`7f5699bd`. Le HUD du boss a passé sa comparaison. La tour3D et le tour animé n’ont pas été exécutés. Aucun FPS/p99 R6 de jeu normal n’est disponible pour cet essai.

Le contrôleur a restauré SC1 et vérifié son identité après progression : PID2376, startticks21307354. Dernier DISPLAY : presents1929120, erreurs/underflow/invalid/sprites/fault tous0. Sauvegarde V4 initiale et après arrêt identique. Aucun FPGA, noyau, SD ou flash écrit. UART et verrou ont été libérés par sortie du contrôleur.

Diagnostic local ultérieur : la comparaison englobait2397568octets non publiés. Le vrai publisher R6 sur RAM empoisonnée vérifie835584octets de champs et961152octets d’atlas, sans accès GPU aux trous ; même contrôle720p. Cela explique un défaut de méthode, mais ne prouve pas encore que tous les octets utiles du matériel étaient corrects. PP2 exige leur comparaison exacte avant de poursuivre.

Preuve locale : `games/luma3d/candidates/arcade_polish_r1/publication_20261027_r1/result.json`. Le rapport PP1 reste inchangé. Les captures mémoire concernent des données/atlas et pixels3D, pas une relecture complète des palettes/descripteurs/compositeLCD.

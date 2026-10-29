# Contre-revue des avis sur le mot version nul

Avis exécutés sur la capture réelle et les sources figées :
`TESTS/assisted_reviews_20261026/neo_utna_header_zero_deepseek_r1/answer.txt`
et `TESTS/assisted_reviews_20261026/neo_utna_header_zero_beam_r1/answer.txt`.
Aucun des deux modèles n'a exécuté ses propositions. Aucun patch n'est appliqué.

Les deux avis retiennent correctement l'écart `[ID,0,1]`, la constante RTL1,
la stabilité des deux lectures et l'absence d'essai R21r2. Ils proposent
utilement de distinguer contenu FIFO/banque et lecture AHB par des lectures
individuelles, inversées et en rafale.

Points rejetés ou précisés :

- Beam déduit trop tôt que count1 prouverait l'émission de la constante1.
  Le compteur indique32 réceptions au niveau HCLK ; il ne prouve pas leur
  contenu. Le bit peut être faux avant la banque ou à sa lecture.
- Une capture lue deux fois ne démontre pas une défaillance reproduite sur
  plusieurs ARM. Un seul ARM a été exécuté.
- Le snapshot est pré-clear, mais la version constante1 ne dépend pas de
  cet état. Le reset logique commun ne suffit pas à expliquer pourquoi la
  version resterait0 tandis que la commande1 serait correctement capturée.
- L'absence de garde `busy` autour de chaque réception n'est pas à elle
  seule un défaut. L'émetteur produit32 mots, et l'index modulo32 se remet
  naturellement à0 pour la banque suivante. Une33e réception serait une
  violation supplémentaire à démontrer, pas une explication acquise.
- Le correctif compteur proposé par DeepSeek réutilise `cmd_pop` du domaine
  USB dans la logique de réception HCLK sans passage CDC défini. Il n'est
  ni applicable tel quel, ni justifié par la capture ; aucun RTL n'est modifié.
- Rendre le mot version constant hors du trajet testé masquerait le témoin
  qui vient de révéler un écart. Cela n'est pas un correctif du problème observé.
- Les RAM physiques n'ont pas de reset natif, mais la synthèse ajoute une
  logique de validité/reset. Il faut vérifier cette logique complète avant
  d'affirmer que la banque ne serait pas remise à zéro logiquement.

La simulation fonctionnelle avec primitives Gowin des modules netlist exacts
a depuis passé trois phases/rapports d'horloges, dont HCLK plus lent que USB,
et le témoin négatif attendu. Ce résultat ne reproduit pas le défaut carte et
ne désigne donc pas à lui seul une cause. Il ne couvre ni les délais physiques
ni l'étage de bus amont. Les résultats sont dans `../utna_header_netlist_01/`.

Une hypothèse supplémentaire plus directement discriminante est conservée
dans `../usb_video_result_20261027_223943_offline/bit6_alias_hypothesis.json` :
l'en-tête observé égale exactement les trois registres de contrôle après ACK1.
Une commande distincte de sa séquence permettrait de tester cet alias sur le
bitstream existant, sans affaiblir le critère d'en-tête. Cette expérience reste
à la main de root ; aucune sonde supplémentaire n'a été ouverte ici.

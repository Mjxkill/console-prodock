# Disposition des avis DeepSeek et Fable sur le chargement

Avis terminés : `neo_deepseek_loader_r1/answer.txt` et
`neo_fable_loader_r1/answer.txt` sous `TESTS/assisted_reviews_20261026/`.
Le paquet était figé avant la lecture complémentaire UG704 et la comparaison
bit à bit des trames ; leurs conclusions ne remplacent pas ces vérifications.

Les deux avis reconnaissent l'absence de preuve causale d'un bug loader.
Retenus : différence du mot 0x0A, séquences/temporisations distinctes,
nécessité de conserver le même FS et de distinguer conversion SVF du
programmeur officiel live. La vérification des volumes/trames suggérée par
Fable a été exécutée hors ligne et est consignée dans `analysis.json`.

Corrections aux avis :

- Le statut loader satisfait déjà le masque du SVF :
  `0x26220 & 0x602F == 0x6020`. Ce n'est pas une divergence de réussite.
- Le CRC matériel reste actif selon UG704 ; l'absence de checkCRC logiciel
  n'est pas une absence de contrôle de transmission. SecurityBit ON explique
  l'absence de readback SRAM sans changer les fichiers.
- Deux échecs avec deux outils n'excluraient pas toute cause de chargement
  commune. Un succès isolé ne prouverait pas davantage un bug du loader.
- Une fréquence de 6 MHz présente dans le SVF ne prouve ni sa prise en
  charge par la CLI live ni son innocuité sur toutes les routes. Employer
  une fréquence commune effectivement prise en charge, sans changer deux
  variables à la fois. Aucune coupure physique supplémentaire n'est imposée
  ici comme condition préalable abstraite.
- L'état TX bloqué n'est pas assimilé à CTS bas : le flux matériel a été
  explicitement désactivé dans le contrôleur et aucune mesure CTS ne prouve
  cette hypothèse. Un écho CPU n'est pas disponible dans la ROM parking.
- Le SVF éventuellement incomplet ne prouve pas que l'opération live 2
  est incomplète ; la syntaxe acceptée d'une conversion ne qualifie pas
  l'intégrité des initialisations mémoire.
- Aucun patch checksum n'est appliqué. La proposition Fable utilisant
  directement `_hdr["CheckSum"]` est notamment impropre : parseHeader ignore
  les commentaires et cesse les clés à 0x3B, tandis que le 0x0A des FS étudiés
  est en fin de fichier. Le champ n'est pas affiché dans les journaux du
  parseur existant. Une chaîne absente provoquerait stoul invalide.

Les points de comparaison sont prêts pour une éventuelle décision du parent.
Aucune nouvelle programmation, lecture de périphérique, modification du
loader ou compilation FPGA n'a été effectuée par ce sous-chantier.

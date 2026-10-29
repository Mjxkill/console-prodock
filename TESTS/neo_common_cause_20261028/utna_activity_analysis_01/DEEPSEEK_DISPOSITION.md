# Avis ciblé après la nouvelle capture d'activité

DeepSeek V4.1 Flash a relu uniquement le paquet de la nouvelle question dans
`TESTS/assisted_reviews_20261026/neo_utna_activity_boundary_deepseek_r1/`.
Aucun outil, accès carte ou modification ne lui était autorisé. Le résultat
ne constitue pas une autorisation de construire ou programmer.

- **Accepté :** le scénario initial unique avec écriture correcte ultérieure
  est insuffisant ; la persistance ne désigne pas la FIFO ou la banque.
  Une lecture prématurée récurrente, à elle seule, ne prédit pas durablement0
  si la même case a fini par recevoir1 : elle demanderait une autre condition
  telle qu'une écriture perdue, une adresse différente ou un effacement.
- **Accepté :** les données non nulles en classes0/2/3 ne valident pas classe1.
  Le drapeau global du groupe0 continuellement invalide ne rendrait pas les
  mots0/2/3 non nuls dans le réseau compilé. La lane1 ou la case1 restent
  distinctes de ce drapeau de groupe.
- **Accepté sous conditions :** un témoin HCLK avant banque sépare sa frontière
  d'entrée du résultat relu. Il ne sépare pas à lui seul FIFO et émission PHY.
  Les mots0/2 témoins doivent venir du même flux reply, et le compteur doit
  compter exactement les captures index1, une par remplissage attendu.
- **Correction de sa recommandation busy :** l'ajout d'un filtre busy au seul
  témoin masquerait des événements que la banque actuelle accepte encore.
  Capturer la même condition `!hreset && reply_valid` et signaler à part les
  événements hors busy est plus fidèle. Ne pas convertir reply_valid en simple
  détection de front : c'est un mot transféré par cycle valide.
- **Accepté :** zéro capture, compte anormal ou sentinelles incorrectes ne
  localisent rien. Témoin1=1 et banque1=1 après un nouveau placement n'identifie
  pas la cause de la version0 de R19.
- **Limite conservée :** les trois simulations du graphe routé, sans SDF,
  n'établissent pas le timing physique ou la forme du reset de la carte.

La contre-simulation `masked_activity/result.json`, exécutée indépendamment
après le paquet, complète la preuve locale : une lane1 forcée0 conserve les
128 mots de l'activité sauf les quatre versions. Ce test n'a pas été exécuté
par DeepSeek et n'était pas fourni dans son paquet initial.

Le prochain témoin demeure une proposition. Aucun RTL, bitstream ou contrainte
n'a été modifié ; aucune conclusion globale sur la Neo n'est tirée.

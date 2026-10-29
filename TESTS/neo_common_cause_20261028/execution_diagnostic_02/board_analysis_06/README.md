# COPY réel rejeté, contenu mémoire désormais mesuré

Résultat root `root_copy_readback_run_01`, SHA et fichiers dans `facts.json`.
Aucun accès carte effectué par cet agent. R19 exact restauré par root.

- Le premier programme finit phase8/résultat−5. Ce code couvre le refus
  constaté par `check_gpu_errors` après completion, pas seulement un timeout.
- Avant/après la lecture CPU, done2, status0, rejected1, errors/lost0.
  Les captures après la commande montraient déjà cet état terminé/rejeté.
- Le lecteur CPU588B exécute32/32loads, cache0, sans trap. Clear ILM,
  nouvelle exécution et retour ROM vérifiés par le contrôleur.
- Les128octets lus sont exactement le seed initial. Les32octets destination
  n'ont pas la copie attendue ; les96octets canaris sont intacts. Les huit
  différences attendues avec une copie réussie ne sont pas des erreurs CPU.

| Essai root sur R19 | Completion GPU | Mémoire CPU après |
|---|---|---|
| CLEAR couleur non vide | done1, busy1 durable | seed intact,32loads terminés |
| CLEAR flags0 | done2, busy0, aucun rejet | seed intact |
| COPY non vide | done2, busy0, rejected1 | seed intact,32loads terminés |

Ces trois résultats ne sont pas un même blocage. COPY produit une completion
d'erreur ; CLEAR non vide reste en attente. Le résultat mémoire ne mesure
pas les transactions natives : il ne prouve pas à lui seul qu'aucune requête
n'a été présentée, ni qu'aucune écriture du même contenu n'a eu lieu.

Dans les lectures CSR, `v1_rejected` (+0x34) vaut1 et `geom_errors` (+0x4c)
vaut0. Le RTL définit `v1_rejected=geom_errors+shader_rejected` : le rejet
observé est donc du côté moteur pixels. Les chemins possibles incluent
`bad_header`, cible invalide, `copy_bad`, ou la branche d'état non reconnu.
Le header1d000000 observé ultérieurement ne prouve pas tous les champs
du paquet local ni les valeurs au front de validation.

Correction d'interprétation : la capture lit26mots depuis e9001000. Son
dernier mot est l'offset **0x64**, `geom_cycles`, qui vaut4. Ce n'est pas
un registre target_valid à0x68. `target_config_valid` est un fil interne
entre les moteurs pixels/géométrie et n'est pas publié dans ces26CSR R19.

Le paquet programmé satisfait numériquement la validation RTL : source
[12000000,12000020), destination[12000020,12000040), largeur16, hauteur1,
stride32, réservés0. L'égalité source_end=destination_base n'est pas un
chevauchement avec le test strict `<`. Le banc complet et le nouveau banc
DeepSeek indépendant acceptent ce paquet. La revue VG/VO ne retrouve pas
l'ancien défaut de deux CE dans le pipeline C du DSP src_end.

Cela n'explique pas encore le rejet physique. Les registres internes réellement
capturés, les sorties d'arithmétique et la branche de refus restent inconnus.
Le prochain contrôle proposé est le même COPY avec seule étendue demandée
vide (w6=0), conservant source/TARGET/adresses et validations. Sa préparation
est dans `../copy_empty_01` ; aucun nouvel essai matériel n'est revendiqué ici.

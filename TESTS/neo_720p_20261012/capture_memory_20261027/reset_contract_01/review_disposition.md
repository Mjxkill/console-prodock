# Disposition des avis sur le correctif R21r1

27 octobre 2026. Les modèles relisent des paquets de texte figés, sans outils.
Leurs réponses ne sont ni des exécutions de tests ni une qualification carte.
Les décisions ci-dessous sont vérifiées par le parent contre les artefacts.

## Premier lot : correction et propositions

Les trois avis `neo_reset_patch_{fable,deepseek,beam}_r1` ne trouvent pas de
contre-exemple logique déterministe au correctif des deux pertes LOCK
reproduites. Fable recalcule plusieurs temps des journaux et confirme leur
cohérence avec le banc v2. La synthèse isolée passe ensuite ; elle ne route
ni ne programme la carte.

| Proposition / réserve | Décision et preuve |
|---|---|
| Fable : une capture par la première chaîne seule ne force pas forcément une nouvelle qualification | Retenu comme renforcement, sans attribution à la panne physique. Candidate02 ajoute `pll_ready = pll_ae350_lock && ae350_por_n`. Le test injecte explicitement une assertion de la première chaîne seule : candidate01 échoue à 25 ns, candidate02 attend 50 000 050 ns. Voir `root_capture_asymmetry_02`. |
| Fable : le port `rst_key_n` pourrait aussi arrêter la DDR et créer une boucle | Vérification du fichier SoC complet : déclaration, réduction `unused`, deux bascules `init_sync` uniquement. Aucun consommateur dans la DDR. Le second paquet fournit le fichier complet. |
| Beam : absence de synchroniseur dédié de désassertion | Formulation rejetée : `ready_meta` et `init_sync` sont précisément les deux chaînes de bascules. Cela ne dispense pas de vérifier leur réalisation physique. |
| Tous : nouveaux trajets de reset à examiner après routage | Retenu. Aucune exception SDC ajoutée. Examiner les pins réellement mappées, leurs horloges et les rapports recovery/removal ; ne pas copier les noms PRESET proposés par certains avis pour des cellules qui utilisent CLEAR. |
| Beam : ajouter `!command_valid` à l'autorisation | Non retenu sans contre-exemple. Les cas10/12 envoient déjà une commande valide pendant POR actif ; le contrôle du nombre de relâchements surveille les impulsions supplémentaires. Les registres de commande sont consommés au front suivant comme dans le protocole initial. |
| DeepSeek : préfixe UART conservé si clk50 s'arrête | Limite confirmée du parseur existant : son délai compte des cycles actifs, pas le temps mural sans horloge. Aucun nouveau watchdog ni reset asynchrone du parseur n'est introduit dans ce correctif ciblé. Les essais d'arrêt d'horloge ne qualifient pas la réception UART interrompue au milieu d'un octet. |
| DeepSeek : ajouter un verrou `loss_seen` sur la même entrée | Non retenu : il ne résout pas l'hypothèse de deux chemins capturant différemment le même événement. Le couplage retenu utilise la détection de la première chaîne. |
| DeepSeek : `WAIT_CYCLES < MIN_LOCK_CYCLES` pourrait violer le minimum | Paramétrage hors du candidat : les valeurs effectivement synthétisées et testées sont 2 500 000 et 104 000 cycles. Ce snapshot n'est pas qualifié pour des paramètres arbitraires. |
| Métastabilité « auto-réparée » ou durée garantissant toutes les horloges actives | Ne pas transformer ces formulations en garanties analogiques. Les simulateurs idéaux n'établissent ni MTBF, ni largeur minimale physique, ni présence de toutes les horloges pendant le délai. |

L'échec initial du banc candidate01 provenait d'un rendez-vous
`$time % 100 == 0` devenu inaccessible après la reprise déphasée de clk50.
Le banc v2 supprime uniquement ce rendez-vous. Les anciens journaux sont
conservés et ne sont pas mélangés aux preuves du banc corrigé.

## Second lot : couplage minimal

Le second paquet fournit candidate02, le SoC complet, la preuve structurelle
indépendante et le test d'injection avec son témoin négatif. Il précise que
la simulation mappée complète est encore en cours au moment de l'envoi.

DeepSeek et Beam confirment l'absence de boucle de démarrage : la première
chaîne ne dépend pas de `trial_request`. Ils confirment aussi l'absence de
nouveau reset DDR et la conservation de la qualification. Leurs demandes
de vérification physique restent à faire après production des résultats de
routage ; un rapport post-route ne peut pas être un préalable à son propre
routage. Aucun essai sur carte n'en découle automatiquement.

La réserve de traçabilité DeepSeek mélange trois périmètres distincts :

- `changed_modules` décrit les modules de la **netlist** modifiés ;
- `source_changes` décrit les deux fichiers du **snapshot source** ;
- `candidate_02/candidate.diff` décrit seulement le delta candidate01 vers
  candidate02, et comprend le banc de test `exact_chain.sv`.

Il n'y a pas de fichier source SoC modifié : son nouveau CLEAR traduit dans
la netlist le raccord fait dans le source top. Le diff source cumulatif
R21r1 vers le candidat final est désormais explicite dans
`source_delta_from_r21r1.diff`. Les comparaisons structurelles vérifient
aussi les modules entiers, les INIT et la restauration du texte hors cône
modifié ; ce n'est pas une simple confiance dans une liste déclarée.

Fable r2 confirme également le couplage logique et les consommateurs SoC.
Deux détails de son avis sont corrigés par le parent :

- L'étirement par deux bascules n'est pas garanti à **deux périodes
  complètes** après une remontée asynchrone : selon la phase, il peut être
  compris entre environ une et deux périodes, hors délais physiques. Aucun
  minimum public de capture CLEAR n'a été établi ; on ne peut donc pas
  affirmer que cet étirement le dépasse « largement ».
- L'invariant proposé exige `delay_done=0` une picoseconde après l'assertion
  de la première chaîne. Il est incorrect pour ce RTL : `ready_meta` et
  l'autorisation tombent asynchronement, mais `delay_done` est volontairement
  effacé au prochain front clk50. L'invariant utile porte sur l'absence
  d'autorisation/POR, pas sur l'effacement asynchrone du compteur.

Le commentaire historique en tête du SoC décrit encore le raccord direct
DDRready. Il n'est pas corrigé dans le fichier commun ni dans le parent
figé : le raccord spécifique de ce candidat et son diff cumulatif sont
documentés ici. Cette imprécision historique n'est pas une différence
fonctionnelle supplémentaire du candidat.

**État de cette note :** les six avis sont terminés et examinés. La décision
de routage reste conditionnée au résultat final du banc mappé. Aucun
bitstream chargé et aucune qualification physique annoncée.

# Audit statique R19 : portée et avis contradictoires

`audit_reviewed.py` a été écrit puis exécuté par l’orchestrateur pendant la
revue indépendante Fable. `sdf_cones_01/result.json` contient 114 paires
origine/broche, chacune regroupant éventuellement plusieurs chemins, vers
cinq bascules du transfert CLEAR. Ce ne sont pas 114 chemins STA individuels.

Les calculs conservent les trois corners, le clock-to-Q, les arcs de cellule,
les INTERCONNECT, le skew depuis une racine commune et le check setup/hold.
Ils ne traversent pas une bascule comme une porte combinatoire. Les types de
primitives non pris en charge sont des frontières, jamais des fils à délai
nul. Une première vérification de schéma a explicitement arrêté l’analyse
sur les arcs CLEAR→Q asynchrones ; ils ont été séparés du clock-to-Q.
Une seconde a arrêté sur OSER16 hors des cônes ; cette primitive est maintenant
une frontière déclarée, pas un arc interprété approximativement.

Le self-loop pending a une borne setup de +1,773 ns et le rapport Gowin
indique +1,780 ns. Ce recoupement ne qualifie pas tous les chemins et ne
prouve pas pourquoi les 7 ps diffèrent (arrondis, arcs/fronts ou chemin retenu).
La marge brute minimale vers native_valid vaut +3,336 ns ; les chemins CLEAR
spécifiques vers CE donnent au moins +4,392 ns. Les sources amont elles-mêmes
ne sont pas qualifiées par cette borne du dernier étage.

## Reset non couvert par le SDF

`reset_coverage_01.json` inventorie 2 612 pins RESET raccordées en .vo au
split INV `u_accel/u_v1/u_pixels/gowin_split_inv_from_n1617_s2`.
Aucune n’a d’INTERCONNECT SDF. L’entrée et la sortie de l’INV n’en ont pas
non plus ; son IOPATH à zéro ne donne pas le délai du réseau absent.

Le pilote réel de l’entrée `gpu_debug_state[48]` est
`u_accel/engine_resetn_4_s0`, primitive DFFCE sur gpu_clk, D connecté à
`gpu_debug_state[42]`, INIT=0. Il ne s’agit pas d’une entrée externe IBUF.
L’absence SDF ne prouve pas un reset physiquement coupé : c’est une absence
de couverture de ce modèle de délais, que le résultat conserve explicitement.

## Revue Fable

La première session a expiré sans réponse finale : aucun avis acquis.
La deuxième réponse (`../neo_fable_netlist_02/answer.txt`) confirme le calcul
partiel et le rapprochement du self-loop avec STA. Ses limites utiles sont
retenues, mais les conclusions suivantes sont rejetées :

- Une absence de ligne dans un rapport STA fini ne prouve pas que le chemin
  n’a pas été chronométré ni contraint. Il faut lire la portée du rapport.
- L’origine des 7 ps ne peut pas être affirmée à partir des seules valeurs
  agrégées fournies.
- Le petit parseur proposé doit normaliser les nets vectoriels Verilog ;
  `gpu_debug_state [48]` ne doit pas être lu comme `gpu_debug_state` seulement.
  Notre inventaire utilise le parseur existant qui normalise ces expressions.

Une troisième revue indépendante reçoit le pilote exact et la couverture
des 2 612 destinations pour poursuivre cette contre-vérification.

Tous ces résultats restent des audits en lecture seule. R19 conserve son
statut timing global FAIL. Aucune carte, source commune ou configuration
FPGA n’a été modifiée par cette branche de travail.

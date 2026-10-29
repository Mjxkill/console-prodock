# COPY0 à bases identiques : rejet confirmé, overlap seul insuffisant

L’essai root_same_base_run_01 est terminé. Deux captures après opération
montrent done2, busy0, rejected1, errors/lost/geom_errors0, geom_cycles4.
Le programmeMD12 finit phase8/résultat−5, après completion rejetée.
Restauré R19 : result.json final=true, garde de retour présente, aucune erreur
contrôleur. Les fichiers bruts et leurs SHA figurent dans facts.json.

Les comparaisons CPU sont32/32/0 : aucune image finale du scratch n’a été
lue dans cet essai. Le bus natif n’est pas exposé ; aucun zérotrafic physique
n’est revendiqué. La source du firmware est bien égale à la destination et
son stride égale le stride destination. Ce changement neutralise le terme
RTL overlap&&(base_diff||stride_diff), mais pas les autres validations.
Le même rejet ne soutient donc pas une explication par ce seul terme,
sous réserve que les registres internes aient effectivement ces valeurs.
La capture observe les headers et les comptes, pas les256bits COPY locaux.

## Ce que les CSR peuvent encore distinguer

+0x34 additionne les rejets des pixels et de la géométrie ; +0x4c sépare les
rejets géométrie. Ici ceux-ci restent0 : le rejet est côté pixels. Mais les
chemins bad_header, target_valid faux au DECODE, descriptor_bad du moteurCOPY
ou défaut d’état peuvent avoir exactement le même tuple done2/busy0/rej1.
+0x64=geom_cycles exclut explicitement l’état PASS, pendant lequel le shader
travaille. Sa valeur4 ne dit donc pas que COPY a pris4cycles ni quel rejet a
été pris. Aucun CSR actuel n’expose les3bits descriptor_bad.

## Un seul prochain contrôle proposé

Repartir exactement du MD12 de ce dernier essai et changer **COPY w2**
`00100001→00010001` : largeur source16pixels→1pixel, hauteur1 conservée.
Ne changer ni TARGET, ni source/destination, ni stride32, ni étendue0×0.
Ainsi src_end reste12000040, et le terme overlap reste neutralisé. Les
validations dépendant de la largeur et la capture du champ changent ; le
calcul du bordsource change aussi, sans produire de DMA pour l’étenduevide.

Si cela réussit, on distingue une sensibilité au champ largeur/aux chemins
de données associés, sans prouver sa cause. Un bit de largeur perdu localement
est un contre-exemple logique testable ; il n’est pas un défaut matériel
observé. Si cela rejette encore, les CSR ne choisissent toujours pas entre
les portes internes. Il faudra alors une observation ciblée, pas présenter
l’essai comme une identification du comparateur fautif.

Cette proposition est analysée dans copy_width_discriminant_01 ; aucun
firmware, contrôleur ou nouveau bitstream n’est chargé par cet agent.

## Fréquences : ne pas confondre les domaines

Le R19 exact lie l’entrée de référence et le pontCPU-DDR à50MHz ; le bus
vidéo/AHB est nominalement80MHz depuis PLLAE350 ; le moteur GPU et l’arbitre
sont dans le domaine clk_out de l’IP DDR, nominalement75MHz (DDRmémoire300MHz).
Sources, paramètres PLL, SDC et liaison netlist sont liés dans clock_evidence.json.
Ce sont des fréquences de conception, pas une nouvelle mesure physique.
Les anciens bancs à83,3/71,4 et100/62,5MHz étaient des variations de simulation,
pas la fréquence déclarée de la carte. Le nouveau banc utilise80/75MHz idéaux
avec deux phases. Aucune conclusion de timing physique n’en est déduite.

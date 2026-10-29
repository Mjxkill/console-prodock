# Relecture indépendante du rejet COPY R19

Lecture seule du RTL figé, de la netlist R19 exacte et de son VO routé.
Aucune compilation ni accès carte. **Aucun nouveau défaut de mapping n'est
établi par cette relecture. L'ancien défaut de pipeline C à deux CE n'est pas
présent dans le calcul `src_end` de ce R19.**

## Chemin source conservé en fabric puis DSP

Les 256 bits `packet_0` sont présents comme DFFRE, tous sur `gpu_clk`,
CE `n7630_6`, RESET GND. Ce reset absent du payload correspond au RTL :
seul le contrôle est remis à zéro et une commande doit être recapturée avant
usage. La LUT d'enable est `n7630_s2`, INIT 16'h4000, entrées
`state_0[4], resetn_copy, state_parent[41], l_31_18` ; `l_31_18` est vrai
uniquement si les quatre autres bits de l'état local sont nuls. C'est donc
IDLE + COPY_START + reset libéré. L'absence de l'attribut texte syn_preserve
après synthèse n'est pas une disparition des bascules : elles sont comptées.

`n421_s1` produit `src_end[32:0]` à partir de :

- A = zéro-étendu packet_0[111:96] (stride source) ;
- B = zéro-étendu packet_0[79:64] (hauteur source) ;
- C = zéro-étendu packet_0[63:32] (base source).

AREG, BREG, PREG, C_IREG et C_PREG sont BYPASS. OREG est CLK0/CE0,
CLK={GND,gpu_clk}, CE={VCC,VCC}, RESET={GND,GND}. Le registre de sortie
est donc mis à jour chaque cycle ; aucun couple de CE fetch/issue n'est
absorbé dans le pipeline C. Tous les paramètres du DSP et les ports
A/B/C/CE/RESET/CLK/DOUT correspondent dans le VO post-routage, après seule
normalisation des préfixes hiérarchiques. Cela prouve le mapping publié,
pas son comportement temporel physique.

Le RTL fait IDLE/capture, CAPTURE_WAIT, CHECK, VALIDATE : au front CHECK,
le registre src_end a eu un front complet avec le nouveau packet_0. Les
3 bits descriptor_bad sont ensuite enregistrés avant leur consommation.

## Destination et comparaison G22

Le calcul local dst_end a été fusionné avec `color_end` du parent gpu_v1.
Son producteur est `n1353_s`. A/B/C sont enregistrés sur CLK0 avec le **même
CE0** `n37855_9` (capture TARGET), C_PREG est BYPASS, OREG est CLK0/CE1
avec CE1=VCC. Cela ne correspond pas non plus à l'ancien défaut des deux
registres C consécutifs aux enables différents. Les bascules d'entrée du DSP
peuvent légitimement représenter les registres target indépendants du packet.

G22 n'emploie pas exactement le même RTL COPY : R19 ajoute le paquet local,
CAPTURE_WAIT, VALIDATE et réutilise les différences locales source_t/source_l.
Dans G22, n421_s1 a OREG BYPASS ; la registration src_end est hors de cette
primitive. Les différences de paramètres ne prouvent donc pas une erreur.
Les deux autres DSP du COPY R19 calculent les adresses de lignes ; certains
CE diffèrent selon le registre, ce qui ne suffit pas à leur appliquer le bug
historique. Leurs résultats ne servent aux requêtes mémoire qu'après la validation du descripteur.

## Paquet matériel observé et séparation des hypothèses

Le paquet de la sonde est :
`1d000000 12000000 00100001 00000020 00000000 00000000 00100001 00000000`.
Avec TARGET base 0x12000020, stride 32 et hauteur 1, les valeurs attendues
sont src_end=0x12000020, dst_end=0x12000040. Les deux surfaces sont adjacentes,
et le test strict dst_base<src_end est faux : aucune superposition. Les
largeur/hauteur/stride/réservés de ce paquet satisfont les trois validations
RTL. Cette arithmétique ne prouve pas que les valeurs internes physiques
étaient celles attendues lors du rejet.

Le parent gpu_v1 peut rejeter COPY avant son démarrage si target_valid est
faux, ou après COPY_DONE si copy_bad est vrai. L'observation d'un compteur
rejected global ne distingue pas ces deux chemins. Une capture externe
correcte du paquet ne prouve pas non plus le contenu des 256 DFFRE locaux ni
src_end/color_end au front CHECK.

Prochaine expérience proposée, sans nouveau bitstream : garder les mêmes
adresses et le même descripteur source, mais mettre la largeur demandée w6 à
zéro (w6=0x00000001). Le RTL valide toujours les mêmes contraintes, puis CLIP
termine sans READ0/WRITE car l>=r. Si cette commande est encore rejetée, le
problème précède l'accès mémoire ; si elle finit proprement mais la copie non
vide rejette, le constat localise une différence de séquence, sans prouver la
cause. Vérifier auparavant le bit target_config_valid déjà observable si son
registre public est accessible et son identité établie. Ne pas transformer
cette proposition en essai automatique ni changer les gardes de scratch.

Les paramètres exacts, connexions et SHA sont dans facts.json. Ce rapport ne
qualifie ni DDR, ni arbitre, ni timing, ni toute l'équivalence du GPU.

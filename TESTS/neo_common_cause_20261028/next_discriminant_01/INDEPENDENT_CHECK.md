# Contre-vérification des quatre avis externes

Les quatre générations se sont terminées normalement et ont été importées
dans `metrics.sqlite`. Cela mesure leur exécution, **pas leur qualité**.
Leurs réponses et paquets restent inchangés. Aucune note automatique,
aucune évaluation de l'auteur par lui-même n'est inscrite dans le registre.

| Modèle exact | Tâche | Durée observée |
|---|---|---:|
| deepseek-v4.1-flash | Contrat de lecture UMSC | 79,660 s |
| beam | Décodeur UMSC et tests adverses | 142,854 s |
| minimax-m3.1-flash | Carte scratch et isolation | 404,202 s |
| glm-5.3-flash | Séquence microDMA conditionnelle | 234,790 s |

## UMSC : retenu et corrigé

DeepSeek et Beam placent correctement propriétaire au bit8 et demande au
bit9. DeepSeek relève correctement que chaque lecture recharge le watchdog.
Ces deux points sont retenus, contre l'ancien commentaire RTL incomplet.

Leur traitement de `highspeed=1/online=0` ne doit pas servir à conclure à
une incohérence matérielle. Les deux synchroniseurs sont indépendants ;
un état de transition est possible. Le décodeur final conserve les valeurs
et changements, sans les transformer en FAIL. Le refus de propriété
firmware porte sur le contexte volontairement sans firmware actif.

Le code proposé par Beam est un prototype permissif : il accepte les
offsets seuls, convertit les types, ne vérifie pas uint32, tags ni ordre,
et une seule occurrence de chaque adresse suffit à son contrôle de
complétude. La consigne originale ne fixait pas encore un format exact à
six lectures : ces durcissements sont **des exigences d'intégration
ajoutées**, pas tous des défauts intrinsèques du modèle. Ils sont appliqués
dans un décodeur séparé et couverts par des tests explicites.

## DDR : retenu et corrigé

Minimax a correctement résolu les paramètres de l'anneau : 512 MiB à partir
de 0x20000000. Une lecture du seul défaut `ddr_subsys.RING_BASE=0x10000000`
serait erronée pour cette instance. Le scratch candidat est donc hors ring.
La distinction entre cache désactivé et satp=0, et celle entre fence et
visibilité à un autre maître, sont retenues.

Deux erreurs numériques de sa réponse sont corrigées :

- la limite `33'h040000000` est **0x40000000, soit 1 GiB**, pas 16 GiB ;
- le vieux test de 1024 mots32 couvre `0x12000000..0x12000fff`, pas
  `..0x120003ff`. Il fait bien 4096 octets, donc il excède ce microtest128octets.

Les conditions d'isolation du plan final sont ciblées sur une session fraîche
CPU garé, sans Linux. Une cartographie générale signée couvrant toutes les
applications n'est pas nécessaire pour ce seul essai, contrairement à la
portée très large proposée dans l'avis.

GLM distingue correctement TARGET22 et CLEAR28. Son plan ne peut cependant
pas être repris directement :

1. Il propose w4..w7=0 pour CLEAR, ce qui donne une taille nulle dans w5.
   Ce rectangle termine sans requête DDR. **Reproduit avec le RTL gelé**,
   puis comparé à un rectangle16×1 qui émet exactement une rafale.
2. Sa limite cible `0x400000000` comporte un zéro de trop : la limite RTL
   est `0x40000000`.
3. Il présente des écritures de la phaseD1 comme une façon de prouver
   l'isolation. La consigne demandait de s'arrêter avant les écritures si
   l'ownership n'était pas démontré. L'isolation est donc une précondition
   du plan corrigé ; les canaris servent uniquement à vérifier l'empreinte.
4. Sa fenêtre W dépasse le scratch128octets initial. Le plan intégré garde
   strictement quatre blocs32octets dans `[S,S+128)`.
5. Les délais exacts d'un compteur ne se déduisent pas de l'absence de mesure
   de fréquence. Un nombre borné de polls **et** un timeout hôte sont gardés.

## Preuves locales et limites

`local_checks_01/result.json` atteste 12 tests du décodeur ainsi qu'une
simulation Icarus de cinq modules RTL exacts du snapshot gelé. Elle vérifie
TARGET sans accès, CLEAR vide sans accès, puis CLEAR16×1 avec une unique
requête native malgré les pauses ready. Aucun RTL n'a été modifié, aucun
bitstream n'a été créé, aucune carte n'a été ouverte.

La simulation n'inclut pas le pont AHB, les arbitres ni l'IP DDR. Elle ne
prouve ni isolation de la mémoire, ni timing du bitstream, ni cohérence
CPU/GPU sur la carte. Ces limites restent des gardes du plan, pas des PASS.

# Neo R19 — lectures CPU après blocage de CLEAR

## Objectif et environnement

Départager une indisponibilité générale de la DDR d'un blocage propre au
trajet GPU. Essai du 28 octobre 2026 sur la Neo locale, programmateur
`2025041420`, branche `3-4.4.1`, sonde CPU ESP-Prog `3-4.4.2`.
Ni Pro Dock, ni SD, ni flash persistante touchée. Pas de Linux.

FPGA R19 exact :
`1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`.
BIN02 : `dbf293d4ed9c739e4641f0ff531374c5fb9ad8ec7b2b7795f0bf4e609baa934c`.
Lecteur ILM de 588 octets :
`aa2a1a061c87de6cc47a567a217b6d4078df1d3c982242bfe2275ef7bcc50503`.
Les scripts exécutés, journaux et empreintes sont conservés dans ce dossier.

## Procédure et attentes

1. Vérifier la cible, prendre le verrou Neo, contrôler CPU garé et caches nuls.
2. Exécuter BIN02 : écrire et relire 128 octets par CPU à `0x12000000`,
   envoyer TARGET puis CLEAR de 16 pixels RGB565 à `0x12000020`.
3. Après timeout de CLEAR, conserver le journal et deux captures GPU cohérentes.
4. Exécuter le lecteur séparé à `0xa0005000` : 32 lectures CPU de la zone,
   journal à `0xa0006400`, sans écriture DDR ni commande GPU dans cette étape.
5. Capturer de nouveau l'état GPU, puis restaurer exactement R19.

Un lecteur qui ne termine pas ne permet pas de qualifier le contenu mémoire.
Un lecteur terminé renseigne le contenu observé, sans valider l'exécution GPU.
Les gardes Tcl ont passé sept cas locaux ; les huit scénarios du binaire
RV32 et la contre-revue sont des preuves distinctes de cet essai matériel.

## Résultat constaté

- BIN02 reproduit le blocage : phase 8, résultat −5 ; TARGET est terminé,
  CLEAR reste en attente, compteur `done=1`, `busy=1`.
- Le lecteur termine **32 lectures sur 32**, sans trap ni cache activé.
- Les **128 octets conservent exactement le motif initial**. Les huit mots
  que CLEAR devait remplacer ne contiennent pas la couleur `0x6b4d6b4d`.
  Les 96 octets de garde sont intacts.
- `done`, `busy`, erreurs, pertes et rejets ne changent pas pendant la lecture.
  Les captures NGDB passent successivement de séquence 1 à 5 ; après CLEAR,
  le blitter conserve la commande `0x1c000000`, l'état `M_SETUP=0x20` et
  l'activité étendue. Les 16 mots de commandes ont été reçus et consommés.
- R19 a été restaurée et son contrôle de démarrage a passé. Aucun nouveau
  bitstream expérimental n'a été construit pour cette mesure.

## Interprétation et limites

La DDR reste accessible au CPU pendant le blocage GPU observé. Cet essai
contredit donc une panne générale des lectures CPU/DDR dans cet état précis.
Le trafic CPU ne débloque pas CLEAR. Le GPU reste **non fonctionnel** pour
cette commande ; `diagnostic_passed=false` est conservé dans le résultat.

L'observation ne prouve pas que le GPU n'a écrit nulle part : seules les
adresses de la zone ciblée sont relues. Elle ne mesure pas directement
VALID/READY natifs, le masque d'écriture, ni toutes les files de requêtes.
Une requête absente ou mal transmise, une écriture masquée ou mal adressée,
et un retour perdu ne sont pas tous départagés. La comparaison avec les
scénarios de simulation doit tenir compte de ces limites, sans transformer
un scénario compatible en cause matérielle démontrée.

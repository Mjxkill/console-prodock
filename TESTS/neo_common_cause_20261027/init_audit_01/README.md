# Contrôle des valeurs initiales et resets — 27 octobre 2026

Le contrôle des primitives routées ne trouve pas de conflit entre la polarité
asynchrone et INIT dans les quatre versions examinées. Cela ne mesure pas la
bonne distribution physique du reset ni la présence des horloges.

| Version | DFFCE avec INIT0 | DFFPE avec INIT1 | Valeur incompatible ou INIT absent |
|---|---:|---:|---:|
| Pro Dock G22r0 | 13 930 | 166 | 0 |
| Neo R19 | 15 537 | 165 | 0 |
| Neo R21r1 | 15 545 | 165 | 0 |
| Neo R21r2 couplé | 15 552 | 165 | 0 |

`all_async_result.json` lie ces comptes aux quatre fichiers `.vo` exacts.
Le contrôle porte sur les types DFFCE et DFFPE explicitement instanciés ; il
ne prétend pas couvrir toutes les variantes de primitives Gowin.

Le contrôle ciblé dans `result.json` couvre également tous les paramètres et
raccordements des 195 FF Pro Dock et 198 FF de chacune des trois versions Neo :

- synchroniseurs `pixel_up`, `u_gpu/prst` et `ae350_rst_sync` ;
- `cdc_word` des images et de la somme vidéo : 71 FF par instance ;
- trois séquenceurs de reset USB, y compris leurs compteurs.

Les 198 noms, types et INIT sont identiques entre R19, R21r1 et R21r2. Les
raccordements routés complets et lignes figurent dans `cells.json` ; cette
identité de type/INIT n'est pas une identité des délais physiques.

Les FF `pixel_up` et `prst` sont des DFFCE INIT0. Les deux FF
`ae350_rst_sync` sont des DFFPE INIT1. Les trois sorties de reset USB sont
également des DFFPE INIT1. Dans les deux `cdc_word`, les contrôles
asynchrones sont constants GND, les FF ont INIT0 ; `req`, `ack`, `ack_s`,
`req_s` et `hold` ont des initialisations explicites dans le RTL.
`dst_data` n'en a pas, et reçoit INIT0 au mapping. Cette valeur par défaut
ne constitue pas un conflit de polarité asynchrone. La mise à jour effective
dépend encore de la présence des deux horloges et de la poignée de main.

Le journal de synthèse N56r9, origine active des cellules considérées, contient
deux avertissements EX2478 : déclaration initialisée des sorties `valid` de
`gpu_blit_dma` et `reset` de `usb_reset_release`, en mode SystemVerilog. Ces
messages sont conservés. La primitive routée du reset USB porte pourtant
bien INIT1 ; le message seul ne prouve donc pas une initialisation physique
incorrecte. Les helpers d'observation/reset ont aussi des EX2478 archivés.
Aucun message de conflit entre INIT et reset asynchrone n'a été trouvé dans
ces journaux examinés. Le journal synthèse Pro Dock original n'est plus dans
les dossiers archivés disponibles ; son absence n'est pas interprétée comme
absence historique d'avertissement.

La note RN100-1.9.12.03E signalée par root justifie ce contrôle. Elle n'établit
pas un défaut sur ces versions : la piste d'une constante INIT contradictoire
n'est pas reproduite ici. Une capture physique manquée, une libération de reset
mal synchronisée ou un défaut d'horloge restent des questions différentes.
Aucun RTL, contrainte, bitstream ou état de carte n'a été modifié.

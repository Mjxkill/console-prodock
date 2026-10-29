# Diagnostic contradictoire Pro Dock / Neo — 27 octobre 2026

**Aucune cause commune matérielle n'est encore démontrée.** L'audit établit
plusieurs différences réelles et un défaut de qualification HDMI ; il ne permet
pas de conclure que les échecs sont tous indépendants ou tous dus au silicium.
Aucun nouveau bitstream n'a été construit ni chargé pour cette recherche.

## Avis effectivement obtenus

Claude Fable, DeepSeek V4.1 Flash et Beam ont chacun terminé deux passes.
Les dossiers `../assisted_reviews_20261026/neo_common_cause_<modèle>_r1/`
et `_r2/` contiennent prompts, réponses et statuts. Les mêmes paquets factuels
ont été envoyés à chaque passe (`review_packet_r1.txt`, `review_packet_r2.txt`).
Les avis ne sont pas des validations. Plusieurs déductions ont été réfutées
par relecture des sources et des netlists : voir
[la contre-revue](contradiction_r1/README.md) et
[le cône busy et les resets vidéo](busy_cone_01/README.md).

## Ce qui a été établi

| Sujet | Résultat vérifié | Ce que cela ne démontre pas |
|---|---|---|
| B/C et boîtiers | Les projets utilisent B/FPG676 pour G22r0 et C/PG484 pour Neo ; l'analyseur L31r8 connu fonctionnel cible lui aussi C/PG484. Sipeed documente les deux révisions dans les deux boîtiers | Une incompatibilité conditionnelle d'IP ou de ressource n'est pas exclue par un succès partiel |
| IP USB | Neo utilise encore les IP Sipeed de 2024 ; Pro Dock utilise Controller 3.3 / SoftPHY 3.5 régénérés. Les nouvelles IP Neo présentes ailleurs ne sont pas dans R19/R21r2 | Ancien IP ne signifie pas mauvais SDC : les rapports 48/60/960/120 MHz sont cohérents dans les primitives réelles |
| Reset CPU | Deux défauts logiques de qualification sont reproduits ; le candidat R21r2 les corrige en simulation/mapping, avec 50 ms normaux et 2,08 ms minimum diagnostic | Leurs occurrences physiques et leur responsabilité dans chaque échec ne sont pas mesurées. Le timing du candidat reste FAIL |
| INIT des registres | Aucun INIT contradictoire à la polarité DFFCE/DFFPE dans les quatre netlists contrôlées | Cela ne valide ni la distribution physique des resets, ni leur désassertion, ni les horloges |
| Reset vidéo | HRESETN du hard CPU est enregistré une fois sur AHB_CLK pour produire vid_hrstn ; même structure Pro Dock et Neo | Les IDs constants ne prouvent pas une forme d'onde de reset sans impulsion |
| PLL vidéo | Neo choisit les contrôles analogiques dynamiques avec codes zéro ; Pro Dock le calcul statique Gowin. L31r8 utilise le même fichier et les mêmes codes que Neo | Pas de valeur interdite ou d'instabilité analogique prouvée. Voir comparaison détaillée |
| Libération HDMI | pixel_up libère le sérialiseur après trois fronts pixel de LOCK haut, environ 40 ns ; aucune surveillance continue 2 ms de LOCK vidéo | Cette lacune documentaire n'est pas une preuve de glitch réel. pixel_up ne pilote pas le reset du compteur de trames |
| Busy GPU | Entrée combinatoire à plusieurs registres avant synchroniseur, sur les deux cartes. Chemin R21r2 −4,813 ns, données 12,918 ns | Ce retour alimente le statut AHB seulement ; aucun lien direct trouvé vers validation COPY, requêtes DDR ou resets |
| Mire actuelle du candidat | R21r2 répond au CPU, mais compteurs vidéo et checksum restent nuls ; R19 apparié compte environ 60 trames/s | Ne distingue pas pixel_clk absent, reset local actif/récurrent ou CDC de compteurs bloquée |

Les sources primaires, versions et pages sont dans
[la recherche web](web_sources_r1.md) et
[la recherche reset indépendante](web_reset_independent.md).
La preuve des valeurs initiales est dans [init_audit_01](init_audit_01/README.md) ;
la comparaison analogique dans [video_pll_audit_01](video_pll_audit_01/README.md).

## Déductions rejetées après le second tour

- CPU lisible ou registre ID exact n'exclut pas tout transitoire antérieur,
  ni un reset local encore actif. Un ID peut être combinatoire.
- pixel_up agit sur HDMI, tandis que le reset du scanout vient de vid_hrstn :
  la seconde réponse Fable les confond dans sa prédiction de compteur nul.
- « Aucun signal » à l'écran ne mesure pas directement l'absence de clock TMDS ;
  format, encodage, récepteur et intégrité peuvent également intervenir.
- UTNA vivant n'exclut ni une ancienne impulsion commune ni une incompatibilité
  de PHY. La réponse DeepSeek r2 réclamant des composants externes du filtre
  PLL n'est pas étayée : ces contrôles concernent la PLL intégrée.
- L31r8 emploie de l'USB3 dans cet historique ; son succès n'est pas une
  validation de notre SoftPHY USB2.
- Aucun cycle d'alimentation après chargement SRAM dans le prochain protocole :
  il rechargerait l'image de flash et détruirait l'identité de l'essai. Cette
  proposition de Beam r2 est rejetée.
- Une faute physique peut être déterministe. « Physique = aléatoire » et
  « rejet déterministe = logique seulement » ne sont pas des diagnostics.
- Une mesure actuelle ne permet pas de conclure exactement trois causes
  indépendantes. Les classements des modèles restent des hypothèses.

## Expériences suivantes et état réel

1. Préparer un relevé commandé UTNA frais, avec séquence/ACK, banque stable et
   compteur de ticks, sur R19 puis R21r2, et restaurer R19. Associer les compteurs
   vidéo et une vue exploitable de l'écran. Aucune écriture GPU/DDR/SD, aucun
   nouveau routage ; seules les commandes de l'observateur USB changent son état.
   **Préparation en cours, aucun résultat matériel nouveau dans ce rapport.**
2. Comparer le générateur PLL officiel à cible et fréquences identiques, sans
   synthèse ni PnR. La tentative isolée est bloquée par la licence Gowin expirée,
   également hors bac à sable : `video_pll_generator_01/generator_unsandboxed.log`.
   Aucun paramètre analogique n'est modifié faute de cette comparaison.
3. Conserver la distinction entre la robustesse du statut busy, le rejet COPY
   avant accès DDR et le blocage du lecteur. Répéter les commandes déjà échouées
   sans observation supplémentaire ne constituerait pas un nouveau test.

La Pro Dock conserve son FPGA G22r0. Le moteur GM1 et son essai logiciel MC1
sont coordonnés séparément sur ax15 ; aucun essai Neo ne touche cette carte.

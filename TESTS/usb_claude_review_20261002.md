# Avis indépendant de Claude — 2 octobre 2026

Avis de revue, hypothèses à vérifier. Voir la fiche L12 pour les résultats obtenus ensuite.

**Aucune cause racine n'est prouvée.** La piste la plus probable est dans le PHY fermé : des traversées 60/120 MHz sans synchroniseur ni contrainte de timing, avec une phase du diviseur 120 MHz qui n'est pas garantie d'un démarrage à l'autre. Je n'ai trouvé aucun bug certain dans le pont ouvert actuel. Je n'ai rien modifié ni lancé, seulement lu.

## Ce qui est établi par lecture

- **Traversée non synchronisée.** Le registre `rx_en` est cadencé à 60 MHz (`usb2_0_softphy.vo:6888`). Il commande directement l'écriture de la FIFO de réception à 120 MHz, pointeurs binaire et Gray compris (`.vo:8281-8434`).
- **Sens inverse identique.** Les sorties des désérialiseurs à 120 MHz attaquent directement les registres d'état à 60 MHz, selon `TESTS/usb_phy_other_cdc_r29_20261002.json`.
- **Chemins non contraints.** `tang/constr/gpu.sdc:11` déclare 60, 120 et 960 MHz asynchrones. Le SDC Sipeed fait de même (`usb_ref.sdc:15`). Ces chemins ne sont donc ni synchronisés ni vérifiés.
- **Phase du diviseur.** Le reset du CLKDIV vient d'un registre à 60 MHz (`.vo:1491-1502`, `.vo:1839-1845`). Son relâchement est asynchrone vis-à-vis du 960 MHz.
- **Limite du banc.** Après un ACK perdu, le banc attend 120 cycles avant le IN suivant (`TESTS/rtl/usb_controller_packet_tb.sv:472`). Un IN proche d'un ACK manqué n'est jamais testé. La netlist simulée sans délais ne peut pas voir une violation 60/120.
- **Limite de la trace.** La fenêtre contient deux ou quatre enregistrements (`tang/rtl/usb/usb_packet_trace.v:103-106`). « Quatre reprises » est donc un minimum.

Ces constats sont structurels. Leur effet sur la carte reste une hypothèse.

## Trois pistes classées

**1. Traversées 60/120 du PHY et phase au démarrage (hypothèse la plus probable).**
- Pour : le même bitstream r13 réussit deux chargements puis échoue au troisième. E0b et L11, archivés comme validés, échouent aujourd'hui. Tous les placements échouent. Les défauts arrivent par rafales, avec ACK manqué puis erreurs côté hôte.
- Contre : aucune mesure de phase, et l'exemple Sipeed est censé fonctionner. La fiche ne rapporte aucun balayage de la phase locale 60/960.

**2. Réactivation tardive de la réception après émission (démontrée en simulation seulement).**
- Pour : avec les modèles originaux, un ACK arrivant 36 à 138 ns après l'émission est perdu, et il est vu à 333 ns.
- Contre : le défaut existe aussi derrière deux hubs, qui retardent l'ACK. Sur carte, la plupart des ACK sont vus. Artefact de primitives possible.

**3. Désynchronisation du toggle côté hôte (amplificateur, pas cause racine).**
D'après ma connaissance de Linux, xHCI remet le toggle hôte à DATA0 après trois erreurs de transaction. `cdc_acm` ne resynchronise pas le périphérique sur EPROTO. C'est à confirmer sur le noyau d'ax15.

Cela lève la contradiction apparente. Un paquet DATA0 déjà accepté est accepté une seconde fois, d'où le doublon. Un paquet DATA1 jamais accepté est acquitté puis jeté, d'où la perte avec ACK et FIN. La prédiction est donc : doublons en DATA0, pertes en DATA1.

| Cas archivé | Anomalie | PID en attente | Conforme |
|---|---|---|---|
| isolation r2, `5a5a` et `3535` | doublon | DATA0 | oui |
| isolation r3, r29, témoin r29, r19 direct, r19 nouveau câble | perte | DATA1 | oui |
| r15, `5c` | perte | DATA0 | non |

- Pour : sept cas sur huit sont conformes, et EPROTO est observé directement dans trois essais usbfs.
- Contre : l'exception r15, et l'origine des erreurs hôte reste à expliquer par les pistes 1 ou 2.

Seule autre explication d'un doublon à PID identique : le PID sur le câble diffère de celui vu à UTMI. Rien ne l'appuie.

**Pont ouvert.** Je n'ai trouvé aucun défaut certain dans CORK, longueur, POP et FIN. Un contrat reste fragile dans `sync_tx_pkt_fifo.v:78-87` et `:141-143`. Si FIN arrive au même cycle que la chute de `txact`, ou après, les pointeurs se croisent ou n'avancent pas. La signature attendue serait une donnée ancienne avec PID alterné, ce que les traces ne montrent pas.

## Tests décisifs et correctif

1. **Le plus petit, sans build.** Sur ax15, capturer usbmon et les messages de debug xHCI pendant le test CDC. Si chaque anomalie est précédée d'un statut −71 ou d'un reset de l'endpoint 0x82, la piste 3 est confirmée. Sinon elle est réfutée.
2. **Statistique de démarrage.** Recharger vingt fois le même bitstream avec un test court. Une répartition bimodale, chargements parfaits ou défaillants d'emblée, appuie la piste 1.
3. **Analyse de timing seule, sur copie de diagnostic.** Déclarer l'horloge 120 MHz comme générée du 960 MHz et retirer le groupe asynchrone 60/120. Rapporter setup et hold pour les huit phases possibles du diviseur.
4. **Preuve sur carte.** Construire quelques variantes ne différant que par la phase statique de la sortie 60 MHz de `Gowin_PLL_B`. Un taux d'erreur qui dépend de la phase prouve la piste 1.
5. **Piste 2.** Balayer `ACK_DELAY` entre 8 et 20 dans le banc pour trouver le seuil. Ajouter à la trace passive le délai, en cycles 60 MHz, entre fin d'émission et réception de l'ACK.

**Correctif réalisable sans toucher aux netlists.** Contraindre réellement les chemins 60/120 dans le SDC de production. Fixer par CST le placement du registre de reset du diviseur pour rendre la phase reproductible. Choisir la phase de la sortie 60 MHz au centre de la fenêtre mesurée au test 4. Côté hôte, un outil qui resynchronise l'endpoint après EPROTO, ou un tramage applicatif numéroté, masque le symptôme sans guérir la liaison.

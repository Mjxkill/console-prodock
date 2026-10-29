# Neo : microDMA discriminant, étape conditionnelle

**Aucun payload ni contrôleur d'écritures DDR n'est préparé.** Le plan reste
bloqué sur les gardes d'isolation et de visibilité décrites ci-dessous.
Même FS R22r1 et restauration systématique R19 que dans `USB_READ_PLAN.md`.
La simulation locale contrôle uniquement l'interface du module `gpu_v1`.

## Ce qu'il faut réellement tester

L'opcode 31 utilisé dans la collecte combinée configure une matrice. Il a
terminé, avec les compteurs actualisés à host=8/received=8/done=1, mais ne
fait pas de DMA DDR. La mire interne n'en fait pas non plus. Un résultat
correct à ces deux tests ne démontre donc aucun trajet GPU↔DDR.

Le prochain test utile est : un motif écrit **par le CPU**, une comparaison
CPU avant DMA, une configuration TARGET sans DMA comme contrôle négatif,
puis un CLEAR couleur sur **16×1 pixels RGB565**, soit une seule rafale
native de 32 octets. La comparaison après DMA doit utiliser un chemin de
lecture dont la relation aux caches est établie. Un accès OpenOCD n'est pas
appelé « écriture CPU » si son mécanisme n'a pas été identifié.

## Carte d'adresses établie à partir du snapshot gelé

| Élément | Fait établi / limite |
|---|---|
| Fenêtre CPU AHB | `ahb_ddr_cdc.v:57-73` refuse les bits31:30 non nuls et les tailles/alignements illégaux ; fenêtre byte apparente `[0,0x40000000)` |
| Anneau hérité | `ae350_soc.v:170-171,191` remplace les paramètres par base `0x20000000`, taille `0x20000000` ; le défaut du module ddr_subsys à `0x10000000` n'est pas la configuration réelle |
| Client acquisition | `console_neo.v:179-182` fixe ev_valid, acq_start, acq_run à zéro ; PATTERN=0 ; aucune nouvelle commande d'acquisition dans ce protocole |
| CPU | Garé à ROM `0x80000000/04` lors des gardes précédentes ; Linux n'a pas été démarré dans cette session diagnostique |
| Scanout | Framebuffer désactivé et compteurs requêtes/retours nuls lors du relevé précédent ; cette garde doit être reproduite, pas simplement réutilisée comme résultat courant |
| GPU | État idle et queues vides à établir après chargement frais ; seul TARGET puis CLEAR seront admis dans cette fenêtre d'essai |
| Scratch candidat | `[0x12000000,0x12000080)`, 128 octets, dans la moitié basse CPU et hors anneau réel. Usage historique n'est pas une réservation actuelle |

La plage candidate est découpable en quatre blocs de 32 octets : canari,
couleur, profondeur non écrite, canari. Dans cette disposition, la base
couleur symbolique est `C=S+32` et la base Z `Z=S+64`. Les deux strides
valent 32, width=16, height=1. Aucune plage hors de ces 128 octets n'est
incluse dans ce projet de test.

## Unités exactes des deux trajets

Soit une adresse byte A dans la fenêtre CPU :

- le pont AHB capture A[29:3] ; une transaction est située dans un beat UI
  aligné de 16 octets, d'adresse en mots16 `(A >> 4) << 3` ;
- `ddr_ui_adapt` transforme ce beat en adresse native en mots32
  `(A >> 5) << 3` et sélectionne une moitié de rafale 32 octets ;
- les masques ont 1 pour un octet non écrit. Une écriture CPU de 4 octets
  ne doit activer que quatre octets, bien que la commande physique fasse
  une rafale de 32 octets. Ce masque doit être vérifié par les canaris.

Le GPU V1 reçoit ses bases en **octets**. Pour un pixel P, il forme P>>2 puis
aligne les 3 bits bas à zéro. À C aligné32, le CLEAR produit donc `C>>2`
comme adresse native, masque=0, 16 copies du mot RGB565. Le plafond validé
par le TARGET est **0x40000000 (1 GiB)**, pas 16 GiB.

## Gardes encore manquantes avant d'émettre des écritures

1. **Réservation dynamique explicite** des 128 octets pendant une session
   fraîche : aucun Linux/payload DDR actif, CPU stoppé, aucune activité
   scanout, commandes GPU exclusivement celles du test, gardes d'identité
   liées à ce FS. Les états antérieurs ne suffisent pas. Le ring ne chevauche
   pas la plage, ce point est déjà clos par les paramètres réels.
2. **Emplacement ILM exact du microprogramme et de son journal**, limites et
   non-chevauchement avec le code de parking/les zones du debugger. Le vieux
   `memory_probe.S` touche 4096 octets DDR et des blocs ILM B000/C000/D000/E000 ;
   il ne doit pas être exécuté tel quel pour ce test128octets.
3. **État du cache de données et chemin d'accès OpenOCD**. M-mode/satp=0 ne
   prouve pas cache désactivé. La configuration OpenOCD fournie ne fixe pas
   explicitement SBA/progbuf/abstract. Établir une méthode de lecture CPU
   non cachée et la consigner, ou traiter la comparaison comme ambiguë.
   Le code Pro Dock `fw_console/gpu_diag.c:152-158` fournit un précédent
   MCACHE_CTL/flush, pas une preuve de l'état présent de la Neo.
4. **Ordre des transactions** : acquittement du pont et `fence` ne sont pas
   seuls une preuve d'écriture physiquement visible par le GPU. Un readback
   CPU non caché du motif entier, avant lancement GPU, doit passer ; une
   lecture après GPU doit suivre la même politique et un GPU idle confirmé.
5. **Contrôleur d'essai et restauration** : conserver le verrou Neo, les
   limites de temps/volumes, le contrôle des erreurs/traps et la restauration
   unique R19 déjà testée. Un échec interdit de poursuivre à l'étape suivante.

Ces gardes sont des points à établir, pas une demande de prouver un allocateur
général pour tous les jeux. La première expérience est volontairement faite
CPU garé et sans Linux ; aucune allocation persistante n'est envisagée.

## Séquence après fermeture de ces gardes

1. Charger frais le même FS, garder la mire interne. Enregistrer contrôles
   avant et après chaque phase, avec snapshots GPU actualisés.
2. CPU : écrire un motif distinct par mot sur les 128 octets, puis relire
   intégralement sans cache. Seuil zéro erreur ; aucune opération GPU si
   le CPU ne relit pas son propre motif.
3. TARGET22 : bases C/Z, dimensions16×1, strides32/32, champs réservés nuls.
   Attendre done et idle bornés. Aucun changement mémoire attendu. Inutile
   d'ajouter un SCISSOR23 : un TARGET valide réinitialise déjà le scissor.
4. CLEAR28 : couleur seule, rectangle (0,0,16,1), profondeur inactive.
   Attendre done puis idle, lire les erreurs et actualiser le snapshot GPU.
5. CPU : comparer 16 pixels à la couleur choisie et les 96 octets restants au
   motif initial. Journal ILM borné : première adresse différente + valeur
   attendue/lue + nombre d'erreurs + compteurs de chaque phase.
6. Lire le journal hors DDR, conserver les données même en échec, restaurer
   R19 et attester identité/CPU/mire selon le contrôleur existant.

La taille CLEAR vient de w5. **w5=0 est un rectangle vide**, même avec TARGET
valide et scissor plein. Il termine normalement, sans erreur et sans DMA.
La simulation exacte a reproduit ce cas proposé dans un avis externe :
`local_checks_01/2.log`. Le CLEAR16×1 corrigé y émet une seule requête native,
avec adresse/data/mask attendus, malgré plusieurs cycles de ready=0.

## Interprétation bornée

| Observation | Ce qu'elle départage |
|---|---|
| CPU échoue avant GPU | Le défaut n'exige pas ce DMA GPU ; conserver adresses/motifs exacts |
| TARGET change la mémoire | Contradiction du contrôle négatif ou contexte/lecture non maîtrisé ; arrêter |
| CLEAR reçu, done n'avance pas | Blocage après réception : examiner état moteur/arbitre, sans appeler automatiquement cela DDR défectueuse |
| done avance, mémoire inchangée | Vérifier rectangle/configuration et méthode de lecture ; done seul ne prouve pas écriture externe |
| 32 octets changés correctement, canaris intacts | Un petit accès CPU↔GPU↔DDR fonctionne dans ce contexte ; pas de preuve de scanout720p, débit, rendu complexe ou stabilité longue |
| Canaris changés | Conserver le motif exact et ne pas poursuivre ; peut discriminer masque/adresse/alias sous réserve du chemin de lecture |

On n'emploie pas une écriture DDR pour « prouver l'isolation » après coup.
Une réussite des canaris valide seulement l'empreinte observée du test ;
l'autorisation et l'exclusivité de la plage doivent être établies avant.

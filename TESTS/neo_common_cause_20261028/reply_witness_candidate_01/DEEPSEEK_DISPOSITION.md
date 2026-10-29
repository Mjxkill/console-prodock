# Confrontation de la revue DeepSeek au code et aux preuves

Avis reçu dans
`TESTS/assisted_reviews_20261026/neo_reply_witness_deepseek_r1_network/answer.txt`.
L'avis ne revendique ni exécution ni accès carte. Le premier essai réseau
avait échoué au DNS sans produire d'avis ; il est conservé séparément.

**Aucun correctif RTL n'est issu de cette revue.** Le helper, le constructeur,
le mapping et le candidat restent gelés aux empreintes déjà testées.
Les changements concernent uniquement la précision du contrat et un
collecteur/décodeur de fichiers hors carte, demandé ensuite par root.

## Points retenus

1. **N=0.** La formule tags=N−1 et F0=`0x003f0007` ne s'applique qu'à N≥1.
   Le contrat le précise maintenant et décrit l'image de reset nulle.
   Le décodeur refuse N=0 comme capture complète à interpréter.
2. **EC obligatoire.** Un mot0 hors busy suivi de 31 mots avec busy peut
   laisser F0 normal et EC=1. Ce n'est pas un défaut du témoin : il comptait
   déjà l'événement et le contrat exigeait EC=0. Le point est désormais mis
   en évidence, puis vérifié sans exception par `offline_capture.py`.
   Le test nommé `mixed busy frame: normal F0 and complete counters but EC1`
   confirme le refus. Aucun bit F0 supplémentaire ni nouveau candidat.
3. **Deux images encadrées.** Les tests d'intégration vérifiaient les valeurs
   stables, sans constituer un collecteur de deux images. Le nouveau format
   exige contrôles avant/après et deux images complètes identiques, soit
   102 lectures ordonnées ; séquences, états, tags, sentinelles et alias sont
   tous vérifiés. Il ne contient aucune acquisition matérielle.
4. **Limite de l'alias raw1.** CC et D4 relisent les mêmes bascules. Une faute
   interne de raw1 peut imiter un zéro à la frontière. Le contrat le disait
   dans sa table conditionnelle ; il le précise maintenant avant la table.
   Le décodeur conserve toujours l'alternative « witness failure » dans le
   résultat zéro/zéro. Il n'attribue jamais ce seul résultat à la FIFO.

## Objections confrontées aux sources exactes

Le paquet de revue borné ne contenait pas l'intégralité des netlists. Certaines
réserves décrivent une preuve absente du paquet, pas un défaut du candidat.

- **Acceptation hors busy et tags.** Le R19 figé,
  `source/tang/rtl/usb/usb_idle_trace.v`, SHA
  `97854f943d523304877e4fafc52c53e71ef03cb3e54940f13cd1a7a0bdbe8d9f`,
  écrit la banque sous `if(reply_valid)` dans la branche `else` de `hreset`.
  Aucun test busy n'est présent. Le même bloc incrémente `snapshot_count`
  seulement pour `receive_index==31`. Au front de réception du mot31, busy
  vaut encore 1 avant les affectations non bloquantes qui le remettent à 0.
  Les tags N−1 aux index0/1/2 et last_busy=1 sont donc cohérents avec cette
  logique, puis effectivement vérifiés sur le cut mappé. Cela ne prouve
  pas les états physiques sur carte, distinction conservée.
- **Horloge arrêtée.** L'avis intitulait ce point « reset avec HCLK arrêté »,
  alors que le banc arrête `u_run`, continue à attendre les fronts HCLK et
  le message du banc dit littéralement « USB clock stopped ». Le README
  et le contrat décrivaient déjà l'horloge USB arrêtée. Aucun test HCLK
  arrêté ni reset asynchrone du témoin n'est revendiqué. Le contrat précise
  maintenant explicitement que HCLK doit avancer.
- **Alias d'écriture C0 vers 0C.** Dans ce R19 exact, `push_command` et la
  prise en compte d'une écriture exigent `address==8'h0c`. Le helper ne
  reçoit ni `hwrite` ni `hwdata`, ne modifie aucun CE/RESET de l'application
  et ne revient que sur D des 32 registres de lecture. Le contre-exemple
  proposé par l'avis suppose donc une autre implémentation du décodeur.
  Lire 0C ne serait d'ailleurs pas un témoin de cette mutation : 0C est une
  commande en écriture, et sa lecture retourne zéro dans le RTL original.
- **Conflit d'adresse global ajouté.** Le top figé sélectionne le retour
  UTNA par `selected=bus_haddr[14:12]`, valeur 2. `soft_usb.vh` qualifie
  pareillement son hsel par `[14:12]==2`. L'extension C0..FF ne change pas
  ces bits et n'ajoute aucun esclave. Le top et les 148 autres modules sont
  vérifiés identiques dans l'audit. Pas de nouveau conflit logique identifié.
  Le décodage existant ignore [11:8] et crée des miroirs de 256 octets ; le
  collecteur refuse ces miroirs et accepte seulement les adresses canoniques.

## Limites conservées

- Le helper n'a pas de preuve d'équivalence formelle pour tous les états ;
  les simulations sont finies et sans SDF. Les CLK/RESET de ses 402 FF sont
  audités, et les stimuli sont comparés au modèle indépendant.
- Les binaires Icarus/vvp n'étaient pas épinglés dans les anciens résultats.
  Le relevé complémentaire `tool_identity.json` les identifie après coup ;
  ce relevé ne prétend pas les avoir verrouillés pendant les essais passés.
- Le cut mappé n'est pas une simulation complète de toutes les IP du FPGA.
  L'identité des modules inchangés est une preuve structurelle distincte.
- L'acceptation future du `.vg` par Gowin, la conservation des FF au P&R,
  le timing et le comportement matériel restent non qualifiés. Les nouveaux
  taps/mux peuvent changer le placement et faire disparaître le défaut :
  cette disparition ne désignerait pas sa cause.

## Décodeur supplémentaire

`offline_capture.py` collecte des **journaux déjà enregistrés** au format
JSONL ou lit un paquet JSON. Aucun OpenOCD, JTAG, USB, SSH, accès carte ou
commande d'écriture n'est présent. Les offsets sont stricts, ordonnés et
alignés, les opérations non prévues sont refusées, les clés JSON dupliquées
et les fichiers tronqués/surdimensionnés aussi. Les entrées sont bornées
à 256 Kio. L'empreinte concerne les octets réellement lus ; elle reste nulle
quand le fichier a été refusé sans lecture complète.

`offline_tests_03/result.json` : **85 cas PASS**. Toutes les données d'essai
sont synthétiques, certaines banques étant reprises des simulations locales.
Les tests avec identité « hardware_capture » sont également des fixtures ;
ils ne prétendent pas qu'un candidat est chargé. Même avec un SHA déclaré
conforme, `hardware_qualified` reste toujours faux. La version0 produit
`passed=false`, `qualification=FAIL`, et un code de sortie 1 en CLI, tout en
préservant la capture et l'interprétation conditionnelle lorsque cohérentes.

Pas de seconde revue intégrale sollicitée : les réserves sont confrontées
aux sources et aux contre-exemples ci-dessus. La relecture root et toute
future qualification matérielle restent distinctes.

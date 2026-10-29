# Neo : prochain relevé UMSC, préparé hors carte

État : **plan et décodeur prêts ; aucun contrôleur matériel nouveau, aucune
exécution**. Root conserve la programmation et le verrou Neo. Le même R22r1
est employé ; aucun nouveau routage. L'essai devra restaurer R19 dans le
`finally` déjà testé, y compris après interruption et échec de lecture.

## Ce que ce relevé peut départager

La collecte combinée du 28 octobre à 13:38 a montré une vidéo qui avance,
un échange de matrice GPU terminé et des captures UTW1 cohérentes. Le PC ne
voyait pas le périphérique USB. Elle ne lisait pas UMSC. Ce relevé distingue :

1. l'accès AHB au bloc UMSC, avec ses constantes ID/version ;
2. les états USB échantillonnés et les traces de reset ;
3. une propriété firmware inattendue alors que le CPU est garé.

Un ID correct et des bits `online/highspeed` ne prouvent ni énumération, ni
fréquence d'horloge, ni fonctionnement des transferts. L'absence USB dans
sysfs reste une observation hôte distincte. Aucun trafic USB ne sera émis.

## Identité et garde de contexte

- R22r1 FS SHA-256 : `55601256120915adbb08279c0b6bd42caabf8deff261bf87b8a7b8d8cbf9c8aa`.
- Netlist normalisée : `0eb5638a63c4c2562f78db1dc71474830b7425b23c30b56674639bac4a4cb191`.
- R19 restaurée : `1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`.
- Réutiliser les gardes d'identité, CPU garé M-mode/satp=0, ROM WFI/J,
  framebuffer désactivé, NCP/GPU inactifs, exclusivité et dépendances SHA du
  contrôleur combiné. Ne pas interpréter une garde échouée comme un fait USB.
- Ne pas réutiliser sa comparaison incorrecte du compteur reçu figé : une
  nouvelle capture GPU doit précéder la comparaison après une commande.
- Limite STA inchangée : setup global −1,013 ns, recovery −0,212 ns. Un
  contrat de collecte PASS n'est pas une qualification de ce bitstream.

## Lectures autorisées et effet de bord connu

Deux passages, chacun **trois lectures individuelles de 32 bits** dans cet
ordre, sans tentative supplémentaire. Un délai hôte borné de 100 ms peut
séparer les passages ; ce délai n'est pas une mesure de fréquence FPGA.

| Ordre du passage | Adresse | Attente / observation |
|---|---:|---|
| 1 | `0xe9003000` | ID exact `0x554d5343` |
| 2 | `0xe9003004` | Status brut conservé et décodé |
| 3 | `0xe9003028` | Version exacte `1` |

**Pas de lecture bloc traversant les trous.** Les lectures `+08` et `+20`
consomment les octets réunis ; elles sont exclues. Aucune écriture dans la
fenêtre, aucune commande EP0/BULK, aucune lecture DDR.

Les lectures choisies ne consomment pas le flux. Elles ne sont cependant
pas sans effet : `usb_msc_port.v:221` recharge le watchdog pour **toute**
lecture acceptée. Même ID/version peuvent donc retarder un abandon du
disque. Six lectures bornées évitent un polling qui masquerait durablement
ce phénomène. Garder cet effet dans le rapport.

## Contrat exact du status

Autorité : affectation RTL gelée `usb_msc_port.v:267-268`, non le commentaire
historique en tête de fichier. Les deux premiers bits de propriété ne sont
pas interchangeables.

| Bits | Interprétation |
|---|---|
| 31:16 | `level_h`, octets TX poussés moins ceux rendus au consommateur |
| 15:11 | zéro réservé |
| 10 | `halted_h[1]`, état de blocage échantillonné |
| 9 | `serve`, demande du firmware |
| 8 | `owner_h`, propriété accordée côté USB, synchronisée vers HCLK |
| 7 | `lost` |
| 6 | `hs_s[1]`, entrée highspeed synchronisée |
| 5 | `online_s[1]`, entrée online synchronisée |
| 4 | `quiet_h` |
| 3 / 2 | reset BOT / reset du bus vus, indicateurs persistants |
| 1 | `level_h == 0` |
| 0 | `gathered != 0 && !hreset` |

ID/version incorrects, bits réservés non nuls, relation interne niveauTX/bit1
incohérente, ou propriété/demande firmware inattendue arrêtent la collecte
dépendante. Toutes les observations déjà obtenues restent enregistrées.
Un status `owner=1/serve=0` peut être transitoire en fonctionnement normal ;
le refus porte ici sur le **contexte CPU garé**, pas sur une violation USB.

Les drapeaux online et highspeed sont synchronisés séparément. Le couple
`highspeed=1/online=0` et un changement entre deux lectures sont conservés
comme observations. Ils ne suffisent pas à déclarer la capture corrompue
ou le PHY en défaut. Ne pas moyenner, ne pas ne garder que la dernière valeur.

## Décodeur préparé

`umsc_decode.py` ne contient aucun transport. Il accepte une liste JSON de
six enregistrements `{seq, address, value}`, ou un préfixe incomplet conservé
après arrêt. Les adresses sont absolues et exactes ; les tags doivent être
0..5. Un préfixe est toujours non PASS. Aucun alias d'adresse, doublon,
uint32 hors plage ou coercition booléenne n'est accepté.

`test_umsc_decode.py` couvre 12 groupes, dont lecture partielle, mauvais
ID/version, offsets interdits, ordre/tags, séparation des bits 8/9 et
transitions CDC. Résultat dans `local_checks_01/result.json`.

## Décision après ce relevé

- ID/version faux : l'observation AHB doit être éclaircie avant de parler PHY.
- ID/version corrects, resets vus et état online/HS changeant : corréler aux
  événements hôte existants ; aucune fréquence déduite.
- ID/version corrects, status constant : cela n'établit pas que toutes les
  horloges et tous les resets PHY sont corrects. UTNA/UMSC ne voient pas
  directement toutes les branches PHY_RESET.
- Une nouvelle compilation n'est justifiée par aucun de ces cas à elle seule.

Le collecteur matériel reste à dériver/revoir par root ; ce dossier ne
lance ni programmation, ni OpenOCD, ni commande hôte.

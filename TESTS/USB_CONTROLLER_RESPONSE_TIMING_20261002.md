# Délai de réponse USB mesuré dans une transaction intégrée

**Le modèle PHY 3.4 Normal dépasse 400 ns pour les 277 réponses observées.
Advance reste sous 400 ns pour ses 273 réponses.** Cette fois, EOP hôte et
première K du FPGA sont horodatés dans la même transaction du banc contrôleur
complet : les résultats ne combinent plus deux simulations indépendantes.

Le budget nominal comparé est 192 temps de bit à 480 Mbit/s, soit 400 ns,
correspondant au maximum de retournement indiqué par EL_22 dans la
[spécification de conformité électrique USB 2.0](https://www.usb.org/sites/default/files/USB%202%200%20Electrical%20Compliance%20Specification(v1.07).pdf).
Ce maximum concerne la réponse à un paquet reçu ; il ne faut pas le confondre
avec le minimum entre deux transmissions successives d'un même émetteur.

## Résultats directs

| Transaction EP2 | Normal, délai min–max (ns) | Advance, délai min–max (ns) |
| --- | ---: | ---: |
| IN → NAK | 438,745–442,912 | 372,079–376,245 |
| IN → DATA0 | 426,245–442,912 | 376,244–376,245 |
| IN → DATA1 | 442,911–442,912 | 376,244–376,245 |
| OUT DATA0 → ACK | 438,744–442,912 | 372,078–376,245 |
| OUT DATA1 → ACK | 438,744–442,912 | 372,078–376,245 |

Normal compte 277 dépassements sur 277, avec un maximum 42,912 ns au-delà du
budget nominal. Advance compte zéro dépassement sur 273, avec au moins
23,755 ns de marge dans cette simulation. Les premiers cas de chaque classe
gagnent 66,667 ns. Le nombre de réponses diffère parce que les mêmes boucles
hôte adaptent leurs sondages et reprises aux réponses effectivement reçues.

Les contrôles de données passent dans les deux runs : 131 octets IN et
524 octets OUT exacts, aucun ZLP inattendu. La qualification du lien complet
reste **FAIL** : 283 différences de tramage Normal, 280 Advance. Le banc
attend la réponse au-delà de 400 ns ; ses contrôles de données ne constituent
donc pas à eux seuls un contrôle de délai USB.

## Instrumentation et reproduction

`TESTS/rtl/usb_controller_phy_link.svh` enregistre désormais :

- `HOST_EOP` : fin de l'EOP transmis, au retour SE0, identifiant du paquet,
  PID, type de token et endpoint ;
- `DEVICE_SOP` : première K effectivement observée sur les broches, associée
  au précédent EOP hôte ;
- `RESPONSE_TIMING` : association finale avec le PID décodé de la réponse,
  largeur de la première K et différence de fin EOP.

Aucun délai, paquet ou stimulus existant n'est modifié. Les options sont les
mêmes pour les deux runs : PHY série, ACK20, DEBUG et `interleave-out`.
L'énumération utilise toujours le bootstrap UTMI existant ; les transactions
mesurées passent ensuite par les broches du PHY.

Les sondes internes Normal sont disponibles ; celles d'Advance sont absentes
et désactivées automatiquement. `--phy-internal-observers auto/on/off` permet
de contrôler ce comportement et le rapport en consigne la disponibilité.
Les horodatages électriques ne dépendent pas de ces sondes internes.

Rapports complets :

- `TESTS/usb_controller_response_normal_r1_20261002.json` ;
- `TESTS/usb_controller_response_advance_r1_20261002.json` ;
- `TESTS/usb_controller_response_timing_comparison_20261002.json`.

Les fichiers `.log` voisins conservent les traces. Le rapport de comparaison
vérifie les 277 et 273 appariements : numéro de paquet, endpoint, PID hôte,
horodatage EOP, première K et soustraction des timestamps. Les commandes de
compilation, SHA des sources et contrôles de stabilité sont dans les rapports.
Chaque run prend environ 103 secondes ; ils ont tourné en parallèle et sont
tous deux terminés. Les sources sont restées inchangées pendant les tests.

Normal utilise le snapshot `gpu_usb_phy34_r2/source` et son modèle officiel.
Advance utilise `gpu_usb_advance_r1/source` et le VO exporté depuis une copie
intacte de son VG matériel, dont le SHA vaut
`363d18af0556baeaff5dd5b0d0ed1da5a7a1298fb7803dd9c865db0fb49728a9`.
Le compagnon `.v` a été copié intact ; le runner impose l'identité avec le
PHY du snapshot matériel avant compilation.

## Portée de la conclusion

Cette preuve établit un délai excessif dans le **modèle Normal**, corrigé par
Advance pour les transactions observées. Elle ne mesure pas le délai sur la
carte et n'établit pas, seule, la cause des erreurs xHCI.

La simulation n'inclut ni SDF, réseau analogique RC, câble, PLL physique ou
métastabilité. Le VO est à résolution 100 ps ; les décimales supplémentaires
sont des horodatages du simulateur. La première K est un événement de broche,
mais les différences de largeur SYNC et de fin EOP empêchent de prétendre que
ce signal représente une émission électriquement qualifiée.

Les clocks sont nominales, phase hôte 0,317 ns et phase locale 960 MHz nulle.
Le mini-banc précédent échouait sur l'ACK isolé à phase locale 0,520833333 ns
dans les deux modes : cette sensibilité limite l'extrapolation aux autres
phases et au matériel.

Enfin, cette correction de délai est distincte de la fenêtre de reprise RX :
le mini-banc précédent perdait toujours les ACK à 40/100 ns après TX dans
les deux modes, tout en recevant ceux à 200/340 ns. Advance ne constitue donc
pas une correction complète démontrée de l'instabilité USB.

Aucun build ni accès matériel n'a été effectué pour ce lot.

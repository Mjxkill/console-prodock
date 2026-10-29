# R11 refusé : contraintes d'horloge propres à Arora V

**R11 reste ROUTING_FAILED, code1.** Gowin émet CT1154 : le type de
contrainte `BUFS` n'est pas pris en charge sur GW5AST-138C. L'arrêt intervient
avant placement, après génération GAO. Cela ne démontre ni que `control0[0]`
est introuvable, ni qu'il aurait été correctement résolu ensuite. Aucun
nouveau routage ni accès matériel n'a été effectué pour cette recherche.
Les [preuves et empreintes](evidence.json) identifient le constructeur,
les entrées R11, le log d'échec et les documents réellement installés.

Le manuel générique **SUG935-1.6.1E**, annexe A.8, documente `BUFS` comme
sélection de SCLK, défini dans ce manuel comme *Segmented Clock*.
Ce texte ne prouve pas que BUFS sélectionne un LW sur Arora V.

Le manuel dédié **SUG1018-1.7E, Arora V Design Physical Constraints**,
§2.7 pages14–16, donne uniquement les choix suivants :

| Forme | Effet documenté |
|---|---|
| `CLOCK_LOC "net" BUFG = CLK;` | Acheminement global, allocation automatique |
| `CLOCK_LOC "net" BUFG[0–15] = CLK;` | Sélection d'un réseau global donné |
| `CLOCK_LOC "net" LOCAL_CLOCK;` | Acheminement local, hors réseau global |

Le manuel **UG306-1.0.7E, Arora V Clock User Guide**, page3, décrit GCLK
comme comprenant PCLK et LW ; page6, il indique seize réseaux globaux.
Ni ce passage ni SUG1018 ne fournissent une table établissant que les
indices8–15 désignent LW. Aucun rapport Neo terminé trouvé localement
avec ces indices ne permet de compléter cette preuve. Ne pas inventer
`BUFL`, `LONGWIRE` ou une correspondance numérique à partir du compteur
7/8LW du rapport.

Une prochaine expérience strictement limitée pourrait donc demander
`CLOCK_LOC "control0[0]" BUFG = CLK;`, type déjà utilisé par les horloges
applicatives GW5AST. La résolution du net GAO reste à vérifier par l'outil.
L'allocation éventuelle au LW disponible reste également une hypothèse :
les huit PRIMARY applicatifs doivent rester inchangés et le rapport doit
identifier le réseau effectivement attribué aux250charges après
`GW_JTAG.tck_o`. Un refus de capacité ou de résolution doit rester un échec.
L'acceptation du CST ne prouve ni l'emploi d'un LW ni une correction de hold.

Les variantes restent séparées de cet essai :

- **GAO Standard REG,16échantillons** :336bits avec21bits capturés, donc sous
  la limite512bits du manuel. La profondeur de capture et la position du
  trigger doivent être cohérentes ;128 est invalide dans une fenêtre16.
  Fenêtre320ns à50MHz, utile surtout pour des états stables capturés tardivement.
  Le stockage supprime les dix chemins actuellement dirigés vers BSRAM,
  mais ne démontre pas la correction des trois chemins logiques existants.
  Avant tout routage, vérifier les paramètres générés et l'absence de BSRAM
  de capture ; ne pas deviner la valeur XML du mode REG sans la génération
  ou le sélecteur fournisseur.
- **Force Trigger by Falling Edge** : option fournisseur pertinente pour
  certains registres TCK, pas une garantie. Le pire chemin est déjà F/F et
  ses registres appartiennent au contrôleur `u_icon_top` ; le manuel ne
  précise pas lesquels changent. Il faut vérifier les fronts et toutes les
  marges du candidat obtenu.
- **Offset d'horloge** : changer seulement une phase ou une latence SDC ne
  corrige pas le matériel et ne doit pas masquer les treize violations.
  Un offset commun aux mêmes fronts se retranche de leur relation. Une
  modification physique de phase serait un autre design à prouver, sans
  mécanisme fournisseur ciblé établi ici.

R10 et R11 sont conservés tels quels. Les treize violations hold R10, les
violations applicatives et les audits de reset ne sont ni supprimés ni
requalifiés par cette analyse documentaire.

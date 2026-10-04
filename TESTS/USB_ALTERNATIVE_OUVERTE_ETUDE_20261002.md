# Alternative USB CDC ouverte — étude, 2 octobre 2026

**Lecture seule des sources ; aucun build ni chargement de cette alternative.**

Après les échecs des témoins fournisseur, une autre voie consiste à tester
un contrôleur et PHY Full Speed entièrement inspectables. Le projet
[ulixxe/usb_cdc](https://github.com/ulixxe/usb_cdc) est téléchargé dans
`/tmp/console_usb_cdc_review_20261002`, commit
`6798bf42d43be81368d4e5e2c26b262b41e9fb6a`, sous licence MIT. Le texte de
licence devra accompagner toute copie intégrée au dépôt.

Les sources exposent les données IN/OUT avec `valid/ready`, les signaux
D+/D− séparés et l'activation de la résistance de rappel. `BIT_SAMPLES=5`
correspond à 60 MHz ; `USE_APP_CLK` permet un domaine applicatif distinct.
Des bancs amont couvrent énumération, contrôles CDC et boucle de données.
Ce sont des possibilités annoncées et lues dans le code, pas une validation
sur la Pro Dock. Le descripteur courant n'annonce pas de numéro de série.

Un témoin éventuel reprendrait seulement les PLL et les broches FS du témoin
Sipeed : T19/U19 pour D+/D−, M19 pour le rappel. Il faudrait vérifier le
reset, l'absence de sorties HS, le timing, l'identité USB et les reprises
de paquets, puis les écarts d'horloge et les resets des domaines utilisés.
Le test matériel commencerait par un écho brut, avant toute adaptation du
pont UART de la console. Les commandes EP0 privées actuelles ne seraient
pas disponibles automatiquement.

Cette piste reste distincte de la recherche de cause et de correction du
transport à 480 Mbit/s. Aucun remplacement de la pile de production n'a été
effectué à ce stade.

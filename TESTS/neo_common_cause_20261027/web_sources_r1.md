# Recherche primaire Pro Dock / Neo — 27 octobre 2026

Recherche documentaire, sans modification RTL, compilation ni accès carte.
Les versions d'un guide et d'une IP générée sont des numérotations distinctes.
Les conclusions ci-dessous ne constituent pas un diagnostic matériel.

## W1 — Révisions B/C : pas une distinction de boîtier

Sipeed, installation IDE :
https://wiki.sipeed.com/hardware/en/tang/common-doc/get_started/install-the-ide.html
Source du même document :
https://github.com/sipeed/sipeed_wiki/blob/main/docs/hardware/en/tang/common-doc/get_started/install-the-ide.md

La note indique une transition de B vers C à partir de juillet 2025 pour les
deux boîtiers 138K, PG484A et FPG676A. Elle impose la sélection Device Version C
pour une puce C, faute de quoi la SSRAM n'est pas utilisable. La fin de sa phrase
anglaise sur d'autres incompatibilités est tronquée : ne pas la compléter.
Cette note ne prouve pas la révision physique des deux cartes présentes.

## W2 — Identification physique et cohérence de cible

Sipeed, section Device Information :
https://wiki.sipeed.com/hardware/en/tang/common-doc/questions

Sipeed identifie la révision par le cinquième caractère de la troisième ligne
du marquage laser. Sa section ID code mismatch demande une cohérence entre
projet, contraintes de broches, modules IP et programmateur. L'absence d'erreur
ID ne démontre pas pour autant la compatibilité de chaque IP ancienne.
Le guide comprend aussi des conseils anciens sur les programmateurs : leur
applicabilité au matériel actuel doit être vérifiée avant toute transposition.

## W3 — GSR et configuration

Gowin DS1239-1.0.3E, daté 24/10/2025, sections 2.12–2.13, pages imprimées 28–29 :
https://cdn.gowinsemi.com.cn/DS1239E.pdf

Le GSR dispose de connexions vers la logique ; son utilisation est configurable
par registre CFU/I/O. Le chargement SRAM comprend une vérification CRC et les
données incorrectes empêchent le réveil. DONE/chargement réussi ne qualifie donc
pas les resets locaux ni les PLL. Ce document ne fournit pas ici d'erratum
commun B/C expliquant les symptômes observés. La date inscrite dans le PDF
fait foi, pas la date de publication affichée par un moteur de recherche.

## W4 — USB PHY : contraintes et portée du guide

Gowin IPUG781-1.7E, 18/07/2025, pages imprimées 9–11 :
https://cdn.gowinsemi.com.cn/IPUG781E.pdf

Le guide donne les attributs Arora V des sorties et comparateurs, recommande
un même bank 3,3 V et des longueurs PCB appariées. Le reset PHY est asynchrone ;
une entrée séparée indique le verrouillage PLL. Son tableau générique donne
60/480 MHz. Cela ne suffit PAS à condamner notre variante 960/120 : l'audit local
montre un DIV8 et la référence Sipeed associée spécifie 120 MHz. Il faut comparer
le contrat de la variante générée exacte, pas appliquer un tableau d'une autre
variante. La version 1.7 du guide n'est pas la version 3.5 du générateur IP.

## W5 — Limites nextpnr/Apicula, pas un erratum Gowin IDE

Rapport primaire d'un utilisateur du projet, ouvert le 11/10/2026 :
https://github.com/YosysHQ/apicula/issues/549

Le rapport décrit une seule porte BUFG déclarée dans la base Apicula 138C,
empêchant le placement de plusieurs horloges. Il concerne la base de données
et le placement de cette chaîne open source. Nos bitstreams comparés viennent
de Gowin : ce rapport ne démontre pas leur cause d'échec.

Correctif primaire Apicula, fusionné le 24/02/2026 :
https://github.com/YosysHQ/apicula/pull/466

Ce correctif porte sur le reset BSRAM dans la chaîne synth_gowin -family gw5a.
La discussion signale aussi une autre correction Yosys liée. À analyser comme
indice d'un contrat de primitive à respecter, jamais comme preuve que les FIFO
du composant sont défectueuses ou que Gowin applique le même mapping erroné.

## État des preuves

Aucune source primaire consultée ne démontre un erratum matériel commun à
tous nos échecs Neo. Les différences de cible, de génération IP et de séquences
de reset sont des pistes vérifiables. Un lien causal exige encore une mesure
discriminante ou un contre-exemple local reproductible.

## L1 — Release note officielle installée, complément local

`/home/michael/gowin/IDE/doc/RN100-1.9.12.03E_Gowin Software Release Note.pdf`,
page imprimée 3. Document primaire livré avec l'outil ; une recherche de son
URL publique exacte n'a pas abouti dans cette passe.

Le PHY USB 3.5 modifie les paramètres de contrôle de délai I/O. Le contrôleur
USB 3.3 ajoute des signaux de fin RX/TX, une interface de debug et des adaptations
de timing vers la logique utilisateur. Cela rend la différence entre les IP
actives pertinente ; cette note ne dit pas qu'elle corrige notre panne.

La même page annonce un avertissement lorsque les valeurs initiales des
registres avec set/reset asynchrones ne correspondent pas aux valeurs initiales
matérielles ; les valeurs incompatibles sont ignorées. Vérifier les warnings
et le mapping exact des chaînes de reset et CDC est une piste de contrôle,
pas la preuve qu'un tel avertissement existe dans nos builds.

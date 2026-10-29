# Complément documentaire et clôture des contre-revues

Le 27 octobre 2026, la documentation primaire MUG1031-1.3.1E du 23 janvier 2026 a été obtenue et archivée par le parent dans `../vendor_docs/`. Ce complément précise les limites de la matrice initiale ; il ne modifie aucun résultat antérieur.

- Page 11, table 4-1 : cœur jusqu'à 800 MHz ; bus DDR, AHB et APB sous 200 MHz ; CORE, DDR et AHB/APB annoncés asynchrones entre eux ; AHB/APB synchrones 1:1. Les 800/50/80/80 MHz et le raccordement AHB=APB actuels correspondent à ces éléments. Les groupes asynchrones CORE/fabric ne sont donc pas en eux-mêmes une faute.
- Page 46, §8.4.1 : chemin cœur imposé depuis PLL_R[0]/CLKOUT1. La contrainte `neo.cst:170` et le raccordement effectif satisfont cette exigence ; cela ne prouve pas que le PLL est physiquement verrouillé pendant l'échec R21.
- Page 11 : RTC indiqué à 32,768 kHz. L'exemple local Sipeed déclare pourtant 10 MHz (`/home/michael/gowin/ref/TangMega-138KPro-example/ae350_customized_demo/ReadMe.txt:11`, top `:66`, ODIV4=80). Notre configuration reprend ces 10 MHz. La divergence documentaire reste à clarifier ; aucune causalité de panne ni invalidité universelle des 10 MHz n'est établie.
- Page 13 : POR_RSTN et HW_RSTN sont nommés, mais aucune durée minimale ni séquence détaillée de libération n'a été identifiée dans les passages étudiés. La lacune concernant ce contrat demeure.
- La note historique du 25 octobre attribue 20 ms à un exemple SDK. Cette attribution n'a pas été reliée à un fichier source exact pendant cet audit. Un 20 ms trouvé dans `key_debounce.v` concerne l'anti-rebond et ne doit pas être transformé en durée de reset CPU. Le choix expérimental de 50 ms reste établi ; son statut de minimum constructeur ne l'est pas.

## Seconde passe Fable

Fable r2 retire explicitement les conclusions dues aux clés JSON absentes, à l'extrait SDF partiel et à une politique inventée interdisant tout reset sur LW. Il conclut qu'aucun patch n'est justifié par les preuves disponibles. Cette conclusion est retenue, avec les corrections suivantes :

- 679 mentions de AHB_CLK ne sont pas 679 arcs distincts ; 26 mentions de CORE_CLK ne sont pas un nombre de chemins qualifiés.
- Le +4,515 ns sur holding → init_sync0 vient d'un contrôle setup/max_delay, pas d'un contrôle hold.
- Les bits 60, 62 et 63 partagés sont les bits constants du préfixe D de l'observateur, déjà vérifiés dans le test mappé et l'audit des bits. L'unicité des drivers n'est pas une exigence pour des constantes égales.
- Un journal caméra vide est normal lorsque ffmpeg utilise `-loglevel error` sans erreur. Le fichier image est la preuve visuelle. Il ne faut pas assimiler ce journal vide à une défaillance de collecte. La collision de nom FileExistsError reste consignée séparément.
- La relecture SRAM n'est pas disponible sous SecurityBit_ON. L'absence de comparaison logicielle du checksum n'implique pas l'absence du CRC matériel de configuration. Ces limites étaient déjà examinées dans `../programmer_comparison_02/`.
- Le classement de plausibilité des hypothèses reset/DDR/route n'est pas retenu : aucun état matériel ne permet encore de les ordonner.

## Conclusion vérifiée des trois modèles

Les trois premières revues indépendantes et leurs contre-vérifications ne démontrent aucune cause matérielle nouvelle. Les conclusions conservées sont : échec R21 réel, invariance fonctionnelle étayée, STA global FAIL, plusieurs exigences d'interface documentées satisfaites, contrat de démarrage POR/HW encore incomplet dans les preuves et fermeture JTAG explicite manquante dans le SDC.

Aucune modification RTL, exception de timing ou contrainte de ressource n'est appliquée sur cette base. Tous les processus de contre-revue sont terminés ; aucun processus matériel ou de routage n'a été lancé par cet audit.

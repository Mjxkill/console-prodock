# Audit hors exécution — reprise Pro Dock SD R3

Le blocage observé est **avant le placement**, dans la lecture de la référence
incrémentale. Aucun élément présent ne permet de le relier au timing FPGA ou
aux réseaux LW. Aucun Gowin, debugger, arrêt de processus ou accès carte n'a
été lancé par cet audit. R3 reste sous la responsabilité de root.

## Faits vérifiés

- Netlist R2 et R3 strictement identique : SHA
  `68939b82531af6aba764d96d3ee45e6b34ee6e447bb77d773d78bec22ebfebe9`.
- CST R2/R3 identique. Le SDC R3 retire uniquement cinq requêtes
  `report_timing` ; toutes les définitions d'horloges et exceptions sont identiques.
- R2 a fini son placement et son routage puis s'est arrêté avec SIGSEGV (-11)
  après « Running timing analysis ». Aucun FS, TR, VO ou SDF final.
- R3 accepte la netlist et le CST mais son journal ne contient pas
  « Running placement ». La pile rapportée par root est
  `ENCRYPTFILE::Prreader::decryptDataBlockContent → prparse → readprfile`.
  Cette pile n'a pas été recapturée par cet agent.
- R3 lit une copie exacte du PR de R2 : 335 301 361 octets,
  SHA `15e7b0a1eb8d4b989543e34fb89c20fb27753b0374caa53d1f9a4e2f0ee6814f`.
- R2 avait lu le PR G22r0 avec le même exécutable Gowin avant de placer/router.
  Cette référence fait 281 464 344 octets,
  SHA `b0cfffbed2295bf54285f90c2f59a1f002026250ac3ad5f827c3f34e897141d0`.
- R2 : `cmd.do` à 23:03:51, `.p` à 23:17:17 : environ 13 min 25 s
  pour la période comprenant chargement de référence et placement. Ce n'est
  pas une mesure isolée du déchiffrement. R3 dépasse 25 minutes avant placement.

## Ce que l'enveloppe PR permet de dire

Les deux fichiers ont les mêmes identifiants de format de protection, la même
clé nommée GWK2022-11, et des marqueurs begin/end équilibrés : 113 021 paires
G22r0, 113 260 R2. Ils ont tous deux une clôture finale. La copie R3 est complète.
Cela réfute une simple copie tronquée ; **cela ne valide pas le contenu PR**.

Les données base64 contiennent plusieurs segments rembourrés concaténés. Un
unique `base64.b64decode(..., validate=True)` appliqué à tout un bloc produit
un faux rejet également sur G22r0. Après décodage segment par segment, tous les
segments sont syntaxiquement lisibles ; 15 tailles déclarées G22r0 et 10 R2
excèdent de 16 octets le total décodé. Ces exceptions existent dans la référence
que Gowin sait lire : elles ne sont pas classées comme corruption R2.

Le plus grand bloc déclaré passe de 58 104 128 à 98 794 272 octets. C'est un
changement de charge de lecture possible, sans démonstration de complexité,
boucle infinie, fichier invalide ou défaut cryptographique. Aucun déchiffrement
ni interprétation des données propriétaires n'a été tenté.

## Prochaine action discriminante proposée à root

Dans **un nouveau candidat**, conserver la netlist R2 exacte, le CST, les
contraintes R3 et les options PnR ; changer seulement la référence `-inc_pnr`
pour la copie protégée de G22r0, déjà lue avec succès par ce même Gowin.
Aucune resynthèse, modification RTL, changement d'horloge ou optimisation n'est
nécessaire pour cet essai. Ne pas modifier le répertoire R3 actif.

- Si ce candidat atteint rapidement le placement, le blocage précédent est lié
  à la lecture/utilisation de la base R2, sans prouver que celle-ci est corrompue.
- S'il bloque aussi dans le lecteur, la suspicion s'étend au lecteur ou à son
  interaction avec le candidat. Ce n'est toujours pas un échec de timing FPGA.
- Si le routage termine puis la STA replante, la panne STA R2 reste distincte.
  R3 n'a pas encore testé l'hypothèse « suppression des rapports évite le crash ».

La préparation actuelle `resume_sd_fpga.py` lance automatiquement Gowin et son
`subprocess.run` n'a pas de timeout. Elle ne fournit donc ni mode de préparation
seule ni borne de phase. Root doit décider de l'arrêt/reprise et conserver les
logs/identités ; cet audit ne tue pas le processus pour obtenir le test.

## Alternatives minimales documentées

1. **Réutiliser uniquement le placement R2** : remplacer `inc_pnr` par
   `set_option -inc_place {copie_exacte_du_R2.p}`. Le fichier `.p` fait
   11 028 136 octets et a été écrit avant le routage et avant le crash STA.
   Cela contourne le gros PR de routage en gardant un placement comme référence.
   Il n'a pas été relu par Gowin dans cet audit : son intégrité sémantique reste
   inconnue, même s'il précède l'échec.
2. **Désactiver l'incrémental** : conserver la même netlist synthétisée et retirer
   `inc_pnr` / `inc_place`. Cela évite entièrement le lecteur de référence, mais
   impose un nouveau placement/routage complet, pas une nouvelle synthèse.

Chaque alternative peut changer les routes physiques et nécessite ses propres
rapports temporels et essais. Aucune ne permet de prétendre conserver le routage
G22r0 ou de promouvoir la carte sans validation.

Documentation primaire installée : SUG100-4.4.6E, §4.3 p.41–42 décrit `.p`
pour placement et `.pr` pour placement/routage. SUG1220-2.0E p.44 donne les
options Tcl `-inc_place` et `-inc_pnr` ; sa ligne de tableau mentionnant `.p`
pour `inc_pnr` paraît incohérente avec SUG100 et avec l'usage `.pr` déjà réussi.
Ne pas convertir ni renommer un format pour contourner cette coquille.

Les identités et observations numériques sont dans `observations.json`.

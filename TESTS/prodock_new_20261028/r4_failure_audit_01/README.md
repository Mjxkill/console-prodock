# Échec R4 au démarrage de la STA — diagnostic hors carte

R4 ne fournit pas de bitstream ni de VO post-routage. Le processus retourne1
après « Running timing analysis », puis Tcl signale `run pnr`, sans message
ERROR détaillé. Ce n’est pas un résultat de timing négatif mesuré : aucune
STA/TR exploitable n’a été publiée. Le gate ROM n’a pas été exécuté.

## Faits établis

| Version | Retour outil | Dernière phase | report_timing supplémentaires | Ancre incrémentale | VG |
|---|---:|---|---:|---|---|
| R2 | −11 (SIGSEGV du processus lancé) | STA en cours | 5 | PR G22r0 | 68939b82… |
| R3 | 0 | STA et artefacts complets | 0 | PR R2 | même VG R2 |
| R4 | 1 (erreur Tcl, signal non établi) | STA en cours | 0 | PR G22r0 | nouvelle VG6358e266… |

Les SDC R3 et R4 sont **identiques**, SHA f50b4cf3b67b390e052ff27289929dfeb272f0c6c530fc523332634f784e2132.
Après normalisation des chemins/noms, cmd.do diffère seulement par
`reference_sd_r2.pr` contre `reference_g22r0.pr`. Cela ne rend pas les entrées
identiques : le contenu VG R4 diffère, car l’IP AE350 a été correctement
régénérée avec la nouvelle ROM et la version fournisseur actuelle.

Le succès R3 avait modifié **deux facteurs** : rapports et ancre incrémentale.
Il ne démontrait pas que les rapports supplémentaires causaient le crash. R4
réfute en tout cas l’idée que les retirer suffirait à garantir le succès.
R3 avait publié des violations STA tout en retournant0 et produisant FS/VO :
le retour1 de R4 ne permet donc pas d’inventer un slack ou de l’expliquer par
un LW particulier. Les PR1014 clk_d/ae350_tck_d/rtc_clk existent aussi sur R3.

R4 a laissé VG, .p, .db et .pr. Le PR fait335303259octets avec113260paires
begin/end_protected équilibrées, comme le PR R2 laissé après son échec.
Ce contrôle détecte une coupure grossière, **pas une intégrité interne**.
Le PR R2 a effectivement été relu par R3 et a permis un résultat complet ;
c’est une preuve que ce type d’artefact peut être réutilisable, pas une preuve
que tout PR échoué est valide. .db R4 est identique à R2 (SHA327866ac…),
mais .p diffère : ne pas annoncer des placements/routages identiques.

Aucun coredumpctl n’est installé. /var/crash ne contient pas de rapport Gowin
lié à cet essai. La recherche journalctl sur06:10–06:15 n’a retourné aucune
entrée correspondante accessible. Cela ne prouve ni absence de crash interne
ni absence d’épuisement mémoire. Sans pile ou message d’erreur supplémentaire,
la cause interne reste inconnue (erreur calcul/report STA, état incrémental,
ressource système ou autre). Aucun défaut de RTL/DDR n’est démontré ici.

## Reprise minimale proposée, non lancée

1. Nouveau candidat ProDock explicite, copie figée des sources R4 pour la
   provenance et surtout de sa VG exacte6358e266cdc3ffd647d643a474f24b5882c11dacf4207c4687dde703a3f4969b.
2. Copier PR R4 en nouvelle ancre, avec SHA avant/après ; conserver CST, SDC
   et options de R4 strictement. Changer uniquement chemins, nom et ancre.
3. Projet avec une seule netlist VG + CST + SDC et `run pnr`, sans `run syn`,
   sans régénération AE350 et sans nouveau RTL. R3 fournit la preuve concrète
   du mode « Skip synthesis, because there is only one netlist file ».
4. Vérifier dans le résultat qu’aucune synthèse n’a eu lieu et que VG/entrées
   n’ont pas changé. Une reprise incrémentale peut encore replacer/rerouter ;
   il faut une **nouvelle STA complète**, sans exceptions ajoutées pour masquer
   les chemins. Ce n’est pas une commande STA seule ni une reprise à95%.
5. Exiger FS/VO/TR complets, comparaison ROM exacte via le checker corrigé,
   pins/horloges/provenance puis revue root avant essai SRAM. Pas de flash
   permanente ni conclusion de boot autonome sans cet essai.

Le helper historique resume_sd_fpga.py est **inapplicable tel quel** : R2/R3
sont codés en dur, il exige−11 et exactement5requêtes à retirer. R4 retourne1
et ses requêtes sont déjà absentes. Retirer d’autres contraintes ou utiliser
R3 comme source logique réintroduirait notamment son ancien firmware ROM.

Le manuel officiel SUG1220-2.0E pp16/44 documente `run syn|pnr|all`, inc_place
et inc_pnr. Aucune commande « run sta » n’est établie dans cette recherche.
Son tableau inc_pnr mentionne*.p, alors que le fonctionnement sur*.pr est
attesté par le précédent R3 ; la procédure doit lier cet usage à cette preuve.

Le watcher799871 s’est fermé spontanément avec exit1 sur le garde build_result.
Aucun signal n’a été nécessaire et aucun checker ROM n’a couru sur ce build
incomplet. Tous les fichiers de compilation restent inchangés. Beam produit
une contre-analyse bornée sur une copie de ces seuls journaux/faits/docs ;
son résultat, quel qu’il soit, ne remplacera pas les preuves du compilateur.

## Contre-avis Beam terminé et contradiction contrôlée

Beam a exécuté un lot complet :22requêtes,30outils,69,61s, tests officiels
échoués avant édition puis PASS après code et rapport. Les11champs factuels
sont cohérents et les processus sont sortis. La revue indépendante accepte
ces constats mais **rejette un point de son plan** : il présente R4VG+R4PR
comme déjà essayé, alors que cmd.do prouve que R4 utilisait encore PR G22.
Cette combinaison reste précisément le prochain test proposé. La matrice de
quatre relances spéculatives proposée par Beam n’est donc pas retenue.
`beam_independent_review.json` conserve les citations, contradictions et SHA ;
la sortie du modèle reste intacte et aucune note qualité n’est auto-attribuée.

Si le test unique R4VG+R4PR échoue également, l’étape utile sera une trace
réelle de l’erreur/du signal interne au même stade, pas une nouvelle variation
de RTL ou de contraintes. Cette instrumentation d’un futur processus reste
à préparer par root ; aucun outil ni compilateur n’a été relancé ici.

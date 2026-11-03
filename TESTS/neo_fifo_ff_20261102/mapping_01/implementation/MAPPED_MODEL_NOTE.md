# Modèle de simulation mappée : échec initial et spécialisation prouvée

Le premier banc mappé utilisant toute la hiérarchie officielle de LUT a expiré
après 90 secondes sans verdict. `run_mapped_01/RESULT.json` conserve cet échec
et les sources du banc de cette tentative. Il ne s’agit pas d’un PASS.

Les probes `mapped_progress_01/` ont ajouté des checkpoints et `vvp -v`.
Avec sortie non tamponnée, le chargement est terminé en 1,97 s, puis le
simulateur reste pendant 45 s sur **propagate initialization events**, avant
l’exécution du premier checkpoint à t=0. La hiérarchie élaborée compte
86 174 scopes et 189 975 functors : les LUT officielles se décomposent en mux
UDP. Le graphe externe du helper ne possède aucun cycle combinatoire ni
pilote multiple d’après le contrôle indépendant `build_review_01/HELPER_GRAPH.json`.
La cause interne précise dans Icarus n’est pas établie ; ce n’est pas une
preuve de boucle dans le FPGA. Les probes ont été arrêtés de façon bornée.

Pour reprendre le banc sans modifier le candidat, `lut_model.py` produit une
**bibliothèque de test** de moins de 1 000 lignes. SDPB, DFFRE, GSR, VCC et GND
sont des extractions exactes du modèle fournisseur. LUT2/3/4 sont exprimées
par le même arbre de mux, avec des ternaires scalaires à quatre états.

La correspondance est vérifiée face aux modèles LUT officiels pour les
183 couples largeur/INIT présents dans ce VG et toutes les 256 combinaisons
de quatre entrées 0/1/X/Z : **46 848 comparaisons PASS**. Les entrées non
utilisées des LUT2/3 entraînent des répétitions, pas une couverture manquante.
Le résultat et les empreintes sont dans `lut_model_01/RESULT.json`.

Ce n’est pas un simple index `INIT[adresse]` : ce dernier perdrait la résolution
d’une constante lorsque certaines entrées sont X. Le ternaire combine deux
valeurs égales en une valeur connue et produit X si elles diffèrent. INIT est
entièrement binaire dans toutes les cellules testées ; les données intermédiaires
peuvent donc être 0/1/X, jamais Z. La différence entre un mux UDP et un ternaire
sur une **donnée Z** est hors de ce domaine et n’est pas masquée.

Limites : équivalence de valeurs après stabilisation ; aucun engagement sur
le nombre de delta-cycles, aucun délai SDF, aucune métastabilité ni qualification
physique. Le banc garde les mêmes stimuli, les mêmes durées et les six profils.
Aucun fichier du helper synthétisé, des mémoires applicatives ou du bitstream
n’a été modifié pour cette accélération de simulation.

## Résultat discriminant ultérieur — la réduction des LUT ne suffit pas

Le premier essai avec LUT ternaires a lui aussi expiré avant verdict ; la suite
a été interrompue avant de répéter inutilement ce délai. `minimal_01` élimine
SDPB et le banc complexe : le helper RTL atteint #1 ns en 0,51 s, alors que
le helper mappé avec chacune des deux bibliothèques n’atteint pas t=0 en 8 s.
La hiérarchie UDP seule n’est donc pas l’explication suffisante. La bibliothèque
ternaire validée reste une preuve de tentative, **elle n’est pas employée pour
la qualification finale**.

Le contrôle suivant ne change que la représentation du fil `words[4095:0]`
à 4096 pilotes FF. Ses 8192 usages sont tous des indices littéraux ; aucun
usage vectoriel ou dynamique ne subsiste dans le VG. Une copie de simulation
remplace ce seul vecteur par 4096 fils scalaires nommés bijectivement. Avec la
bibliothèque Gowin **officielle intégrale**, le même top minimal atteint alors
#1 ns en 2,12 s, dont 1,97 s de chargement et 0,09 s de simulation.

`scalarize.py` exige les empreintes du VG, l’absence de collisions de noms,
deux usages par bit et une inversion textuelle **octet par octet**. La preuve
est `scalarized_01/PROOF.json`. Aucune cellule, valeur INIT, connexion logique,
horloge, reset ou fonction n’est modifiée. Il s’agit d’un problème de simulation
lié à la représentation du bus multi-pilotes dans Icarus ; son mécanisme interne
précis n’est pas déterminé. La lecture de pile GDB était refusée par le sandbox
et n’a produit aucune preuve ; ce refus est conservé dans `mapped_progress_01`.

Le banc complet repart sur cette copie, avec les mêmes six profils et la
bibliothèque officielle. L’assemblage destiné au FPGA garde le VG original
`dedea942...2d89`, sans scalarisation. Seul son résultat effectivement terminé
peut être utilisé pour la qualification mappée ; aucune attente n’est un PASS.

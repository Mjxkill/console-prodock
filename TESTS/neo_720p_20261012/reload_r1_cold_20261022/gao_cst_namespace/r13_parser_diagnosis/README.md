# R13 : pourquoi le backend affiche l'aide

L'appel de R13 emploie la bonne forme `argc=3`, `argv={exécutable, "-do", fichier}` et le même booléen `false` que le Proxy Gowin. Le défaut du wrapper est l'initialisation incomplète du parseur dans ce mode. Il ne précharge aucune des entrées que le Proxy précharge avant de lire `cmd.do`.

La lecture du binaire installé établit la chaîne suivante, sans lancer Gowin :

1. Le [Proxy officiel](proxy_launch_full.asm) appelle `addArguments` pour le composant (0x6c04), la référence complète (0x6d5f), la netlist (0x6eba), la configuration (0x7016), puis, lorsque présentes, les contraintes SDC (0x8578), CST (0x8690) et la netlist GAO (0x8708). L'appel `readInUserCommand(3, argv, false)` est à 0x7524–0x752e. Les autres entrées optionnelles du Proxy ne figurent pas dans ce candidat.
2. Dans [parseScriptFile](parse_script_full.asm), le booléen `false` conduit aux comparaisons des sélecteurs `-d`, `-design`, `-gao`, `-p`, `-cfg`, `-cst`, `-cst_1`, `-sdc`, `-scf`, `-pn` et `-csr`. Une correspondance saute leur insertion et reprend la boucle à 0x7b67c0. Ce mode conserve donc les entrées initialisées par le Proxy au lieu de les remplacer par celles du fichier.
3. Le wrapper R13 commence par `clearAllArguments`, puis ne fait aucun `addArguments`. La présence de `-d` dans le fichier ne répare pas cette omission : il est ignoré dans ce mode.
4. [isArgumentsLegal](arguments_legal_full.asm) cherche `-d`, puis `-design`, puis `-pdl`. En leur absence, il imprime l'aide à 0x7b46f6 et renvoie `false`. [readInUserCommand](read_user_full.asm) transforme ce refus en retour 1 à 0x7d59f4–0x7d5a09. Cela explique exactement le symptôme du journal R13 : aide sans erreur de fichier, puis retour 1.

Le chemin textuel de `argv[0]` ne détermine pas ce refus : [parseCommandLine](parse_command_full.asm) le conserve comme nom d'exécutable, puis traite `-do`. Le parseur de script accepte les options ligne par ligne. Aucun argument n'a besoin d'être regroupé dans une seule chaîne.

La correction proposée est un **nouveau wrapper et un nouveau dossier candidat**, conservant R13 intact : précharger les sept valeurs exactes `-p/-pn/-d/-cfg/-cst/-sdc/-gao` du `cmd.do` figé, puis garder `false` et le même appel. Vérifier explicitement les sept valeurs après le parseur et la valeur de `-gao_cst`. Conserver le contrôle des cinq chemins résolus dans `globalMem`, ainsi que toutes les identités, `-cst_error`, audits et gardes déjà prévus. Ajouter un test qui refuse de parser sans ces seeds ; les anciens mocks n'émulaient pas cette condition et n'avaient donc pas détecté le défaut.

Il ne faut pas changer simplement le booléen en `true` pour contourner ce contrat : cela sélectionnerait un autre mode que le lanceur officiel étudié. L'étape suivante doit rester **arguments seulement**, sans `executePnrTask`, avant toute autorisation de routage.

Les SHA des deux bibliothèques, du wrapper R13, du manifeste, de `cmd.do`, du résultat et du journal conservés sont dans [evidence.json](evidence.json). L'analyse est statique ; le succès du futur parseur, la résolution du net GAO `control0[0]`, son allocation d'horloge et les résultats de placement/routage restent non démontrés. Le refus R13 n'est pas un refus de licence ni un résultat concernant cette contrainte GAO.

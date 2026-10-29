# LUMA — musique YuE2

La banque comprend **25 morceaux prévus et deux pilotes réellement produits**.
Chaque pilote dure 24 secondes, en FLAC16 stéréo 48 kHz, sans saturation détectée ;
leurs boucles de 23,875 secondes passent le contrôle technique. L'écoute musicale
reste en attente. Le pilote B comparatif utilise une partition originale.
Les six premières ambiances régionales ont été produites : six boucles passent
le contrôle technique. Le premier rendu Nuages contient deux échantillons au
plafond PCM ; il est conservé comme FAIL, sans boucle. Sa révision r2 passe,
avec une crête de −5,112 dBFS. Cuivre s'arrête à 40,24 secondes au lieu des 64 demandées ; sa boucle
dure 40,115 secondes, avec avertissement de durée. Les dix-neuf autres morceaux
attendent l'appréciation musicale des premiers.
Le modèle installé est
`yue2_3b_int8_convrot.safetensors`. Après avoir été arrêté lors de la préparation,
le service répond maintenant sur `http://gx10-2:8188`, ComfyUI 0.39.0 sur GB10.
Les 27 graphes initiaux et la révision Nuages sont vérifiés contre les schémas de l'API active. Les pilotes
partagent une file sérialisée avec les visuels ; aucun modèle n'a été
téléchargé et aucune autre méthode de génération musicale n'est utilisée.

## Direction musicale

L'aventure doit avoir de la tendresse, de l'air et une mémoire. Un petit
ensemble acoustique accompagne les personnages ; les passages grandioses
gardent une taille humaine. Une mélodie originale de huit mesures relie les
régions : ré–la–si–ré aigu, puis une réponse descendante. Le fichier de chaque
cue contient sa partition ABC, son style, sa graine et ses paramètres.
Le contrôle de la partition par le modèle reste à vérifier à l'écoute.

| Région | Couleur | Transformation du motif |
|---|---|---|
| Val des Lanternes | Flûte en bois, cordes pincées, piano feutré | Présentation simple, ample et chaleureuse |
| Canopée de Verre | Flûte basse, verre, marimba, pizzicati | Réponses fragmentées, silences, couleur dorienne |
| Archipel des Marées | Clarinette, guitare, vibraphone | Phrases bercées, basse plus mobile |
| Ateliers du Soleil | Cuivres assourdis, dulcimer, bois | Motif rythmé, réponses mécaniques espiègles |
| Mer des Nuages | Harpe, harmoniques de cordes, cor doux | Notes tenues, élans ascendants, espace |
| Jardin des Retours | Violoncelle, piano, flûte, verre lointain | Souvenirs des autres timbres, résolution intime |

Chaque région dispose de deux explorations et d'un mystère. Les autres cues
couvrent village, escarmouche, gardien, voyage au sol, voyage aérien, victoire
et découverte. L'objectif de campagne de 6–10 heures est une intention de
conception ; il n'est pas une durée mesurée. La musique alterne des variations,
des retours de motifs et des périodes calmes ; 25 titres ne prouvent pas à eux
seuls la qualité musicale sur cette durée.

## Pilotes et graphes réels

`workflows/pilot_a_free.json` teste 24 secondes instrumentales sans partition ;
`pilot_b_motif.json` teste la même couleur et graine avec la partition originale.
Les paroles restent vides. Le code installé autorise une chaîne vide ; il reste
à vérifier que le rendu ne contient ni chant ni pseudo-paroles. Un échec vocal
doit conduire à retravailler le prompt YuE2, pas à substituer un autre modèle.

Les graphes au format API contiennent sept nœuds : chargement du checkpoint,
`YuE2GenerateMusic`, `ConditioningZeroOut`, `EmptyYuE2LatentAudio`, `KSampler`,
`VAEDecodeAudio`, `SaveAudio`. Le latent prend la durée **effectivement produite**
par YuE2. Le sampler reprend le blueprint installé : 32 pas, `dpm_2`,
`sgm_uniform`, CFG 1. La sortie native FLAC conserve le rendu avant adaptation
pour le jeu. L'ABC est fourni directement ; le nœud de génération ABC n'est
pas requis pour ces pilotes et sa présence ne déclenche pas de second job.

Les copies des sources installées et du blueprint sont dans `../art/provenance/` ;
leurs empreintes sont dans le manifeste. Le SHA du checkpoint installé, calculé
en lecture seule sur gx10-2, est conservé dans `provenance/model.json` et dans
les QA des rendus. Garder pour chaque rendu le graph exact envoyé,
l'identifiant du prompt, l'historique ComfyUI, la version ComfyUI, le SHA du modèle,
le fichier natif et son SHA. Une graine fixe facilite la reproduction ; elle
ne garantit pas une identité binaire entre environnements GPU différents.

Ne soumettre qu'un pilote à la fois, après les premiers visuels. Contrôler son
audio avant le deuxième ; ne pas lancer toute la banque avant ces résultats.
`prepare_bank.py` écrit uniquement des fichiers locaux et n'appelle aucun réseau.

## Contrôle et adaptation

Depuis la racine du dépôt :

```sh
python3 games/luma_adventure/audio/prepare_bank.py
python3 games/luma_adventure/audio/validate_bank.py
python3 games/luma_adventure/audio/test_audio.py
python3 games/luma_adventure/audio/test_sdl_backend.py
python3 games/luma_adventure/audio/audio_tools.py inspect games/luma_adventure/audio/renders/raw/pilot_a.flac --out games/luma_adventure/audio/qa/pilot_a.json
python3 games/luma_adventure/audio/audio_tools.py prepare games/luma_adventure/audio/renders/raw/aube_explore_00001_.flac --cue aube_explore --history games/luma_adventure/audio/provenance/aube_history.json
```

Pour enregistrer un pilote, conserver le nom de fichier natif annoncé par
ComfyUI et son historique complet :

```sh
python3 games/luma_adventure/audio/review_pilot.py --id pilot_a_free --source games/luma_adventure/art/music_staging/pilot_a_free_00001_.flac --history games/luma_adventure/art/music_staging/pilot_a_history.json
```

L'importeur exige le graph exact du pilote, une exécution réussie et un nom de
sortie correspondant à l'historique. Il conserve le FLAC, son SHA et l'historique,
puis crée deux WAV et `audition.html` pour comparaison locale du rendu et du
raccord. Aucun outil d'écoute ou de transcription n'est disponible dans la
session au constat initial. Une tentative de lecture d'un extrait via
`AudioContent` confirme que le modèle de cette session ne prend pas l'audio en
entrée ; l'audition reste donc explicitement en attente. Ouvrir `audition.html`
pour écouter les fichiers réels et leurs boucles ; ce résultat ne vaut pas
validation automatique pour le jeu.

Les deux dernières commandes nécessitent de vrais rendus ; elles ne fabriquent
aucun substitut. `inspect` relève durée, taux natif, canaux, niveau crête/RMS,
saturation, silence, composante continue et saut au raccord. `prepare` exporte
du WAV PCM16 stéréo 48 kHz, avec marge crête d'au moins 2 dB, sans amplification
automatique. Un fichier déjà présent n'est pas remplacé.

Une boucle recouvre 125 ms de fin et de début avec un fondu à puissance constante.
Le raccord externe est une paire d'échantillons adjacents du son d'origine ;
la jointure ne dépend pas d'un passage forcé par zéro. La durée exportée est
raccourcie de 125 ms. Ce traitement évite un raccord électrique abrupt ; il
ne prouve pas la continuité harmonique ou rythmique. Ajuster `--start`, `--end`
et `--crossfade` après écoute de trois répétitions. Les cues non bouclés ont de
courtes enveloppes de 10 ms ; préserver une fin musicale naturelle dans le prompt.

Le manifeste passe à `generated`, jamais automatiquement à `ready`. Pour
promouvoir un morceau après écoute, renseigner `audition: "approved"`,
`status: "ready"` et conserver le QA PASS associé au SHA du WAV. Vérifier aussi
absence de voix, adéquation au monde, fatigue sur trois répétitions, raccord
musical et niveau avec dialogues/effets. Le validateur refuse un cue `ready`
sans fichier, empreinte correcte, audition approuvée et QA PASS.

## Contrat avec le jeu

`manifest.json` contient `cues[]`. `world` vaut 0–5 pour une région et −1 pour
un cue partagé. `file` est relatif à `games/luma_adventure/`, par exemple
`audio/renders/aube_explore.wav`. Ne charger que `status == "ready"` et un
chemin non nul. Les morceaux manquants donnent du silence ; aucun son fictif
n'est annoncé. Le PCM stéréo 48 kHz coûte 192 ko/s, soit environ 12,3 Mo pour
64 secondes. Le chargement de toute la banque en RAM est inutile.

Priorité souhaitée : victoire, gardien, combat, mystère, village, voyage,
exploration. Le jeu peut utiliser un sous-ensemble. Prévoir 1,8 s pour les
transitions de région et 350 ms pour l'entrée en combat ; attendre 4 s après
la dernière menace avant de revenir à l'exploration. Les variantes A/B peuvent
alterner après deux boucles ; ne pas annoncer de synchronisation à la mesure
avant vérification du tempo réel. Une baisse de volume pendant dialogue/pause
est souhaitée. Ces métadonnées ne prouvent pas que le mélangeur les implémente.

Le frontend PC est en C/SDL2 ; son propriétaire réalise l'intégration audio.
Le module `luma_audio.c` est fourni avec son en-tête :

```c
luma_audio_init();                       /* après SDL vidéo */
luma_audio_transition(1800);             /* 350 ms pour combat si souhaité */
luma_audio_play(path_from_ready_cue, 1);  /* chemin WAV, lecture en boucle */
luma_audio_pause(game_is_paused);        /* baisse 50 ms puis gèle la position */
luma_audio_play(NULL, 0);                /* arrêt avec fondu */
luma_audio_shutdown();                   /* avant SDL_Quit */
```

Ajouter `audio/luma_audio.c` aux sources et inclure `audio/luma_audio.h`.
`LUMA_HOST` active SDL ; sans ce symbole, les fonctions restent silencieuses et
`init` renvoie 0. Le chargement et la conversion WAV ont lieu dans le thread du
jeu au changement de cue. Le callback ne fait aucune lecture disque, aucune
allocation et mélange au plus deux pistes en PCM16 stéréo 48 kHz. Deux boucles
de 64 secondes occupent environ 24,6 Mo ; ce module PC ne constitue pas un
streamer SD ni un backend carte. Un changement très rapide de trois cues peut
remplacer la voix la plus faible avant la fin de son fondu ; le moteur doit
garder l'hystérésis de combat prévue.

Le test SDL force le pilote `dummy` : vrai pilote YuE2, conversion d'un signal
temporaire mono 22,05 kHz, boucle courte, fin de son, pause et arrêt silencieux.
Les résultats sont dans `qa/backend_validation.json`. Il n'ouvre aucune sortie
physique et ne remplace pas une écoute. Un diagnostic explicite peut charger
un cue `generated`, mais la lecture normale reste réservée aux cues `ready`.

SDL2 2.30 et ffmpeg sont déjà disponibles sur le PC. Les tests audio utilisent
des sinusoïdes temporaires comme fixtures ; elles ne sont jamais des assets LUMA.

Les sources `linux/configs/linux.config`, les deux DTS et `linux/drivers/` ne
définissent pas de backend audio exploitable. La feuille de route L07 demande
encore de choisir et qualifier la sortie physique ; `ARCHI/PORT_NEO_720P.md`
précise que l'audio HDMI n'est pas implémenté. Aucun essai ni changement matériel
n'est effectué ici. Les sorties Pro Dock et Neo restent **indisponibles et non
qualifiées** pour ce jeu, quelle que soit la qualité des assets produits sur PC.

# Cône busy et origine vidéo — vérification du premier avis Fable

L'entrée D de `u_accel/busy_sync_0_s0` est effectivement combinatoire et issue
de plusieurs registres du domaine GPU. Cette structure existe aussi dans la
référence Pro Dock ; elle n'est pas une différence Neo nouvellement découverte.

Sur les trois netlists examinées (G22r0, R19, R21r2), le cône contient 12 cellules
combinatoires et 21 FF sources, tous cadencés par `gpu_clk` : les 16 bits de
pointeurs wp/rp, le bit d'état IDLE, les trois bits `command_word` et le flag
`head_valid` de la FIFO. Les ports de sortie des primitives sont tirés du modèle
Gowin officiel, notamment SUM/COUT des ALU. L'extraction ne rencontre aucun
pilote inconnu. `result.json` conserve cellules, paramètres, raccordements,
lignes et empreintes.

Le RTL sur les deux cartes est :

```
fill = wp - rp;
cmd_avail = fill >= 8;
blitter_busy = !st[IDLE] || cmd_avail;
busy_sync <= {busy_sync[0], blitter_busy || queue_valid || command_word != 0};
```

Cela permet des transitions combinatoires intermédiaires en amont du premier
synchroniseur. Les deux FF de destination ne garantissent pas que toute impulsion
combinatoire corresponde à un état enregistré de la source. C'est une faiblesse
à examiner pour la fiabilité du **statut busy**, sans preuve ici d'une occurrence
physique ou de sa durée.

La portée est déterminante : dans les trois `.vo`, la sortie de `busy_sync_0`
ne pilote que D de `busy_sync_1`. La sortie du second ne pilote qu'une LUT du
multiplexeur `response_data_0`, retour du registre AHB. Le RTL ne l'utilise pas
pour les CE des paquets, la validation COPY, les requêtes DDR, le reset ou la
machine blitter. Une fausse lecture busy pourrait modifier le comportement d'un
logiciel qui ne consulte que ce bit ; elle n'établit pas directement la cause
des rejets internes COPY ou des compteurs done/réjection effectivement observés.
Leur chemin causal devrait être démontré séparément.

Le chemin R21r2 est mesuré à −4,813 ns, contre −2,888 ns sur R19. Le détail R21r2
(`neo_r21r2_path.txt`) n'est pas dominé par un décalage des horloges :

- arrivée horloge source : 3,332 ns ; destination : 3,529 ns ; skew +0,197 ns ;
- C2Q : 0,344 ns ; logique : 2,059 ns ; fils de données : 10,515 ns ;
- un fil entre les LUT `gpu_debug_state_100_s0` et `gpu_debug_state_96_s0`
  prend 6,094 ns, puis 2,966 ns jusqu'à la LUT finale ;
- contrainte inter-domaines héritée : 8 ns, incertitude 0,035 ns, setup 0,057 ns.

Ces noms `gpu_debug_state_*` désignent ici des sorties fonctionnelles optimisées
partagées avec les observations. Le nom seul ne rend pas le cône diagnostique.
Le rapport G22r0 ne fournit pas ce chemin parmi ses chemins détaillés exportés ;
aucune marge Pro Dock n'est inventée. L'identité fonctionnelle du cône n'implique
pas une identité de délai.

## vid_hclk et vid_hrstn : définition retrouvée

`video_reset_clock_bindings.json` vérifie les connexions exactes dans les deux
`.vo` Pro Dock et Neo :

```
PLL AE350 CLKOUT0 -> vid_hclk -> AHB_CLK du hard CPU
HRESETN du hard CPU -> u_soc/exts_hrstn
                  -> DFFCE (CLK=vid_hclk, CE=VCC, CLEAR=GND, INIT0)
                  -> vid_hrstn
```

Le RTL correspondant est `ae350_soc.v:331–332,369`; le wrapper généré assigne
`EXTS_HCLK = AHB_CLK` à la ligne 945. Cette provenance est la même sur les deux
cartes. Les entrées POR/HW et les délais physiques du hard CPU ne deviennent
pas pour autant identiques. La source du reset vidéo était omise dans le premier
extrait envoyé aux modèles, elle n'est pas absente du design.

## Autres corrections à l'avis Fable

- `MIN_LOCK_CYCLES` vaut 104000, soit 2,08 ms à 50 MHz, dans
  `neo_reset_trial.v:6`. Aucun override dans l'instance top. La durée normale
  reste 2 500 000 cycles, soit 50 ms.
- Des lectures CPU réussies ne prouvent pas l'absence de toute impulsion reset
  pendant 1,6 s ; aucune capture continue de HRESETN n'a été faite.
- Une injection de pulse peut être simulée en RTL ; ce sont la production
  analogique du glitch, sa capture physique et la métastabilité qui ne sont
  pas prouvées par un tel banc.
- Une écriture/relecture shadow est un témoin utile, mais lecture nulle ne
  démontre pas à elle seule `vid_hrstn` bas : le transport AHB, le décodage,
  le registre ou son retour peuvent aussi échouer. Relecture exacte ne prouve
  pas la réception correcte du reset dans tous les récepteurs pixel.
- R19/L31r8 ne réfutent pas toutes les incompatibilités conditionnelles ;
  ils réfutent une panne universelle de tout design C/PG484.
- Le classement des causes proposé par Fable reste spéculatif. Aucun PnR,
  essai matériel ou correctif partagé n'a été lancé par cette analyse.

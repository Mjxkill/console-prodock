# Diagnostic AE350 — Pro Dock FPG676, 27 septembre 2026

Symptômes rapportés : chargement réussi, aucun texte UART, programme LED sans effet.
La programmation FPGA seule ne prouve pas l'exécution du firmware.

## Horloge du cœur

Le cœur reste à **800 MHz**. Le manuel Gowin MUG1030-1.3E, §2.6.3–2.6.4,
pages imprimées 9–10, impose la liaison dédiée **PLL_R[0] / CLKOUT1**.
Source : https://cdn.gowinsemi.com.cn/MUG1030E.pdf

Avant correction, `constr/ae350_e2.cst` plaçait la PLL AE350 en R[2] et
`u_pll_f` (USB) en R[0]. Or `rtl/usb/gowin_pll_f.v` désactive CLKOUT1.
Cette configuration ne fournit donc pas l'horloge dédiée attendue par le cœur.
Correction : AE350 en R[0], USB F en R[2], USB B conservée en R[1].

Dans `ref_demo/ae350_customized_demo.cst`, la contrainte AE350 était commentée
et son ancien chemin ne correspondait pas au wrapper actuel. Elle est activée
avec le chemin `u_Gowin_PLL_AE350/u_pll/PLL_inst`.

## Comparaison avec le projet indiqué par Michael

Référence lue sans modification : `/home/michael/gowin/Analyzer_project`.
Sa PLL configure un VCO à 800 MHz, CORE_DIV=1 (800 MHz), AHB/APB divisés
par 10 (80 MHz). Le test LED reprend ces fréquences, en conservant le
brochage Pro Dock FPG676. Le `.gprj` et le rapport présents dans la référence
locale ciblent PG484 : leurs broches ne sont pas recopiées.

La référence utilise un démarrage SPI flash et une DDR intégrée. Le test LED
local utilise l'ITCM préinitialisée et une DDR externe à l'IP SoC : ce n'est
pas une reproduction complète de la référence.

## Test LED

`fw_console/demo/demo_led.S` écrit dans les registres GPIO corrects :
CHANNELDIR=0xF0700028, DOUTCLEAR=0xF070002C, DOUTSET=0xF0700030.
L'image ITCM commence par le saut vers ce programme. SHA-256 des quatre
fichiers ITCM entrelacés en octets little-endian :
`0db7f9d1465b3beba79e18628e68ea9cf386cbc94fef9d259ab45c8610984ba3`.

Dans **refdemo**, GPIO[2:0] rejoint les trois LED R26, L20, M25. Dans
**console_e2**, `.GPIO()` est déconnecté ; les LED sont pilotées par la logique
de diagnostic FPGA. Un programme GPIO ne peut donc pas les commander dans E2.

Le compteur de diagnostic en fabric cadencé à 800 MHz a été retiré : son
Fmax d'environ 464 MHz ne représentait **pas** une limite du cœur dur AE350.
`TEST_LOCK` montre maintenant le véritable verrouillage de PLL. Les compteurs
AHB/APB restent à 80 MHz. Le test intermédiaire à 200 MHz a été écarté à la
demande de Michael ; ses artefacts sont dans `discarded_200mhz_not_for_board`.

## Défauts UART distincts, non corrigés dans ce diagnostic de démarrage

- Le pont `rtl/ae350/uart2_to_ep2.v` utilise 32 cycles/bit à 60 MHz,
  soit 1,875 Mbaud. Simulation Verilator : un `A` envoyé à 115200 bauds
  produit trois octets 00. Le temporisateur de début de trame est aussi erroné.
- La configuration ITCM E2 pointe sur `logic_analyser_wifi/ae350/e1_itcm`,
  dont le pilote UART suppose APB=80 MHz, alors qu'E2 fournit 100 MHz.
  La configuration et le firmware doivent être rendus cohérents et l'IP
  régénérée avant de valider la console.

## Validation

Les builds sont isolés sous `tang/impl/diag_pllr0/` ; les anciens bitstreams
`tang/impl/pnr/console_e2.fs` et `refdemo.fs` n'ont pas été remplacés.

- `refdemo/` : correction de placement seule ; bitstream généré, violations
  persistantes sur le compteur fabric 800 MHz et l'ITCM à 100 MHz.
- `e2/` : correction de placement seule, cœur 800 MHz ; bitstream généré,
  TNS interne par horloge nul. Le pont UART et les traversées de domaines
  restent à traiter ; cela ne valide pas le fonctionnement de la console.
- `refdemo_800/` : cœur **800 MHz**, bus **80 MHz**, compteur fabric 800 MHz
  retiré ; synthèse et P&R terminés, aucune erreur de build, TNS setup/hold nul
  pour toutes les horloges. Les 110 marges de chemins détaillées dans le rapport
  sont non négatives (minimum : 0,140 ns). Fmax AHB/ITCM : 101,326 MHz pour
  80 MHz demandés. Le cœur dur n'a pas de chemin fabric à analyser ; sa PLL
  est bien rapportée à 800 MHz, période 1,250 ns.

Bitstream à essayer :
`tang/impl/diag_pllr0/refdemo_800/impl/pnr/refdemo_led_800.fs`.
Le même dossier contient le `.bin`, le `.tr` et le `.rpt.txt`.
Ce test utilise le programme LED ITCM, pas la console UART E2.

## Chargement carte — 27 septembre 2026, 21:58 CEST

À la demande de Michael, `refdemo_led_800.fs` a été chargé en **SRAM** avec
openFPGALoader v1.1.1. Pro Dock identifiée par la série USB **2023112818**,
adresse USB **3:12** relue au moment du test ; JTAG : **0x1081b, GW5AST-138**.
La Tang Console série 2025041420 n'a pas été programmée.

Commande : `openFPGALoader --busdev-num 3:12 -b tangmega138k -m .../refdemo_led_800.fs`.
Résultat : progression 100 %, **Done / DONE**, code de retour **0**.
Journal : `tang/impl/diag_pllr0/refdemo_800/load.log`.
SHA-256 : `6bcff36be5b2389742916f6fef5172ef0d3d8dd627469ecad44553aa51005b7c`.

Le chargement est confirmé. **Michael confirme que les LED alternent**, mais
signale un défilement très lent : l'exécution du programme par le CPU est donc
confirmée sur carte avec cette configuration à 800 MHz.

## Ajustement de la temporisation LED

Le programme faisait 100 000 000 itérations entre transitions. Le commentaire
annonçant 0,25 s ignorait le coût des accès aux instructions et des branches.
Il ne s'agissait pas d'une temporisation mesurée.

`LED_DELAY_ITERATIONS` vaut maintenant 5 000 000 : attente 20 fois plus courte,
cœur conservé à 800 MHz, AHB/APB à 80 MHz. Vérification du binaire : seules
les trois constantes d'attente changent ; les quatre fichiers ITCM recomposent
exactement le nouveau binaire de 96 octets. L'IP AE350 est régénérée pour
incorporer la nouvelle image. Le build est isolé sous `refdemo_800_fast/`.
Le bitstream qui a déjà fonctionné est conservé sous `refdemo_800/`.

Validation de `refdemo_led_800_fast.fs` : build terminé sans erreur, horloge
cœur rapportée à 800 MHz, 18 entrées TNS setup/hold à zéro, 110 chemins
détaillés sans marge négative (minimum 0,140 ns). Rechargement SRAM sur la
Pro Dock série 2023112818, USB 3:12, identité revérifiée : **100 %, Done / DONE,
code retour 0**. Journal : `refdemo_800_fast/load.log` ; empreintes :
`refdemo_800_fast/sha256.json`.

**VALIDÉ SUR CARTE par Michael : « c'est bon ça marche ! »** Le test LED et
sa cadence corrigée fonctionnent avec le cœur AE350 à **800 MHz** et les bus
AHB/APB à **80 MHz**. Bitstream validé :
`tang/impl/diag_pllr0/refdemo_800_fast/impl/pnr/refdemo_led_800_fast.fs`.
Cette validation concerne le test LED ; la console UART E2 reste à corriger
et à tester séparément.

Suite de session : **console UART E2 corrigée et validée sur carte**, voir
`TESTS_E2.md` : cœur 800 MHz, bus 80 MHz, écho exact de 5441 octets via USB CDC.

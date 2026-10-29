from pathlib import Path
import json,hashlib
R=Path('/home/michael/console');D=R/'TESTS/neo_720p_20261012/capture_memory_20261027';B=R/'tang/impl/console_neo_n56r21r1_capture_memory'
text=['Diagnostic Neo GW5AST138C PG484. Question urgente: pourquoi R21r1 observation-only ne démarre pas alors que R19 redémarre immédiatement, même100kHzJTAG? Pas de nouveauPnR ni codeRTL autorisé. Séparer faits/hypothèses. Proposer un signal observable existant et test discriminant précis sans recompiler. Ne pas conclure erratum.',
'''Faits: R19 logique fonctionnelle identique à R21r1,143366primitives parent horshelper conservées. R21 ajoute8FF+8LUThelper,4LUT COPY états etINV pixelvalid; aucuneentrée fonctionnelle modifiée. L'ensemble est rerouté, aucunplacementfonctionnelpréservé. Timing R19 setup−2.888/hold+.124/recovery−.239/removal+.274. R21 setup−2.602/hold+.124/recovery+.381/removal+.168; localobservercaptureborne+.334. App globale FAIL conservée. AucunLinux/SD/flashécrit. CortexAE350 RV32 cœur800MHz,bus80MHz,DDR300MHzUI75MHz.
MATÉRIEL1: R19 CPUparking/cache0 lu à1MHz. R21 programmé SRAM DONE sanserreur maispasderelecturecomplète; TAP1000563d correct, DMInecomplètepas. RetourR19 DONE, IDCODEmalaligné à1MHz, mais100kHzsansreload donneimmédiatementPC80000004+GPUfrais+mire.
MATÉRIEL2: R19 baselinePASS100kHz; mêmeR21programmé; photoAVANTDMI écranHDMInoir, paslesbandesR19; TAP1000563d correctà100kHz maisDMIinachevé timeout30s. MêmeR19 restauré, mêmeTcl100kHz redonnePC80000004+GPUfrais. A/B/A à100kHz. Doncproblème1MHzfallbackexiste séparément, ne suffitplusàexpliquerR21.
R19/R21 n'intègrentaucunGAO (0primitives). Fichiersgao présentsdanssourceshistoriquesseulement. SOFT-USB359f2011 n'étaitpasénuméré auxessaisprécédents, pasprésumerEP0accessible. LED_n=~ddr_init, brocheV13. PhotoLEDs nonidentifiéesneprouvepasddr_init. ROOTpossèdeexclusivementmatériel, pasvous.
Différenceclockglobal: huitPRIMARYidentiques, seulesrégionspixel_clk PBR2,PBR3→PBR0..3. R19 LW:usb_app_reset,v1_pending,rtc_clk,n59467_5(materialface),COPYCE n7630_6,triangle state0[4],DDRip ddr_rst. R21 LW: mêmes sauftriangle supprimé et u_gpu/prst[1] AJOUTÉ. UnepromotiondecontrôleLW a déjàcorrigéplusieurscaptures maispaspreuveerratumgénéral. prst[1] touche scanout pixel; aucunlienretour CPU identifié.''']
comp=json.loads((D/'cpu_route_compare_01/result.json').read_text())
text+=['ComparaisonSDF exactedesarcs (min/nom/max ns); CORE0:0:0 fournisparvendorpasmesure. Cellules/INIT/PLL/resettrialexactementidentiques.']
for x in comp['comparison']:
 if not x['before'] or not x['after']:continue
 text.append(x['endpoint']+' R19 '+str(x['before'])+' R21 '+str(x['after']))
text+=['STAnegativeCPU/reset/PLL ciblé: R19 '+str(comp['before']['negative_sta_rows'])+' R21 '+str(comp['after']['negative_sta_rows'])]
paths=[('source/tang/boards/neo/console_neo.v',[(120,178),(201,206)]),('source/tang/rtl/board/ae350_soc.v',[(129,157),(329,332),(359,380)]),('source/tang/boards/neo/neo_reset_trial.v',[(1,110)]),('source/tang/rtl/video/gpu_scanout.v',[(30,42),(237,258),(515,545)]),('source/tang/boards/neo/soft_usb.vh',[(303,336)])]
for name,sections in paths:
 p=B/name;s=p.read_text().splitlines();text.append('SOURCE '+str(p.relative_to(R))+' SHA256 '+hashlib.sha256(p.read_bytes()).hexdigest())
 for lo,hi in sections:text+=['\n'.join(f'{i}: {s[i-1]}' for i in range(lo,min(hi,len(s))+1))]
for n in ['startup_100k_20261027_090320/baseline_r19.log','startup_100k_20261027_090320/r21_read100k.log','startup_100k_20261027_090320/fallback_read100k.log']:
 p=D/n;text+=['LOG '+str(p.relative_to(R))+' SHA256 '+hashlib.sha256(p.read_bytes()).hexdigest(),p.read_text()]
for n in ['startup_100k_20261027_090320/result.json','cpu_route_compare_01/result.json','postroute_01/result.json']:
 p=D/n;text+=['PROOF '+str(p.relative_to(R))+' SHA256 '+hashlib.sha256(p.read_bytes()).hexdigest()]
out=R/'TESTS/assisted_reviews_20261026/r21_startup_packet.txt';out.write_text('\n\n'.join(text));print(out,len(out.read_bytes()))

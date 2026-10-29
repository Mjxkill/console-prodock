from pathlib import Path
import hashlib,json,re
ROOT=Path('/home/michael/console'); HERE=Path(__file__).resolve().parent; OUT=ROOT/'TESTS/assisted_reviews_20261026/neo_clock_reset_packet_r1.txt'
R21=Path('tang/impl/console_neo_n56r21r1_capture_memory'); R19=Path('tang/impl/console_neo_n56r19_capture_ce_local'); G22=Path('tang/impl/gpu_geometry_g22r0')
manifest=[]; chunks=[]
def add(path,ranges=None,pattern=None):
 p=ROOT/path; b=p.read_bytes(); lines=b.decode(errors='replace').splitlines(); selected=[(i,s) for i,s in enumerate(lines,1) if (not ranges or any(a<=i<=z for a,z in ranges)) and (not pattern or re.search(pattern,s))];
 manifest.append(dict(path=str(path),sha256=hashlib.sha256(b).hexdigest(),ranges=ranges,pattern=pattern)); chunks.append('\nSOURCE '+str(path)+' SHA256 '+manifest[-1]['sha256']+'\n'+''.join(f'{i}: {s}\n' for i,s in selected))
def obj(path,keys):
 p=ROOT/path; b=p.read_bytes(); d=json.loads(b); manifest.append(dict(path=str(path),sha256=hashlib.sha256(b).hexdigest(),keys=keys)); chunks.append('\nJSON EXCERPT '+str(path)+' SHA256 '+manifest[-1]['sha256']+'\n'+json.dumps({k:d.get(k) for k in keys},indent=2)+'\n')
chunks.append('''AUDIT INDEPENDANT R19 / R21r1 : couverture clocks/reset/initialisation, aucune action matérielle.
Question utilisateur ingénieur FPGA : RTL identique hors observateur + mêmes contraintes devraient assurer un comportement stable après timing. L'ajout diagnostic révèle-t-il une contrainte manquante/erronée ?
IMPORTANT : global STA n'est PAS PASS. R19 démarre mais GPU CLEAR stalle et COPY est rejeté. R21r1 ajoute observation uniquement et échoue au démarrage (écran noir avant toute requête DMI, TAP AE350 correct mais DMI timeout). A/B/A à100k : R19 fonctionne, R21 échoue, R19 fonctionne immédiatement. Pas preuve causale d'un reset ou LW. Aucune conclusion hardCPU entièrement non modélisé sans regarder les arcs fournis. 0 endpoints dans table TNS = zéro VIOLATION, pas zéro endpoints évalués !
R19 et R21 : CST et SDC octet identiques; options build identiques après seules substitutions chemins. Toutes cellules fonctionnelles/ports/paramètres INIT préservés; nouvel observateur remplace contenu capture NCP, handshake/registre/bus inchangés. Ancien helper C1 devient D* : D/Q8 largeurCOPY, CE/reset/start et états, quatre sticky issue/valid/pending/accepted. Ajout4LUT+INV horshelper et+8DFFCE/+8LUT3 danshelper; charges et routage changent. SDC et contraintes de reset ne changent pas. prst[1] du scanout devientLW surR21, effet causal non démontré.
ProDock G22r0 fonctionnelle cible GW5AST-138B / GW5AST-LV138FPG676AC1/I0; Neo R19/R21 cible GW5AST-138C / GW5AST-LV138PG484AC1/I0. Ne pas déduire une révision silicon/erratum de B/C sans document fabricant. MêmeDDR ne garantit pas mêmeinterface/routage. ProDock références protégées.
EssaiUARTmode1 : surR19 témoinNCP2/2 avant, reste2/2 aprèsouvertureUART, devient0/0 aprèstrameavantfermeture; réception reset prouvée R19. SurR21 write8 acceptéPC maisout_waiting ne se videpas2s; réception FPGA inconnue, ce n'est PAS une preuve warmreset inefficace. R19restauré.
Revue demandée : faits précis chemins/lignes, contraintes réellement manquantes vs absence de preuve ou modèle incomplet; erreursRTL/initCDC plausibles et réfutables; trois contrôles horscarte avant toutnouveauPnR. Aucun patchapplication nihardware autorisé. Les extraits sont sélectionnés, aucune conclusion sur des lignes absentes sans demander preuve.
''')
for b in [G22,R19,R21]: add(b/'build.tcl',[(1,12)])
base=R21/'source'
add(base/'tang/boards/neo/neo.sdc')
add(base/'tang/boards/neo/neo.cst',pattern=r'CLOCK|ae350|clk|led|uart')
add(base/'tang/boards/neo/console_neo.v',[(95,220),(1220,1280)])
add(base/'tang/rtl/board/ae350_soc.v',[(1,38),(120,205),(335,385)])
add(base/'tang/boards/neo/neo_reset_trial.v')
add(base/'tang/rtl/board/pll_init.v')
add(base/'tang/rtl/ae350/pll_ae350/gowin_pll_ae350.v')
add(base/'tang/rtl/ae350/pll_ae350/gowin_pll_ae350_mod.v',[(1,130),(155,210)])
add(base/'tang/rtl/board/riscv_ae350_soc_ext/riscv_ae350_soc.v',pattern=r'AE350_SOC|POR|RST|CLK|DBG_TCK|EMAW|EMAS|EMA\(')
for b in [R19,R21]:
 add(b/'impl/pnr/console_neo.tr',[(1,140)])
 add(b/'impl/pnr/console_neo.rpt.txt',pattern=r'prst\[1\]|ae350|reset_trial|Clock|LW|PG\[')
# Include precise hard macro timing checks, not all interface data arcs.
sdf=R21/'impl/pnr/console_neo.sdf'; lines=(ROOT/sdf).read_text().splitlines(); start=next(i for i,x in enumerate(lines) if '(CELLTYPE "AE350_SOC")' in x); end=next(i for i in range(start+1,len(lines)) if '(CELLTYPE ' in lines[i]);
add(sdf,[(start+1,start+3)])
add(sdf,[(start+1,end)],pattern=r'POR_N|HW_RSTN|DBG_TCK|CORE_CLK|RTC_CLK|RECOVERY|REMOVAL|WIDTH|PERIOD')
add(sdf,pattern=r'INTERCONNECT .* (u_soc.*u_AE350_SOC/(CORE_CLK|AHB_CLK|APB_CLK|RTC_CLK|POR_N|HW_RSTN|DBG_TCK)|u_soc.*init_sync_[01]_s0/CLEAR) ')
cap=Path('TESTS/neo_720p_20261012/capture_memory_20261027')
obj(cap/'cpu_route_compare_01/result.json',['logic_equal','parameters_equal','comparison','limits'])
obj(cap/'postroute_01/result.json',['qualification_status','gates','timing','timing_summary'])
obj(cap/'root_review_01.json',['status','constraints_equal','pnr_settings_only_path_changed','application_cells_intact','helper_clock_reset_identical'])
obj(cap/'startup_100k_20261027_090320/result.json',['status','outcome','last_programmed_sha','baseline','r21','fallback'])
packet='\n'.join(chunks); OUT.write_text(packet); assert OUT.stat().st_size<200000,OUT.stat().st_size
result=dict(packet=str(OUT.relative_to(ROOT)),packet_sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(),bytes=OUT.stat().st_size,sources=manifest,hardware_access=False,independent_review=True)
(HERE/'packet_manifest.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps({k:v for k,v in result.items() if k!='sources'},indent=2))

from pathlib import Path
import hashlib,json
R=Path('/home/michael/console'); C=R/'TESTS/neo_720p_20261012/capture_memory_20261027/reset_contract_01'; P=R/'TESTS/assisted_reviews_20261026/neo_por_contract_packet_r1.txt'; entries=[]; chunks=['''Revue ciblée du contrat POR/HW et de LOCK, sans outil, compilation, RTLmodifié, carte ni nouveau routage.
But : distinguer minimum fabricant, exemple et propriétéRTLréellement prouvée. Aucune causematérielleR21 encore établie. R19etR21 mêmechaînereset, R21nebootepas maisR19oui ; une faiblesse commune ne prouvepascause de différence.
Question réfutable : UG306-1.0.9E p40 demande LOCK observé continûment2ms. Neo attend50ms enéchantillonnantreadyàclk50; son ae350_rst_sync captureperteLOCKasync. UnLOCKbas brefentrefrontsclk50 peut-il laisserdelay_done=1etpermettrePOR/HW à1quelquescyclesAHBaprèsretourLOCK? Donner une tracefrontsparfronts dérivée duRTL FOURNI, ycompris ordreNBA, etconditions qui réfuteraientcetexemple. Ne pasprésenter cette tracepapiercomme simulationexécutée, niun minimumduréeglitchnonfourni parfabricant.
Autrespoints : référencelocaleSipeedkey_debounce20ms estbiencâbléDDRready→ae350_rstn ; ce n'estpasminimumPORdocumenté. L31r8console138k_reset qualifieLOCK2.08ms, MAIS ae350_socinit_sync estclk50etignore rst_key_n : attentionànepasattribuerlaqualifauCPUdirectement. ProDockutiliseDDRready2FFAHBaprèsPLLlock2FFsans50ms. RTC10MHz estdirect sansdiviseur visibleentrePLL etmacro, malgréMUG1031tableRTC32.768KHz ; n'inventerpasunprescaler.
Conclusionattendue<=1500mots,faitsconditionsnonétabliesetUNEobservationdiscriminantefuture. Aucunpatchautorisés.
''']
def add(p,rs):
 p=Path(p);b=p.read_bytes();ls=b.decode(errors='replace').splitlines();e=dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),ranges=rs);entries.append(e);chunks.append('\nSOURCE '+str(p)+' SHA256 '+e['sha256']+'\n'+''.join(f'{i}: {line}\n'for i,line in enumerate(ls,1)if any(a<=i<=z for a,z in rs)))
N=R/'tang/impl/console_neo_n56r21r1_capture_memory/source';G=R/'tang/impl/gpu_geometry_g22r0/source';A=Path('/home/michael/logic_analyser_wifi/tang/impl/linux_l31r8_local_20261012/workspace/tang/rtl');S=Path('/home/michael/gowin/ref/TangMega-138KPro-example/ae350_customized_demo/src')
add(N/'tang/boards/neo/neo_reset_trial.v',[(1,110)]);add(N/'tang/boards/neo/console_neo.v',[(130,190)]);add(N/'tang/rtl/board/ae350_soc.v',[(140,158),(375,382)])
add(G/'tang/rtl/console_top.v',[(503,530)]);add(G/'tang/rtl/board/ae350_soc.v',[(148,157),(373,381)])
add(A/'board/console138k_clk.v',[(1,100)]);add(A/'board/ae350_soc.v',[(128,146),(365,374)]);add(A/'la_top_sd_boot.v',[(20,29)])
add(S/'key_debounce.v',[(1,80)]);add(S/'ae350_customized_demo.v',[(58,117),(210,220)])
add(C/'UG306_109E.txt',[(2028,2051)])
add(C.parent/'vendor_docs/MUG1031-1.3.1E.txt',[(615,630),(709,725),(766,782),(1829,1838)])
add(N/'tang/rtl/board/pll_init.v',[(19,46),(126,221)]);add(N/'tang/rtl/ae350/pll_ae350/gowin_pll_ae350.v',[(34,70)])
P.write_text('\n'.join(chunks));assert P.stat().st_size<200000;d=dict(packet=str(P.relative_to(R)),packet_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),bytes=P.stat().st_size,sources=entries,hardware_access=False,compiled=False);(C/'packet_manifest.json').write_text(json.dumps(d,indent=2)+'\n');print(d['packet_sha256'],d['bytes'])

#!/usr/bin/env python3
"""Prepare PP2: same frozen game and staged references, two exact useful ranges."""
import argparse,hashlib,json,shutil,subprocess,zlib
from pathlib import Path
C=Path(__file__).resolve().parent;R=C.parents[3]
P=R/'games/luma3d/tests/hardware/polish_20261026_pp1_prepared_r2'
RESULT=R/'games/luma3d/tests/hardware/polish_20261026_pp1_result/result.json'
B=R/'games/luma3d/build/arcade_polish_20261026_r6'
def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
 assert digest(P/'manifest.json')['sha256']=='53c138b62fa96334389df536bdb728e45b6664eac0bf47a0068355ef00ba327b'
 m=json.loads((P/'manifest.json').read_text());r=json.loads(RESULT.read_text())
 assert not r['passed'] and r['restored_sc1'] and [f['name'] for f in r['fixtures']]==['entry_0','entry_1','entry_2','entry_3','entry_4','crystal']
 assert r['game']==m['game'] and 'pp1_boss_memory_1' in r['error'] and r['recovery']['identity']==dict(pid=2376,start_ticks=21307354)
 for name,d in m['files'].items():assert digest(P/name)==d;shutil.copy2(P/name,o/name)
 shutil.copy2(RESULT,o/'prior_result.json');shutil.copy2(P/'manifest.json',o/'prior_manifest.json')
 code=(P/'runtime_inspect.c').read_text()
 code=code.replace('if(argc<2)return 2;int is_patch=', 'if(argc<2)return 2;int is_slice=!strcmp(argv[1],"memory-slice");int is_patch=')
 code=code.replace('if(argc!=(is_patch?7:6)||','if(argc!=(is_patch?7:is_slice?8:6)||')
 code=code.replace('&&strcmp(argv[1],"memory")&&!is_patch)', '&&strcmp(argv[1],"memory")&&!is_slice&&!is_patch)')
 needle=' int rc=1;'
 block=''' if(is_slice) {
  unsigned skip,count;
  if(!number(argv[6],0,&skip)||!number(argv[7],0,&count)||!count||(skip&3)||(count&3)||skip>bytes||count>bytes-skip){free(data);return 2;}
  memmove(data,data+skip,count);bytes=count;sum=crc(data,bytes);
 }
'''
 assert code.count(needle)==1;code=code.replace(needle,block+needle)
 code=code.replace('else if(!strcmp(argv[1],"memory")) {','else if(!strcmp(argv[1],"memory")||is_slice) {')
 (o/'runtime_inspect.c').write_text(code)
 for target,cc,flags in [('helper-host','cc',[]),('pp2-helper',R/'linux/build/userbin/riscv32-prodock-linux-gcc',['-static'])]:
  cmd=[cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*flags,'-I'+str(o),o/'runtime_inspect.c','-o',o/target]
  with (o/(target+'.compile.log')).open('w') as f:subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,check=True)
 controller=(P/'prodock_polish.py').read_text();controller=controller[:controller.index('def main():')]+(C/'resume_main.py.txt').read_text()
 controller=controller.replace("m['program']=='luma3d-'+m['tag'] and m['probe']==m['tag']+'-probe'", "m['program']=='luma3d-pp1' and m['probe']=='pp1-probe'")
 controller=controller.replace("assert m['transfer_files']==[m['helper'],m['delta']['file'],m['probe_delta']['file'],*[r['file'] for r in references]]", "assert m['transfer_files']==[m['helper']]")
 needle=' return m\n\ndef tour_result'
 replacement=''' assert sha(bundle/'prior_result.json')==m['resume_result_sha256']
 prior=json.loads((bundle/'prior_result.json').read_text())
 assert not prior['passed'] and prior['restored_sc1'] and prior['game']==m['game']
 assert prior['recovery']['identity']==m['expected_identity']==dict(pid=2376,start_ticks=21307354)
 assert [f['name'] for f in prior['fixtures']]==['entry_0','entry_1','entry_2','entry_3','entry_4','crystal']
 assert [(q['gpu_offset'],q['source_offset'],q['bytes']) for q in m['publication_ranges']]==[(28<<20,0,835584),(31<<20,3<<20,961152)]
 publication=json.loads((bundle/'publication_validation.json').read_text())
 assert publication['passed'] and not publication['hardware'] and publication['game_sha256']==m['game']['sha256']
 assert len(publication['records'])==2 and all(x['passed'] for x in publication['records'])
 for expected,actual in zip(m['publication_ranges'],publication['records'][0]['ranges']):
  assert expected['gpu_offset']==actual['offset'] and all(expected[k]==actual[k] for k in ('bytes','sha256','crc32'))
 return m

def tour_result'''
 assert controller.count(needle)==1;controller=controller.replace(needle,replacement);(o/'prodock_polish.py').write_text(controller)
 m.update(tag='pp2',helper='pp2-helper',transfer_files=['pp2-helper'],expected_identity=r['recovery']['identity'],resume_result_sha256=digest(RESULT)['sha256'])
 memory=(B/'captures/boss.memory').read_bytes();m['publication_ranges']=[]
 for start,n in [(28<<20,835584),(31<<20,961152)]:
  b=memory[start:start+n];m['publication_ranges'].append(dict(gpu_offset=start,source_offset=start-(28<<20),bytes=n,sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}'))
 shutil.copy2(C/'prepare_resume.py',o/'prepare_resume.py');shutil.copy2(C/'resume_main.py.txt',o/'resume_main.py.txt');shutil.copy2(C/'test_resume.py',o/'test_resume.py')
 shutil.copy2(C/'tests/shooter_publication.c',o/'shooter_publication.c')
 shutil.copy2(C/'validate_publication.py',o/'validate_publication.py')
 shutil.copy2(C/'publication_20261027_r1/result.json',o/'publication_validation.json')
 for name in ('boss.log','boss_720.log'):shutil.copy2(C/'publication_20261027_r1'/name,o/('publication_'+name))
 (o/'PLAN_REPRISE.txt').write_text('''PP2 — reprise après erreur de périmètre de comparaison PP1.
Même ELF R6 d8f65131…c0a48 et même probe2982fd…e19bc, aucun changement de jeu.
SC1 attendu PID2376/startticks21307354 ; identité/argv et progrès contrôlés sous verrou.
Transfert RAM du seul helper de lecture avec sélection bornée de référence. Aucune écriture GPU du helper.
Vérifier CRC de SC1, image du processus, ELF/probe PP1 déjà installés et références nécessaires avant arrêt.
Les six fixtures déjà réussies et première image restent liées au résultat PP1, jamais réécrites.
Rejouer boss : UI entière et deux allocations exactes835584+961152octets, chacune comparée sans tolérance.
Rejouer checkpoint3D :96000pixels et UI exacte. Puis vrai --showcase-once, délai3700s, silenceUART.
Le plein4MiB échouait parce qu'il inclut2397568octets non publiés ; aucune couche/sprite ne les lit.
La preuve locale appelle le vrai publisher figé avec une mémoire A5, compare toutes écritures et vérifie tous défilements/entréesatlas,800 et720p.
Un résultat matériel exact des deux allocations reste requis : les données utiles ne sont pas présumées PASS après PP1.
Sauvegarde V4 /tmp/op2-live.save inchangée. Aucun --save dans essai/repli. Aucun FPGA/noyau/SD/flash.
En échec repli SC1 idempotent avec identité finale/progrès ; en succès boucle R6 autonome /dev/null.
La fluidité reste à juger par activité/p95/p99/max ; succès fonctionnel ne vaut pas fluidité satisfaisante.
Autorisation utilisateur existante ; revue parent du paquet concret avant exécution.
''')
 m['files']={p.name:digest(p) for p in sorted(o.iterdir()) if p.is_file()};m['transport_bytes']=m['files']['pp2-helper']['bytes'];(o/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 print(json.dumps(dict(manifest=digest(o/'manifest.json'),controller=digest(o/'prodock_polish.py'),transport_bytes=m['transport_bytes']),indent=2))
if __name__=='__main__':main()

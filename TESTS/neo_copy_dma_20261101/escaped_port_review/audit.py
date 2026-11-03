#!/usr/bin/env python3
"""Independent read-only connectivity audit of frozen Gowin mapped netlists.

No imports from previous prepare/mapping/inventory code. Lexer implements the
Verilog escaped identifier rule: every non-whitespace character following '\\'
belongs to that identifier, including commas/parentheses. Whitespace is its
terminator, never blindly removed. This audits generated module headers and
named-port instances, not arbitrary behavioral Verilog or analog behavior.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
ID=r'(?:\\[^\s]+|[A-Za-z_$][A-Za-z0-9_$]*)'
TOKEN=re.compile(r'(?P<space>\s+)|(?P<comment>//[^\n]*|/\*.*?\*/)|'
                 r'(?P<string>"(?:\\.|[^"\\])*")|(?P<escape>\\[^\s]+)|'
                 r'(?P<id>[A-Za-z_$][A-Za-z0-9_$]*)|(?P<number>[0-9][A-Za-z0-9_\x27?]*)|(?P<other>.)',re.S)
START=re.compile(r'^[ \t]*(?P<kind>'+ID+r')[ \t\r\n]+(?P<name>'+ID+r')\s*\(',re.M)
MOD=re.compile(r'^module\s+([A-Za-z_$][A-Za-z0-9_$]*)\b.*?^endmodule\b',re.M|re.S)
DIAGNOSTICS={'neo_capture_local','neo_capture_bus','neo_copy_snapshot','neo_copy_snapshot_readout','neo_copy_dma_observe','neo_copy_dma_taps'}

def tokens(text,start=0):
    for m in TOKEN.finditer(text,start):
        if m.lastgroup not in ('space','comment'):
            if m.lastgroup=='escape' and m.end()==len(text):
                raise ValueError('Escaped identifier has no terminating whitespace')
            yield m.group(),m.start(),m.end()

def identifier(word):return bool(re.fullmatch(ID,word))

def body_until_close(text,start):
    depth=1;out=[];it=tokens(text,start)
    for v,a,b in it:
        if v=='(':depth+=1
        elif v==')':
            depth-=1
            if depth==0:
                semi=next(it,None)
                if semi is None or semi[0]!=';':raise ValueError('Instance/header lacks semicolon')
                return out,semi[2]
        out.append((v,a,b))
    raise ValueError('Unclosed instance/header')

def header(text):
    first=START.match(text)
    if first is None or first['kind']!='module':raise ValueError('Unsupported mapped module declaration')
    ts,end=body_until_close(text,first.end());names=[];expect_name=True
    for v,a,b in ts:
        if expect_name:
            if not identifier(v):raise ValueError('Expected header port, got '+repr(v))
            names.append(v)
        elif v!=',':raise ValueError('Expected comma after '+repr(names[-1])+', got '+repr(v))
        expect_name=not expect_name
    if ts and expect_name:raise ValueError('Trailing comma in header')
    if len(names)!=len(set(names)):raise ValueError('Duplicate module port')
    return names,text[:end]

def ports(ts):
    """Consume the entire body; reject rather than skip unsupported syntax."""
    out={};i=0
    while i<len(ts):
        if ts[i][0]!='.':raise ValueError('Expected named port, got '+repr(ts[i][0]))
        if i+2>=len(ts) or not identifier(ts[i+1][0]) or ts[i+2][0]!='(':
            raise ValueError('Malformed named connection near '+repr(ts[i:i+3]))
        name=ts[i+1][0];i+=3;depth=1;expr=[]
        while i<len(ts):
            value=ts[i][0];i+=1
            if value=='(':depth+=1
            elif value==')':
                depth-=1
                if depth==0:break
            expr.append(value)
        if depth:raise ValueError('Unclosed expression for '+name)
        if name in out:raise ValueError('Duplicate port '+name)
        out[name]=tuple(expr)
        if i<len(ts):
            if ts[i][0]!=',':raise ValueError('Missing connection comma')
            i+=1
            if i==len(ts):raise ValueError('Trailing connection comma')
    return out

def instances(text):
    result={}
    for m in START.finditer(text):
        if m['kind']=='module':continue
        ts,end=body_until_close(text,m.end());ps=ports(ts)
        if m['name'] in result:raise ValueError('Duplicate instance '+m['name'])
        result[m['name']]={'kind':m['kind'],'ports':ps,
                          'raw':text[m.start():end], 'line':text.count('\n',0,m.start())+1}
    return result

def statements(text,keyword):
    """Tokenize complete generated declarations/assignments, escaped-aware."""
    out=[]
    for m in re.finditer(r'^[ \t]*'+keyword+r'\b',text,re.M):
        row=[]
        for v,a,b in tokens(text,m.start()):
            if v==';':break
            row.append(v)
        else:raise ValueError('Unterminated '+keyword)
        out.append(tuple(row))
    return out

def declarations(text):
    out={}
    for row in statements(text,r'(?:input|output|inout)'):
        if not identifier(row[-1]) or ',' in row:raise ValueError('Unsupported mapped port declaration '+repr(row))
        if row[-1] in out:raise ValueError('Duplicate port declaration')
        out[row[-1]]=row[:-1]
    return out

def modules(text):
    result={m.group(1):m.group() for m in MOD.finditer(text)}
    if len(result)!=len(list(MOD.finditer(text))):raise ValueError('Duplicate module')
    return result

def compare(a,b,label):
    ma,mb=modules(a),modules(b);rows=[];escape_a=[];escape_b=[]
    result={'label':label,'modules_before':len(ma),'modules_after':len(mb),
      'added_modules':sorted(set(mb)-set(ma)),'removed_modules':sorted(set(ma)-set(mb)),
      'diagnostic_modules_excluded':sorted((set(ma)|set(mb))&DIAGNOSTICS),
      'byte_identical_application_modules':0,'changed_application_modules':[],
      'header_errors':[],'header_deltas':[],'declaration_changes':[],
      'parameter_changes':[],'assign_changes':[],'connection_changes':rows}
    for name in sorted((set(ma)|set(mb))-DIAGNOSTICS):
        if name not in ma or name not in mb:
            rows.append(dict(module=name,problem='application_module_added_or_removed'));continue
        headers=[]
        for version,source in [('before',ma[name]),('after',mb[name])]:
            try:hs,raw=header(source);headers.append(hs)
            except ValueError as exc:
                result['header_errors'].append(dict(module=name,version=version,error=str(exc)));headers.append(None)
        if headers[0]!=headers[1]:
            result['header_deltas'].append(dict(module=name,before=headers[0],after=headers[1]))
        if ma[name]==mb[name]:
            result['byte_identical_application_modules']+=1;continue
        result['changed_application_modules'].append(name)
        da,db=declarations(ma[name]),declarations(mb[name])
        for pin in sorted(set(da)|set(db)):
            if da.get(pin)!=db.get(pin):result['declaration_changes'].append(dict(module=name,port=pin,before=da.get(pin),after=db.get(pin)))
        for keyword,dest in [('defparam','parameter_changes'),('assign','assign_changes')]:
            sa,sb=statements(ma[name],keyword),statements(mb[name],keyword)
            removed=[v for v in sa if v not in sb];added=[v for v in sb if v not in sa]
            if removed or added:result[dest].append(dict(module=name,removed=removed,added=added))
        ca,cb=instances(ma[name]),instances(mb[name])
        for tag,table,escaped in [('before',ca,escape_a),('after',cb,escape_b)]:
            for instance,c in table.items():
                for pin,expr in c['ports'].items():
                    if pin.startswith('\\'):escaped.append(dict(module=name,instance=instance,pin=pin,expr=expr))
        for inst in sorted(set(ca)|set(cb)):
            if inst not in ca or inst not in cb:
                c=ca.get(inst)or cb[inst]
                rows.append(dict(module=name,instance=inst,kind=c['kind'],change='instance_added' if inst in cb else 'instance_removed',diagnostic=c['kind'] in DIAGNOSTICS));continue
            x,y=ca[inst],cb[inst]
            if x['kind']!=y['kind']:rows.append(dict(module=name,instance=inst,change='kind_changed',before=x['kind'],after=y['kind']))
            for pin in sorted(set(x['ports'])|set(y['ports'])):
                px,py=x['ports'].get(pin),y['ports'].get(pin)
                if px!=py:rows.append(dict(module=name,instance=inst,kind=x['kind'],pin=pin,
                  change='port_added' if px is None else 'port_removed' if py is None else 'expression_changed',
                  before=px,after=py,before_module_line=x['line'],after_module_line=y['line']))
    result['escaped_connections_in_changed_modules_before']=escape_a
    result['escaped_connections_in_changed_modules_after']=escape_b
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path);ap.add_argument('--out',type=Path,default=HERE/'RESULT.json');args=ap.parse_args()
    start=time.monotonic()
    paths={'r19':ROOT/'tang/impl/console_neo_n56r19_capture_ce_local/console_neo.vg',
      's400':ROOT/'tang/impl/console_neo_s400_20261031_r1/console_neo.vg',
      'd128_r2':ROOT/'tang/impl/console_neo_d128_20261102_r2/console_neo.vg'}
    if args.candidate:paths['candidate']=args.candidate
    texts={n:(gzip.decompress(p.read_bytes()).decode() if p.suffix=='.gz' else p.read_text()) for n,p in paths.items()}
    results=[compare(texts['r19'],texts['s400'],'R19_to_S400'),compare(texts['s400'],texts['d128_r2'],'S400_to_D128r2')]
    if args.candidate:results.append(compare(texts['s400'],texts['candidate'],'S400_to_candidate'))
    report=dict(hardware_access=False,production_changed=False,elapsed_s=time.monotonic()-start,
      files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()},
      uncompressed_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in texts.items()},
      script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),comparisons=results,
      limitation='Generated module interfaces and all connections in changed application modules; byte identity covers every remaining application module. Not full behavioral/STA proof; diagnostic helpers excluded explicitly.')
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n')
    for r in results:print(r['label'],'unchanged_modules',r['byte_identical_application_modules'],
      'changed',r['changed_application_modules'],'header_errors',len(r['header_errors']),
      'ports_removed',sum(x.get('change')=='port_removed' for x in r['connection_changes']))

if __name__=='__main__':main()

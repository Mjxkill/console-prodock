"""Generate a proof-only firmware snapshot from the frozen same-base parent.

The maintained input is the single field patch below, not another assembly
fork. All parent inputs are pinned; generated assembly/decoder are evidence.
"""
from pathlib import Path
import hashlib,json,subprocess

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/'copy_empty_same_base_01'
PARENT_BIN_SHA='39484a6b2068dc48f176b3c397eee2551801cbda86936a5d0b38532a208f0663'
PINS={'microdma.S': '63ed596d057cbe9c715b1a93ef8cfd8986e5cbc902976556eb1e74f77824266d', 'build_01/microdma.bin': '39484a6b2068dc48f176b3c397eee2551801cbda86936a5d0b38532a208f0663', 'decode_same_base.py': '1c3b5bd331abbf8b10eff4c043512743817815a9f38c1e282d89b50a5e5a49ba'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def build():
    for name,wanted in PINS.items():assert sha(PARENT/name)==wanted,name
    old=(PARENT/'build_01/microdma.bin').read_bytes();assert hashlib.sha256(old).hexdigest()==PARENT_BIN_SHA
    before=(PARENT/'microdma.S').read_text()
    oldline='    .word 0x1d000000,0x12000020,0x00100001,0x00000020'
    newline='    .word 0x1d000000,0x12000020,0x00010001,0x00000020'
    assert before.count(oldline)==1
    out=HERE/'build_01';out.mkdir()
    source=out/'microdma.S';source.write_text(before.replace(oldline,newline))
    cmd=['/usr/bin/riscv64-unknown-elf-gcc','-march=rv32im_zicsr_zifencei','-mabi=ilp32',
      '-nostdlib','-nostartfiles','-Wl,--no-relax','-Wl,--build-id=none','-Wl,-Ttext=0xa0004000',
      str(source),'-o',str(out/'microdma.elf')]
    subprocess.run(cmd,check=True,capture_output=True,timeout=20)
    subprocess.run(['/usr/bin/riscv64-unknown-elf-objcopy','-O','binary',str(out/'microdma.elf'),str(out/'microdma.bin')],check=True,capture_output=True,timeout=10)
    listing=subprocess.run(['/usr/bin/riscv64-unknown-elf-objdump','-d','-s',str(out/'microdma.elf')],check=True,capture_output=True,text=True,timeout=10)
    (out/'listing.txt').write_text(listing.stdout)
    binary=(out/'microdma.bin').read_bytes();assert len(binary)==len(old)==928
    changed=[i for i in range(len(old)) if binary[i]!=old[i]]
    assert changed==[906] and old[906]==16 and binary[906]==1
    newsha=sha(out/'microdma.bin')
    decoder=(PARENT/'decode_same_base.py').read_text()
    assert decoder.count(PARENT_BIN_SHA)==1
    # Only provenance changes: MD12 sequence and seed-only final expectation
    # are identical, and the old firmware SHA must no longer be accepted.
    bound=decoder.replace(PARENT_BIN_SHA,newsha)
    assert bound.replace(newsha,PARENT_BIN_SHA)==decoder
    (out/'decode_width1.py').write_text(bound)
    manifest=dict(hardware=False,code_bytes=928,code_address='0xa0004000',code_end_exclusive='0xa00043a0',
      journal_address='0xa0006000',journal_bytes=512,journal_magic='MD12',scratch_address='0x12000000',scratch_bytes=128,
      gpu_expected_read_bytes=0,gpu_expected_write_bytes=0,parent_sha256=PARENT_BIN_SHA,changed_byte_offsets=changed,
      generated_snapshots=True,parent_pins=PINS,files={f.name:sha(f) for f in sorted(out.iterdir())})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(binary_bytes=928,sha256=newsha,changed_byte_offsets=changed)))

if __name__=='__main__':build()

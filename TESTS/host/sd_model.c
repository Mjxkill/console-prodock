// Modèle d'une carte SDHC en mode SPI, octet par octet, pour tester fw_console/sd.c et FatFs sur PC.
// Il vérifie ce qu'une vraie carte exige : horloges de réveil, CRC7 des commandes, CRC16 des blocs
// écrits, sélection maintenue pendant une séquence. Il peut injecter des erreurs.
#include <stdint.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sd.h"
static uint8_t *image; static uint32_t sectors;
static int corrupt_csd;
void model_corrupt_csd(int corrupt) { corrupt_csd=corrupt; }
static struct { int present, selected, idle, crc_on, wake, acmd, app, hz; unsigned clock_ms;
    uint8_t command[6]; unsigned filled;
    uint8_t out[1100]; unsigned head, count, busy;
    int streaming; uint32_t stream_sector;
    int writing, multi; uint32_t write_sector; uint8_t block[515]; unsigned block_filled; int collecting;
    unsigned corrupt_reads, reject_writes, violations, commands, reads, writes;
    unsigned transport_length, transport_after, transport_left, transport_hits;
    unsigned programming_errors, r2, cmd13, stops, busy_block, busy_length; unsigned long bytes; } m;
void model_load(uint8_t *data, uint32_t count) { image=data; sectors=count; memset(&m,0,sizeof m); m.present=1; m.idle=1; }
void model_present(int present) { m.present=present; }
void model_corrupt_reads(unsigned count) { m.corrupt_reads=count; }
void model_reject_writes(unsigned count) { m.reject_writes=count; }
void model_programming_errors(unsigned count) { m.programming_errors=count; }
void model_busy_after(unsigned block, unsigned ticks) { m.busy_block=block; m.busy_length=ticks; }
unsigned model_cmd13(void) { return m.cmd13; }
unsigned model_stops(void) { return m.stops; }
unsigned model_writing(void) { return m.writing; }
unsigned model_violations(void) { return m.violations; }
// Fail the selected transfer size after a bounded prefix. This models a
// partial transport failure, independently of SD token/CRC/protocol errors.
void model_transport_fault(unsigned length, unsigned after, unsigned failures)
{ m.transport_length=length; m.transport_after=after; m.transport_left=failures; m.transport_hits=0; }
unsigned model_transport_hits(void) { return m.transport_hits; }
unsigned model_selected(void) { return (unsigned)m.selected; }
unsigned model_speed(void) { return (unsigned)m.hz; }
static void push(unsigned value) { if (m.count<sizeof m.out) m.out[(m.head+m.count++)%sizeof m.out]=(uint8_t)value; else ++m.violations; }
static void push_block(const uint8_t *data, unsigned count, int corrupt)
{
    unsigned crc=sd_crc16(data,count);
    push(0xff); push(0xfe);
    for (unsigned i=0;i<count;++i) push(data[i]^(corrupt && i==7 ? 0x10 : 0));
    push(crc>>8); push(crc);
}
static void execute(void)
{
    unsigned index=m.command[0]&63; uint32_t arg=((uint32_t)m.command[1]<<24)|((uint32_t)m.command[2]<<16)|((uint32_t)m.command[3]<<8)|m.command[4];
    int app=m.app; m.app=0; ++m.commands;
    m.count=0; m.streaming=0;                                    // une commande interrompt ce qui était émis
    push(0xff);                                                  // un octet avant la réponse
    if ((m.crc_on || index==0 || index==8) && sd_crc7(m.command,5)!=m.command[5]) { push(0x08|(m.idle?1:0)); return; }
    if (index==0) { if (m.wake<74) ++m.violations; m.idle=1; m.acmd=0; m.crc_on=0; m.writing=0; m.r2=0; push(1); return; }
    if (index==8) { push(m.idle?1:0); push(0); push(0); push(1); push(arg&0xff); return; }
    if (index==59) { m.crc_on=arg&1; push(m.idle?1:0); return; }
    if (index==55) { m.app=1; push(m.idle?1:0); return; }
    if (index==41 && app) { if (++m.acmd>=3 && (arg&0x40000000)) m.idle=0; push(m.idle?1:0); return; }
    if (index==58) { push(m.idle?1:0); push(0xc0); push(0xff); push(0x80); push(0); return; }      // alimentée, grande capacité
    if (m.idle) { push(0x05); return; }                          // commande illégale avant la fin de l'initialisation
    if (index==13) { ++m.cmd13; push(0); push(m.r2); m.r2=0; return; }
    if (index==9) { uint8_t csd[16]={0x40,0x0e,0,0x32,0x5b,0x59,0,0,0,0,0x7f,0x80,0x0a,0x40,0,0}; uint32_t c=sectors/1024-1;
        csd[7]=(c>>16)&0x3f; csd[8]=c>>8; csd[9]=c; push(0); push_block(csd,16,corrupt_csd); return; }
    if (index==16) { push(arg==512?0:0x40); return; }
    if (index==12) { push(0xff); push(0); m.busy=2; return; }
    if (index==17 || index==18) {
        if (arg>=sectors) { push(0x40); return; }
        push(0); ++m.reads; int corrupt=m.corrupt_reads>0; if (corrupt) --m.corrupt_reads;
        push_block(image+(size_t)arg*512,512,corrupt);
        if (index==18) { m.streaming=1; m.stream_sector=arg+1; }
        return; }
    if (index==23 && app) { push(0); return; }
    if (index==24 || index==25) {
        if (arg>=sectors) { push(0x40); return; }
        push(0); m.writing=1; m.multi=index==25; m.write_sector=arg; m.collecting=0; return; }
    push(0x04);
}
static uint8_t model_byte(uint8_t in)
{
    uint8_t out=0xff; ++m.bytes;
    if (!m.selected) { m.wake+=8; return 0xff; }
    if (m.count) { out=m.out[m.head]; m.head=(m.head+1)%sizeof m.out; --m.count; }
    else if (m.busy) { out=0; --m.busy; }
    else if (m.streaming && m.stream_sector<sectors) { int corrupt=m.corrupt_reads>0; if (corrupt) --m.corrupt_reads;
        push_block(image+(size_t)m.stream_sector++*512,512,corrupt); ++m.reads; }
    if (m.collecting) {                                          // données d'un bloc en cours d'écriture
        m.block[m.block_filled++]=in;
        if (m.block_filled==514) {
            unsigned crc=((unsigned)m.block[512]<<8)|m.block[513]; m.collecting=0;
            if (m.reject_writes) { --m.reject_writes; push(0x0b); }
            else if (crc!=sd_crc16(m.block,512)) push(0x0b);
            else {
                if(m.programming_errors) { --m.programming_errors; m.r2|=0x04; }
                else memcpy(image+(size_t)m.write_sector*512,m.block,512);
                ++m.write_sector; ++m.writes; push(0x05);
                m.busy=m.writes==m.busy_block ? m.busy_length : 3;
            }
            if (!m.multi) m.writing=0;
        }
        return out;
    }
    if (m.writing && !m.filled) {
        if (in==0xfe && !m.multi) { m.collecting=1; m.block_filled=0; return out; }
        if (in==0xfc && m.multi) { m.collecting=1; m.block_filled=0; return out; }
        if (in==0xfd && m.multi) { m.writing=0; m.busy=4; ++m.stops; return out; }
    }
    if (m.filled || (in&0xc0)==0x40) {                           // 01xxxxxx ouvre une commande
        m.command[m.filled++]=in;
        if (m.filled==6) { m.filled=0; m.writing=0; execute(); }
    }
    return out;
}
// Les quatre fonctions attendues par sd.c.
void sd_port_speed(unsigned hz) { m.hz=(int)hz; }
void sd_port_select(int selected) { if (m.filled) ++m.violations; m.selected=selected; if (!selected) m.streaming=0; }
int sd_port_exchange(const uint8_t *tx, uint8_t *rx, unsigned count)
{
    int fail=m.transport_left && count==m.transport_length;
    unsigned done=fail && m.transport_after<count ? m.transport_after : count;
    for (unsigned i=0;i<done;++i) { uint8_t value=model_byte(tx ? tx[i] : 0xff); if (rx) rx[i]=value; }
    m.clock_ms+=1+done/64;
    if (fail) { --m.transport_left; ++m.transport_hits; return -ETIMEDOUT; }
    return 0;
}
unsigned sd_port_ms(void) { return m.clock_ms++; }
int sd_port_present(void) { return m.present; }

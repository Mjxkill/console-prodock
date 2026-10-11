// Carte SD en mode SPI : initialisation, lecture et écriture de blocs de 512 octets.
// Les CRC sont activés (CMD59) : CRC7 sur chaque commande, CRC16 vérifié sur chaque bloc lu.
// Un bloc au CRC faux est relu ; après trois échecs consécutifs la fréquence est divisée par deux.
#include "sd.h"
#include <stddef.h>
enum { CMD0=0, CMD8=8, CMD9=9, CMD12=12, CMD13=13, CMD16=16, CMD17=17, CMD18=18, CMD24=24, CMD25=25,
       CMD55=55, CMD58=58, CMD59=59, ACMD23=23, ACMD41=41 };
enum { TOKEN_BLOCK=0xfe, TOKEN_MULTI_WRITE=0xfc, TOKEN_STOP_WRITE=0xfd, R1_IDLE=1, R1_ILLEGAL=4 };

uint8_t sd_crc7(const uint8_t *data, unsigned count)
{
    unsigned crc=0;
    for (unsigned i=0;i<count;++i) {
        unsigned byte=data[i];
        for (unsigned bit=0;bit<8;++bit,byte<<=1) {
            crc<<=1;
            if ((byte^crc)&0x80) crc^=0x09;
        }
    }
    return (uint8_t)((crc<<1)|1);          // sept bits de CRC puis le bit de fin
}
uint16_t sd_crc16(const uint8_t *data, unsigned count)
{
    unsigned crc=0;                         // CCITT, polynôme 0x1021, initial 0
    for (unsigned i=0;i<count;++i) {
        crc=((crc>>8)|(crc<<8))&0xffff;
        crc^=data[i];
        crc^=(crc&0xff)>>4;
        crc^=(crc<<12)&0xffff;
        crc^=((crc&0xff)<<5)&0xffff;
    }
    return (uint16_t)crc;
}
static uint8_t receive(void) { uint8_t value; sd_port_exchange(NULL,&value,1); return value; }
// La carte tient la ligne de données basse tant qu'elle est occupée.
static int wait_ready(unsigned ms)
{
    unsigned start=sd_port_ms();
    do { if (receive()==0xff) return 1; } while (sd_port_ms()-start<ms);
    return 0;
}
static void release(void) { sd_port_select(0); (void)receive(); }
// Envoie une commande, carte sélectionnée, et renvoie sa réponse R1 (0xff : pas de réponse).
static unsigned command(unsigned index, uint32_t argument)
{
    uint8_t frame[6]={(uint8_t)(0x40|index),(uint8_t)(argument>>24),(uint8_t)(argument>>16),(uint8_t)(argument>>8),(uint8_t)argument,0};
    frame[5]=sd_crc7(frame,5);
    if (index!=CMD0 && index!=CMD12 && !wait_ready(500)) return 0xff;
    sd_port_exchange(frame,NULL,6);
    if (index==CMD12) (void)receive();      // octet de bourrage après l'arrêt d'une lecture multiple
    for (unsigned i=0;i<10;++i) { unsigned r=receive(); if (!(r&0x80)) return r; }
    return 0xff;
}
static unsigned app_command(unsigned index, uint32_t argument)
{
    unsigned r=command(CMD55,0);
    return r>1 ? r : command(index,argument);
}
// Reçoit un bloc de données précédé de son jeton et suivi de son CRC16.
static int receive_block(uint8_t *data, unsigned count)
{
    uint8_t crc[2]; unsigned token, start=sd_port_ms();
    do token=receive(); while (token==0xff && sd_port_ms()-start<300);
    if (token!=TOKEN_BLOCK) return SD_TIMEOUT;
    sd_port_exchange(NULL,data,count);
    sd_port_exchange(NULL,crc,2);
    return sd_crc16(data,count)==(((unsigned)crc[0]<<8)|crc[1]) ? SD_OK : SD_CRC;
}
static int send_block(const uint8_t *data, unsigned token)
{
    unsigned check=sd_crc16(data,512); uint8_t head=(uint8_t)token, crc[2]={(uint8_t)(check>>8),(uint8_t)check};
    if (!wait_ready(500)) return SD_TIMEOUT;
    sd_port_exchange(&head,NULL,1);
    sd_port_exchange(data,NULL,512);
    sd_port_exchange(crc,NULL,2);
    unsigned response=receive()&0x1f;       // xxx0sss1 : 00101 accepté, 01011 CRC refusé, 01101 erreur d'écriture
    return response==0x05 ? SD_OK : response==0x0b ? SD_CRC : SD_REJECTED;
}
static uint32_t capacity(const uint8_t csd[16])
{
    if ((csd[0]>>6)==1)                     // CSD version 2 : (C_SIZE+1) × 1024 blocs
        return (((((uint32_t)csd[7]&0x3f)<<16)|((uint32_t)csd[8]<<8)|csd[9])+1U)<<10;
    if ((csd[0]>>6)==0) {                   // CSD version 1
        uint32_t c_size=(((uint32_t)csd[6]&3)<<10)|((uint32_t)csd[7]<<2)|(csd[8]>>6);
        unsigned mult=((csd[9]&3U)<<1)|(csd[10]>>7), block=csd[5]&15U;
        uint64_t blocks=((uint64_t)c_size+1)<<(mult+2+block);
        blocks>>=9;
        return blocks<=UINT32_MAX ? (uint32_t)blocks : 0;
    }
    return 0;
}
int sd_init(sd_card *card, unsigned hz)
{
    uint8_t reply[4], csd[16]; unsigned r=0xff, start;
    *card=(sd_card){0};
    if (!hz) return SD_PARAMETER;
    if (!sd_port_present()) return SD_NO_CARD;
    sd_port_speed(400000);
    sd_port_select(0);
    for (unsigned i=0;i<10;++i) (void)receive();      // au moins 74 fronts d'horloge, carte non sélectionnée
    for (unsigned i=0;i<10 && r!=R1_IDLE;++i) { sd_port_select(1); r=command(CMD0,0); release(); }
    if (r!=R1_IDLE) return SD_TIMEOUT;
    sd_port_select(1);
    r=command(CMD8,0x1aa);                             // 2,7 à 3,6 V, motif de contrôle 0xaa
    if (r==R1_IDLE) {
        sd_port_exchange(NULL,reply,4);
        if (reply[2]!=1 || reply[3]!=0xaa) { release(); return SD_REJECTED; }
        card->version2=1;
    } else if (!(r&R1_ILLEGAL)) { release(); return SD_REJECTED; }
    release();
    sd_port_select(1); r=command(CMD59,1); release();  // CRC exigés et produits par la carte
    if (r>1) return SD_REJECTED;
    start=sd_port_ms();
    do { sd_port_select(1); r=app_command(ACMD41,card->version2 ? 0x40000000U : 0); release(); }
    while (r==R1_IDLE && sd_port_ms()-start<2000);
    if (r) return r==R1_IDLE ? SD_TIMEOUT : SD_REJECTED;
    sd_port_select(1);
    if (command(CMD58,0)) { release(); return SD_REJECTED; }
    sd_port_exchange(NULL,reply,4); release();
    card->high_capacity=card->version2 && (reply[0]&0x40);
    if (!card->high_capacity) { sd_port_select(1); r=command(CMD16,512); release(); if (r) return SD_REJECTED; }
    sd_port_select(1);
    int status=command(CMD9,0)==0 ? receive_block(csd,16) : SD_REJECTED;
    release();
    if (status!=SD_OK) return status;
    card->sectors=capacity(csd);
    if (!card->sectors) return SD_REJECTED;
    card->hz=hz; sd_port_speed(hz); card->ready=1;
    return SD_OK;
}
// Après trois échecs de suite, la moitié de la fréquence, jusqu'à 400 kHz.
static int failed(sd_card *card, unsigned attempt, int status)
{
    ++card->retries;
    if (status==SD_CRC) ++card->crc_errors;
    if (attempt%3==2 && card->hz>400000) { card->hz/=2; if(card->hz<400000)card->hz=400000; ++card->downshifts; sd_port_speed(card->hz); }
    return attempt>=8;
}
int sd_read(sd_card *card, uint32_t sector, uint8_t *data, unsigned count)
{
    if (!card->ready || !data || !count || sector>=card->sectors || count>card->sectors-sector) return SD_PARAMETER;
    if (!sd_port_present()) { card->ready=0; return SD_NO_CARD; }
    for (unsigned attempt=0;;++attempt) {
        int status=SD_OK; unsigned done=0;
        sd_port_select(1);
        if (command(count>1 ? CMD18 : CMD17, card->high_capacity ? sector : sector<<9)) status=SD_REJECTED;
        for (;status==SD_OK && done<count;++done) status=receive_block(data+done*512U,512);
        if (count>1) (void)command(CMD12,0);
        release();
        if (status==SD_OK) return SD_OK;
        if (failed(card,attempt,status)) return status;
    }
}
int sd_write(sd_card *card, uint32_t sector, const uint8_t *data, unsigned count)
{
    if (!card->ready || !data || !count || sector>=card->sectors || count>card->sectors-sector) return SD_PARAMETER;
    if (!sd_port_present()) { card->ready=0; return SD_NO_CARD; }
    for (unsigned attempt=0;;++attempt) {
        int status=SD_OK;
        sd_port_select(1);
        if (count==1) {
            if (command(CMD24, card->high_capacity ? sector : sector<<9)) status=SD_REJECTED;
            else status=send_block(data,TOKEN_BLOCK);
        } else {
            (void)app_command(ACMD23,count);            // pré-effacement, facultatif
            if (command(CMD25, card->high_capacity ? sector : sector<<9)) status=SD_REJECTED;
            else {
                for (unsigned done=0;status==SD_OK && done<count;++done) status=send_block(data+done*512U,TOKEN_MULTI_WRITE);
                // CMD25 se termine par STOP, y compris après refus d'un bloc.
                // CMD12 termine une lecture : il ne remplace pas ce jeton.
                if (!wait_ready(500)) {
                    card->ready=0; release(); return SD_TIMEOUT;
                }
                uint8_t stop=TOKEN_STOP_WRITE;
                sd_port_exchange(&stop,NULL,1); (void)receive();
            }
        }
        // La fin de busy n'est pas une preuve de programmation réussie :
        // des erreurs ne sont visibles qu'à SEND_STATUS (réponse R1 + R2).
        if (!wait_ready(1000)) { card->ready=0; release(); return SD_TIMEOUT; }
        unsigned r1=command(CMD13,0);
        unsigned r2=r1==0xff ? 0xff : receive();
        if (r1==0xff) { card->ready=0; release(); return SD_TIMEOUT; }
        if (r1 || r2) { release(); return SD_REJECTED; }
        release();
        if (status==SD_OK) return SD_OK;
        if (failed(card,attempt,status)) return status;
    }
}

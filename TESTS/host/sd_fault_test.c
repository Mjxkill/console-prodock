// Erreurs tardives et terminaison CMD25 : mémoire simulée, aucun matériel.
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "sd.h"
void model_load(uint8_t *,uint32_t);
void model_programming_errors(unsigned);
void model_busy_after(unsigned,unsigned);
void model_corrupt_reads(unsigned);
void model_reject_writes(unsigned);
unsigned model_cmd13(void), model_stops(void), model_writing(void);
void model_transport_fault(unsigned,unsigned,unsigned);
unsigned model_transport_hits(void),model_selected(void);
unsigned model_speed(void);
#define CHECK(c) do { if(!(c)){printf("FAIL line %d: %s\n",__LINE__,#c);return 1;} } while(0)
int main(void)
{
    static uint8_t media[4096*512], data[1024], readback[1024];
    memset(data,0xa5,sizeof data);
    for(unsigned blocks=1;blocks<=2;++blocks) {
        for(unsigned fault=0;fault<=1;++fault) {
            memset(media,0,sizeof media); model_load(media,4096);
            sd_card card; CHECK(sd_init(&card,20000000)==SD_OK);
            if(fault)model_programming_errors(blocks);
            int result=sd_write(&card,23,data,blocks);
            CHECK(result==(fault ? SD_REJECTED : SD_OK));
            CHECK(model_cmd13()==1 && !model_writing());
            CHECK(model_stops()==(blocks==2));
            if(fault) { for(unsigned i=0;i<blocks*512;++i)CHECK(media[23*512+i]==0); }
            else CHECK(memcmp(media+23*512,data,blocks*512)==0);
            // Le statut a été consommé et l'accès suivant doit rester correct.
            CHECK(sd_write(&card,23,data,blocks)==SD_OK);
            CHECK(sd_read(&card,23,readback,blocks)==SD_OK);
            CHECK(memcmp(data,readback,blocks*512)==0);
            printf("SD late status blocks=%u fault=%u PASS\n",blocks,fault);
        }
    }
    // 400 octets occupés dépassent la première attente du modèle, pas les
    // deux attentes cumulées de l'ancienne implémentation.
    model_load(media,4096); sd_card card; CHECK(sd_init(&card,20000000)==SD_OK);
    model_busy_after(2,400);
    CHECK(sd_write(&card,23,data,2)==SD_TIMEOUT);
    CHECK(!card.ready && model_stops()==0 && model_writing());
    CHECK(sd_read(&card,23,readback,1)==SD_PARAMETER);
    CHECK(sd_write(&card,23,data,1)==SD_PARAMETER);
    // Réinitialisation explicite requise avant toute nouvelle transaction.
    model_busy_after(0,0);
    CHECK(sd_init(&card,20000000)==SD_OK);
    CHECK(sd_write(&card,23,data,2)==SD_OK && !model_writing());
    CHECK(sd_read(&card,23,readback,2)==SD_OK && memcmp(data,readback,1024)==0);
    // Transport failures must not be mistaken for successful SD responses or
    // for CRC failures. Each RX buffer may contain only a prefix on failure.
    model_load(media,4096); model_transport_fault(4,2,1);
    CHECK(sd_init(&card,20000000)==SD_TIMEOUT);
    CHECK(!card.ready && model_transport_hits()==1 && !model_selected());
    for (unsigned length=2; length<=512; length+=510) {
        model_load(media,4096); CHECK(sd_init(&card,20000000)==SD_OK);
        memset(readback,0xcc,sizeof readback);
        model_transport_fault(length,length==512 ? 63 : 1,20);
        CHECK(sd_read(&card,23,readback,1)==SD_TIMEOUT);
        CHECK(card.retries==9 && card.crc_errors==0 && !model_selected());
        CHECK(model_transport_hits()>=1 && model_transport_hits()<=9);
        printf("SD transport RX size=%u bounded retry PASS\n",length);
    }
    model_load(media,4096); CHECK(sd_init(&card,20000000)==SD_OK);
    model_transport_fault(512,63,1);
    CHECK(sd_write(&card,23,data,1)==SD_TIMEOUT);
    CHECK(!card.ready && !model_selected() && model_transport_hits()==1);
    // Régression du régime fixe : les reprises bornées après CRC ou TIMEOUT
    // restent visibles, mais aucune erreur ne rappelle sd_port_speed. Les
    // lectures et écritures simples et multibloc gardent donc la fréquence
    // demandée à sd_init et rendent des données exactes après récupération.
    for (unsigned blocks=1; blocks<=2; ++blocks) {
        model_load(media,4096); CHECK(sd_init(&card,20000000)==SD_OK);
        model_corrupt_reads(blocks==1 ? 3 : 5);
        CHECK(sd_read(&card,23,readback,blocks)==SD_OK);
        CHECK(card.retries==3 && card.crc_errors==3 && model_speed()==20000000);
        CHECK(memcmp(media+23*512,readback,blocks*512)==0);
        model_load(media,4096); CHECK(sd_init(&card,20000000)==SD_OK);
        model_corrupt_reads(40);
        CHECK(sd_read(&card,23,readback,blocks)==SD_CRC);
        CHECK(card.retries==9 && card.crc_errors==9 && model_speed()==20000000);
        model_load(media,4096); CHECK(sd_init(&card,20000000)==SD_OK);
        model_reject_writes(3);
        CHECK(sd_write(&card,23,data,blocks)==SD_OK);
        CHECK(card.retries==3 && card.crc_errors==3 && model_speed()==20000000);
        CHECK(memcmp(media+23*512,data,blocks*512)==0);
        model_load(media,4096); CHECK(sd_init(&card,20000000)==SD_OK);
        model_reject_writes(40);
        CHECK(sd_write(&card,23,data,blocks)==SD_CRC);
        CHECK(card.retries==9 && card.crc_errors==9 && model_speed()==20000000);
        model_load(media,4096); CHECK(sd_init(&card,20000000)==SD_OK);
        model_transport_fault(512,63,20);
        CHECK(sd_read(&card,23,readback,blocks)==SD_TIMEOUT);
        CHECK(card.retries==9 && card.crc_errors==0 && model_speed()==20000000);
        CHECK(model_transport_hits()>=1 && model_transport_hits()<=9 && !model_selected());
        model_load(media,4096); CHECK(sd_init(&card,20000000)==SD_OK);
        model_transport_fault(512,63,1);
        CHECK(sd_write(&card,23,data,blocks)==SD_TIMEOUT);
        CHECK(!card.ready && card.crc_errors==0 && model_speed()==20000000);
        CHECK(model_transport_hits()==1 && !model_selected());
        printf("SD fixed-rate CRC/TIMEOUT blocks=%u PASS\n",blocks);
    }
    // Successful reinitialisation explicitly clears the operation error latch.
    model_load(media,4096); CHECK(sd_init(&card,20000000)==SD_OK);
    CHECK(sd_write(&card,23,data,1)==SD_OK);
    CHECK(sd_read(&card,23,readback,1)==SD_OK && !memcmp(data,readback,512));
    puts("SD FAULT PASS : aucune erreur tardive ni terminaison manquante annoncée comme succès");
    return 0;
}

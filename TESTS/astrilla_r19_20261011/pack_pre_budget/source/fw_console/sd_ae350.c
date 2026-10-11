// Carte SD sur le SPI maître intégré de l'AE350 (ATCSPI200, 0xF0F00000) : horloge divisée de
// l'horloge APB 80 MHz, sélection de la carte par la sortie GPIO 0, présence lue sur GPIO 1.
// La sélection n'utilise pas la broche CS du contrôleur : il la relâche entre deux transferts,
// alors qu'une carte SD exige qu'elle reste active de la commande à la fin des données.
#include "ae350.h"
#include "sd.h"
#define APB_HZ 80000000U
enum { SPI_ACTIVE=1U<<0, RX_EMPTY=1U<<14, TX_FULL=1U<<23, RESET_SPI=1U<<0, RESET_RX=1U<<1, RESET_TX=1U<<2,
       MODE_BOTH=0U<<24, MODE_WRITE=1U<<24, DATA_MERGE=1U<<7, SD_SELECT=1U<<0, SD_DETECT=1U<<1 };
static int configured;
static unsigned long long cycles(void)
{
    unsigned hi,lo,again;
    do { __asm__ volatile("rdcycleh %0":"=r"(hi)); __asm__ volatile("rdcycle %0":"=r"(lo)); __asm__ volatile("rdcycleh %0":"=r"(again)); } while (hi!=again);
    return ((unsigned long long)hi<<32)|lo;
}
static void configure(void)
{
    AE350_GPIO->DOUTSET=SD_SELECT;                     // carte non sélectionnée avant de piloter la broche
    AE350_GPIO->CHANNELDIR|=SD_SELECT;
    AE350_SPI->CTRL=RESET_SPI|RESET_RX|RESET_TX;
    while (AE350_SPI->CTRL&(RESET_SPI|RESET_RX|RESET_TX)) {}
    AE350_SPI->INTREN=0;
    AE350_SPI->TRANSFMT=7U<<8;                         // maître, mode 0, poids fort en tête, mots de 8 bits
    configured=1;
}
void sd_port_speed(unsigned hz)
{
    if (!configured) configure();
    unsigned divider=(APB_HZ+2*hz-1)/(2*hz);           // SCK = APB / (2 × (n + 1)), arrondi vers la fréquence inférieure
    divider=divider ? divider-1 : 0;
    if (divider>254) divider=254;                      // 255 désigne l'horloge APB elle-même
    while (AE350_SPI->STATUS&SPI_ACTIVE) {}
    AE350_SPI->TIMING=(AE350_SPI->TIMING&~0xffU)|divider;
}
void sd_port_select(int selected)
{
    if (!configured) configure();
    if (selected) AE350_GPIO->DOUTCLEAR=SD_SELECT; else AE350_GPIO->DOUTSET=SD_SELECT;
}
// Un transfert d'au plus 512 octets. merged : quatre octets par accès au registre de données
// (premier octet dans les bits 7:0), pour les blocs ; sinon un octet par accès.
static void transfer(const uint8_t *tx, uint8_t *rx, unsigned part, int merged)
{
    unsigned step=merged ? 4U : 1U, sent=0, got=0, reads=rx ? part : 0;
    while (AE350_SPI->STATUS&SPI_ACTIVE) {}
    AE350_SPI->CTRL|=RESET_RX|RESET_TX;
    while (AE350_SPI->CTRL&(RESET_RX|RESET_TX)) {}
    AE350_SPI->TRANSFMT=(7U<<8)|(merged ? DATA_MERGE : 0U);
    // Toujours un échange complet : sans données à émettre, des 0xFF. En lecture seule le
    // contrôleur tient la ligne de commande à 0 ; la carte y voit des débuts de trame et perd
    // l'alignement de ses réponses (relevé sur carte le 5 octobre 2026).
    AE350_SPI->TRANSCTRL=(rx ? MODE_BOTH : MODE_WRITE)|((part-1)<<12)|(part-1);
    for (int started=0; sent<part || got<reads; ) {
        unsigned status=AE350_SPI->STATUS;
        if (sent<part && !(status&TX_FULL)) {
            uint32_t word=0xffffffffU;
            if (tx) { if (merged) __builtin_memcpy(&word,tx+sent,4); else word=tx[sent]; }
            AE350_SPI->DATA=word; sent+=step;
        } else if (!started) { AE350_SPI->CMD=0; started=1; }   // file garnie avant le départ : l'horloge ne l'attend jamais
        if (sent>=part && !started) { AE350_SPI->CMD=0; started=1; }
        if (started && got<reads && !(status&RX_EMPTY)) {
            uint32_t word=AE350_SPI->DATA;
            if (merged) __builtin_memcpy(rx+got,&word,4); else rx[got]=(uint8_t)word;
            got+=step;
        }
    }
    while (AE350_SPI->STATUS&SPI_ACTIVE) {}
}
void sd_port_exchange(const uint8_t *tx, uint8_t *rx, unsigned count)
{
    while (count) {
        unsigned part=count>512 ? 512 : count;
        if (part>=16) part&=~3U;                       // la partie multiple de quatre part en mots
        transfer(tx,rx,part,part>=16);
        if (tx) tx+=part;
        if (rx) rx+=part;
        count-=part;
    }
}
unsigned sd_port_ms(void) { return (unsigned)(cycles()/800000ULL); }
// J15 est tirée au haut hors présence, contact fermé à la masse carte insérée
// (GPIO 1 = 0 relevé sur la carte). Ne pas lancer de commandes si elle manque.
int sd_port_present(void) { return (AE350_GPIO->DATAIN&SD_DETECT)==0; }
unsigned sd_ae350_detect_raw(void) { return (AE350_GPIO->DATAIN&SD_DETECT) ? 1U : 0U; }
unsigned sd_ae350_spi_id(void) { return AE350_SPI->IDREV; }

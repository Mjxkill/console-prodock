// Carte SD en mode SPI. Pilote indépendant du matériel : il parle à la carte par les quatre
// fonctions sd_port_* (SPI de l'AE350 dans sd_ae350.c, modèle de carte dans les tests sur PC).
#ifndef CONSOLE_SD_H
#define CONSOLE_SD_H
#include <stdint.h>
enum { SD_OK=0, SD_NO_CARD, SD_TIMEOUT, SD_REJECTED, SD_CRC, SD_PARAMETER };
typedef struct {
    unsigned ready;        // 1 après sd_init réussi
    unsigned high_capacity;// 1 : adressage par bloc (SDHC/SDXC), 0 : par octet (SDSC)
    unsigned version2;     // 1 : carte SD 2.0 ou plus
    uint32_t sectors;      // capacité en blocs de 512 octets, 0 si le CSD n'est pas compris
    unsigned hz;           // fréquence SPI de régime demandée à sd_init, conservée après erreur
    unsigned crc_errors;   // blocs relus à cause d'un CRC16 faux
    unsigned retries;      // commandes ou blocs rejoués
} sd_card;
// Le matériel fournit : fréquence d'horloge, sélection, échange d'octets (tx NULL : envoie 0xFF,
// rx NULL : ignore), temps en millisecondes pour les délais, présence de la carte.
void sd_port_speed(unsigned hz);
void sd_port_select(int selected);
// 0 on complete exchange; negative errno on transport failure. Partial RX
// contents are invalid on failure. count=0 checks any preceding setup error.
int sd_port_exchange(const uint8_t *tx, uint8_t *rx, unsigned count);
unsigned sd_port_ms(void);
int sd_port_present(void);

int sd_init(sd_card *card, unsigned hz);
int sd_read(sd_card *card, uint32_t sector, uint8_t *data, unsigned count);
int sd_write(sd_card *card, uint32_t sector, const uint8_t *data, unsigned count);
// Références des contrôles, testées séparément.
uint8_t sd_crc7(const uint8_t *data, unsigned count);
uint16_t sd_crc16(const uint8_t *data, unsigned count);
#endif

// Disque USB (stockage de masse, Bulk-Only + SCSI transparent) servi par le firmware.
// Le matériel (usb_msc_port.v, fenêtre 0xE9003000) ne transporte que des octets ; ce module
// interprète les commandes de l'hôte et les applique à un périphérique de blocs de 512 octets
// (carte SD, ou zone de DDR pour les essais). Indépendant du matériel : les registres sont
// atteints par usb_msc_reg_read/write (accès directs sur l'AE350, modèle dans les tests sur PC).
#ifndef CONSOLE_USB_MSC_H
#define CONSOLE_USB_MSC_H
#include <stdint.h>
typedef struct {
    uint32_t blocks;                 // capacité en blocs de 512 octets ; 0 : pas de support
    int write_protected;
    void *context;
    int (*read)(void *context, uint32_t block, uint8_t *data, uint32_t count);        // 0 : réussi
    int (*write)(void *context, uint32_t block, const uint8_t *data, uint32_t count); // 0 : réussi
    int (*sync)(void *context);      // peut être NULL
} usb_msc_disk;
typedef struct {
    uint32_t commands, failed;       // commandes terminées, dont celles en échec
    uint32_t read_blocks, written_blocks;
    uint32_t resets;                 // resets du bus ou Bulk-Only pris en compte
    uint32_t resyncs;                // octets de préfixe invalides ; impose désormais un reset BOT
    uint32_t timeouts;               // transferts abandonnés faute de progression
    uint32_t losses;                 // indicateur « perte » du port vu levé
    uint32_t takeovers;              // disque repris par le matériel puis redemandé
    uint8_t last_opcode;
} usb_msc_stats;

// Demande à servir le disque avec ce support. Le matériel l'accorde entre deux commandes de
// l'hôte ; d'ici là, et quand aucun firmware ne le sert, il répond « lecteur sans carte ».
void usb_msc_init(const usb_msc_disk *disk);
// Rend le disque au matériel (à appeler entre deux usb_msc_poll avant de quitter).
void usb_msc_release(void);
// 1 si le firmware sert actuellement le disque.
int usb_msc_serving(void);
// À appeler régulièrement. Traite au plus une commande de l'hôte ; renvoie 1 si une commande
// a été traitée, 0 s'il n'y avait rien à faire. Ne bloque que pendant un transfert en cours.
int usb_msc_poll(void);
// Remplace le support (insertion, retrait avec blocks = 0) ; l'hôte en est averti par
// UNIT ATTENTION à sa commande suivante.
void usb_msc_media(const usb_msc_disk *disk);
const usb_msc_stats *usb_msc_statistics(void);
// 1 si l'hôte a configuré le périphérique ; *high_speed renseigné si non NULL.
int usb_msc_online(int *high_speed);

// Fournis par le matériel.
#ifdef USB_MSC_HOST_MODEL
uint32_t usb_msc_reg_read(unsigned offset);
void usb_msc_reg_write(unsigned offset, uint32_t value);
unsigned usb_msc_ms(void);
#else
#define USB_MSC_BASE 0xE9003000UL
static inline uint32_t usb_msc_reg_read(unsigned offset) { return *(volatile uint32_t *)(USB_MSC_BASE + offset); }
static inline void usb_msc_reg_write(unsigned offset, uint32_t value) { *(volatile uint32_t *)(USB_MSC_BASE + offset) = value; }
unsigned usb_msc_ms(void);
#endif
#endif

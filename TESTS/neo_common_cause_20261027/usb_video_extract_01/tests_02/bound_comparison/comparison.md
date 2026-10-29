# Relevé hors carte des journaux vidéo/UTNA

Ces valeurs sont extraites des journaux fournis ; elles ne qualifient ni le timing, ni une énumération USB HS.

| Build | Capture cohérente | Durée hôte vidéo (ms) | Delta images modulo 2³² | Sommes vidéo successives |
|---|---|---:|---:|---|
| r19 | True | 1600 | 96 | 0x1ff8f800, 0x1ff8f800, 0x1ff8f800, 0x1ff8f800, 0x1ff8f800 |
| candidate | True | 1600 | 0 | 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000 |

| Build | Phase | Heure hôte écriture (ms) | Séq. | En-tête ID/version/cmd | ACK idle | Armed | Ticks | RX error cycles | Bus-reset fronts | SOF cycles | TX stall cycles |
|---|---|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| r19 | ARM | 1200 | 1 | 0x55544e41/0x1/0x1 | True | False | 0 | 0 | 0 | 0 | 0 |
| r19 | DISARM | 1400 | 2 | 0x55544e41/0x1/0x6 | True | True | 12000000 | 130 | 150 | 160 | 170 |
| r19 | STOPPED | 1500 | 3 | 0x55544e41/0x1/0x2 | True | False | 12000001 | 130 | 150 | 160 | 170 |
| r19 | STABLE | 1600 | 4 | 0x55544e41/0x1/0x2 | True | False | 12000001 | 130 | 150 | 160 | 170 |
| candidate | ARM | 1200 | 1 | 0x55544e41/0x1/0x1 | True | False | 0 | 0 | 0 | 0 | 0 |
| candidate | DISARM | 1400 | 2 | 0x55544e41/0x1/0x6 | True | True | 12000000 | 130 | 150 | 160 | 170 |
| candidate | STOPPED | 1500 | 3 | 0x55544e41/0x1/0x2 | True | False | 12000001 | 130 | 150 | 160 | 170 |
| candidate | STABLE | 1600 | 4 | 0x55544e41/0x1/0x2 | True | False | 12000001 | 130 | 150 | 160 | 170 |

Les heures hôte précèdent chaque écriture MMIO ; elles ne datent pas exactement le front FPGA de capture. ARM contient l’état avant effacement. Les champs après DISARM appartiennent à une fenêtre armée, pas à toute la vie du FPGA.


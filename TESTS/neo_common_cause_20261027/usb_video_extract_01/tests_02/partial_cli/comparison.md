# Relevé hors carte des journaux vidéo/UTNA

Ces valeurs sont extraites des journaux fournis ; elles ne qualifient ni le timing, ni une énumération USB HS.

| Build | Capture cohérente | Durée hôte vidéo (ms) | Delta images modulo 2³² | Sommes vidéo successives |
|---|---|---:|---:|---|
| r19 | False | 1200 | 72 | 0x1ff8f800, 0x1ff8f800, 0x1ff8f800, 0x1ff8f800 |

| Build | Phase | Heure hôte écriture (ms) | Séq. | En-tête ID/version/cmd | ACK idle | Armed | Ticks | RX error cycles | Bus-reset fronts | SOF cycles | TX stall cycles |
|---|---|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| r19 | ARM | 1200 | 1 | 0x55544e41/0x1/0x1 | True | False | 0 | 0 | 0 | 0 | 0 |
| r19 | DISARM | 1400 | 2 | 0x55544e41/0x1/0x6 | True | True | 12000000 | 130 | 150 | 160 | 170 |

Les heures hôte précèdent chaque écriture MMIO ; elles ne datent pas exactement le front FPGA de capture. ARM contient l’état avant effacement. Les champs après DISARM appartiennent à une fenêtre armée, pas à toute la vie du FPGA.

- r19: STOPPED: missing command or complete repeated bank
- r19: STABLE: missing command or complete repeated bank
- r19: Protocol capture incomplete
- r19: Missing/duplicate overall completion marker
- r19: Unexpected command order/phase
- r19: Unexpected bank order/phase
- r19: POST_USB: incomplete video/control sample

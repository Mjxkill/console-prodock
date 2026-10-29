# Sémantique du timeout TX UART, lecture seule

Le résultat `../warm_mode1_20261027_094017/result.json` prouve un reset R19
après la trame, témoin conservé après ouverture puis effacé avant fermeture.
Sur R21, write a accepté huit octets, mais out_waiting est resté non nul
pendant deux secondes. Sa valeur n'a pas été journalisée. Réception inconnue :
ce n'est pas une preuve d'inefficacité du reset. R19 a été restauré et vérifié.

Le host indique 7.0.0-38-generic, ttyUSB1 lié à ftdi_sio. Les fichiers C/H
ci-joints proviennent de Linux tag v7.0 ; ils ne sont pas une reconstruction
du module Ubuntu chargé. Sources officielles :
https://github.com/torvalds/linux/tree/v7.0/drivers/usb/serial.

PySerial POSIX implémente out_waiting via TIOCOUTQ. USB-serial générique
compte la FIFO du pilote et les octets d'URB en vol, pas la FIFO UART
physique. Sa fermeture annule les URB write et vide la FIFO host. Sous ce
contrat, les données restant côté host ne survivent pas au dernier close ;
les octets déjà acceptés par le périphérique restent une question distincte.
PySerial close appelle os.close, sans purge vendor explicite.

L'ouverture FTDI envoie RESET_SIO au canal. Le protocole prévoit purge RX/TX
et arrêt du flow-control, mais le pilote ne vérifie pas le résultat de la
requête. Une ouverture réussie ne prouve donc pas l'exécution de cette purge
par le firmware Sipeed. Ce firmware n'a pas été lu ni identifié ici.

reset_output_buffer appelle tcflush(TCOFLUSH) ; ne pas l'assimiler sans preuve
à une purge firmware. Aucune nouvelle trame, réouverture, requête vendor,
reset USB ou manipulation de carte n'a été faite par le sous-agent. La
prochaine observation doit séparer file host, fin d'URB et état du pont,
sans déclarer réception sur le seul retour huit octets de write.

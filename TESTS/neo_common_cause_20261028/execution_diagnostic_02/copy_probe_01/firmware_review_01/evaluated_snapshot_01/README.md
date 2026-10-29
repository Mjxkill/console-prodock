# Firmware COPY565 prêt, essai matériel réservé à root

Binaire928B : build_01/microdma.bin, SHA
4d3b91ee5fd7aae44abd7d55ab712c24f78167ec1ac318f7a9a21aea000a8684.
Code à0xa0004000, fin exclusive0xa00043a0, limite0xa0005000 (4096B).
Journal512B à0xa0006000, donc aucun chevauchement. Scratch128B inchangé :
0x12000000..0x1200007f. Aucun changementRTL ou bitstream, aucune carte utilisée.

Le CPU conserve toutes les gardes BIN02, ses32stores de motif et ses32loads
avant/aprèsTARGET. Il envoie ensuite COPY565, attend done2 ET busy/full0,
vérifie32mots : octets32..63 copiés depuis0..31 ; les96autres octets inchangés.
Il retourne au parkingROM et conserve les codes d’erreur/formatjournal MD12.

Seuls8mots binaires diffèrent de BIN02 : offsets696/700 pour comparer le motif
source, puis896/900/904/908/916/920 pourle paquetCOPY. Toutes les autres données,
instructions, gardes et adresses restent identiques. source.diff et listing
permettent la revue. Le paquet extrait du binaire et celui réellement envoyé
par l’interpréteur RV32 sont identiques au paquet du banc RTL quatrecasPASS.

## Preuves et limites

-16cas RV32 protégés PASS : gardes, interruptions/trap,32comparaisons, délais,
done2maisbusy1, mauvaisretour, écriture manquante, canaris, accès horsscratch.
-6contre-tests complémentaires du modèle PASS après correction isolée : stride
nonaligné32, source nonalignée, source≥1GiB, réservé, deux extentsvides légaux.
-14cas du décodeur COPY PASS. Journal incomplet = mémoire nonobservée.
-4cas RTL complets déjàPASS : deuxhorloges/phases saines avec1lecture native,
1retour et1écriture32B, puis deux contrôles négatifs de readiness.

La contre-revue a trouvé des limites du modèle livré par DeepSeek : il
acceptait certains descripteurs malalignés, ne terminait pas le rejet et
rejetait les extentsvides. model_review.patch les corrige, les preuves avant/
après restent visibles. Le firmware et son SHA n’ont pas changé. Le modèle
reste limité aux rectangles disjoints ; il ne prétend pas remplacer la
sémantique complète de memmove du GPU ni simuler le PHY ou l’AE350 réel.

ANALYSIS.md est le rapport original du modèle, conservé ; README.md et le
manifeste décrivent la version revue. La mission réelle a duré78,97s,
11requêtes/16outils ; ses processus sont terminés, audit sansorphelin.

## Lecture du résultat

Utiliser decode_copy.py, pas le décodeur CLEAR. MD12 seul n’identifie pas
l’opération : le contrôleur doit lier le journal au SHA exact de ce firmware.
Un succès COPY qualifiera uniquement ce contrôle128B sur ce routage. Un échec
n’accusera pas automatiquement le staging partagé : COPY utilise aussi un
retour de lectureGPU absent duCLEAR. Garder captures avant/après, watchdog et
restaurationR19. Ce dossier ne contient aucune commande de programmation.

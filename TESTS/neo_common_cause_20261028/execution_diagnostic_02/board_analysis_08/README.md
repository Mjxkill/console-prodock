# MD13 réel : CLEAR0 valide avant le rejet COPY0

Root a exécuté le firmware1020B SHA5171a15d… sur R19 exact, sans nouveau
bitstream expérimental. Les empreintes brutes figurent dans facts.json.
CLEAR0 termine à done2/rejected0 ; COPY0 termine à done3/rejected1. Le
programme s’arrête phase10/résultat−5, après cette completion d’erreur.
Le contrôleur rapporte restauration R19 réussie, sans erreur de procédure.

Le journal compte32/32/0comparaisons : contrôle seed et TARGET terminés,
aucune image CPU après COPY. Aucun état de mémoire final n’est déduit.
La validité de cible est attestée au front de validation CLEAR selon le RTL,
pas directement mesurée comme signal. Une perte ultérieure de target_valid
et un refus interne COPY ont exactement les mêmes CSR dans les contre-tests.
La séquence seule ne distingue pas ces deux hypothèses.

Le prochain essai ne conserve PAS le préfixe CLEAR0 : il revient au MD12
COPY vide928B déjà testé et ne change que w1 source12000000→12000020.
La base source devient identique à la destination, strides32 égaux. Dans
le RTL cela rend faux le terme de refus overlap&&(base_diff||stride_diff),
même si overlap vaut1. Les autres validations restent actives, dont src_end.
Le changement modifie également src_end de32octets : une réussite éventuelle
ne prouverait pas à elle seule une panne du comparateur d’overlap.
Le contrôle ne requiert aucun transfert selon le contrat, sans observation
physique des requêtes natives. Root garde seule la décision et la carte.

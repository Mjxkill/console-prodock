# Fiche de test — construction isolée FIFO FF Neo

Objectif : construire un candidat où seuls les deux stockages de commandes SDPB deviennent des bascules, sans resynthétiser l'application, changer les connexions, contraintes ou référence Pro Dock.

Environnement : Linux hôte, Python3 ; GowinSynthesis `40bd2e0028c32931e2608b89ca51f6f4cf2fe66883509bb7eff379f928447899`, bibliothèque fournisseur `7db6e9953af24f1233dbc8f58352a1673e91d01bb69656a16ae893a68089f85d`. Les entrées/base exactes sont épinglées dans recipe.py et stage_02/stage.json. Source helper unique SHA `7ec21ef5f8c8f9ad7f548c702e6954919e089f4d7ebe0b8e76d6da1425ba2c92`.

1. Tests natifs de construction sur le VG réel : 3/3 PASS en10,194s. Delta autorisé/inversion byte exacte ; refus de READ_MODE différent ; refus de primitive inattendue. Aucun matériel.
2. `stage_01` : échec avant synthèse, AF_NETLINK interdit par sandbox puis licence hostid refusée. Journaux et reçu conservés. Aucune conclusion RTL tirée de cet échec.
3. `stage_02` hors sandbox autorisé : un GowinSynthesis PID1141855, exit0 en12,942310763988644s. Une seconde tentative de lancement root concurrente a été refusée par le verrou avant lancement : événement de coordination, pas échec du FPGA. Aucun second Gowin ni relance cachée.
4. Helper VG SHA `dedea942988183dc6cfdae65c570d51eae3e55072a4c056f43b1763734282d89`. Interface douze ports conservée. 4128DFFRE,3092LUT4,969LUT3,52LUT2,unVCC/unGND/unGSR par instance ; GSR.GSRI=VCC. Aucune primitive RAM/SDPB/SP/DP/ROM dans le helper.
5. Assemblage SHA `4cae016631ebea6989e54e0c48752f4fbfacaa53d7a96fa206549eab3cd356e8`. Deux cellules SDPB remplacées, douze defparam retirés ; noms/ports/adresses/horloges/reset et toutes autres cellules inchangés. Inversion du texte intégral de l'application PASS. Les modules ajoutés sont uniquement ceux du helper synthétisé. Détails assembly_01/assembly.json.

La comparaison comportementale contre SDPB fournisseur, y compris la variante réelle cmem, relève du dossier mapping_01. La qualification mapped doit être fournie avant finalize.py. Les tests réussis ne prouvent ni le timing du futur placement ni une correction de la panne Neo. Aucun PNR, chargement FPGA ou accès matériel effectué ici. Aucune entrée source commune ou référence Pro Dock modifiée.

Contrôle structurel complémentaire, demandé après timeout de simulation mapped : HELPER_GRAPH.json,8244cellules4113LUT, profondeurLUTmax6 ; zérocycle combinatoire, zéropilote multiple, zéroentrée nonpilotée. Deux contre-exemples injectés détectés. Durée7,303149712039158s. Ce contrôle ne remplace pas la qualification dynamique et ne fait pas disparaître son premier timeout.

Le probe ultérieur a discriminé le coût de simulation du bus words[4095:0] : renommage bijectif simulationseule en4096nets scalaires, cellules/paramètres identiques, modèle fournisseur intégral, progression à#1ns en2,12s contre timeout90s avantt0 sur grandbus. Ni GSR, ni helper, ni VG destiné au PNR ne sont modifiés. Preuve inverse et campagne complète sous la responsabilité mapping_01 ; attendre son reçu final.

Qualification finale indépendante : mapping_01/MAPPED_QUALIFICATION.json SHA a1e7ae982c080c6864dcc4f9bdf0e1fa37e792c1c94df6ef1f74dd7edbef662e ; six cas mappés PASS en41,50298618385568s avec bibliothèque Gowin intégrale et scalarisation simulationseule inverse exacte. Les8192 références remplacées reviennent exactement au SHAoriginal du helper. Pas de modèle LUT allégé utilisé pour ce PASS final. Vérification INIT0/4128FF/CLK/reset/GSRVCC faite par mapping. Les timeouts antérieurs restent conservés.

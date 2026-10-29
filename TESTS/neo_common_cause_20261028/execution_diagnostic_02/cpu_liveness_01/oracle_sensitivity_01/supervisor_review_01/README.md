# Contre-tests des oracles : résultat superviseur

Six programmes Verilator ont été réellement compilés et exécutés dans la
boîte isolée. Le contrôle sain termine32lectures ; les cinq mutations sont
détectées par une assertion spécifique, pas par un échec de compilation :

| Mutation externe | Résultat observé |
|---|---|
| Retour bit0 inversé | CPU_DATA index0 |
| Retour bit128 inversé | CPU_DATA index4 |
| Aucun retour de lecture émis | CPU progress timeout interne au banc |
| MasqueGPU bit0 inversé | ENDPOINT unexpected CLEAR footprint |
| Adresse native bit23 inversé | ENDPOINT address outside scratch128B |

Correction de vocabulaire : XOR00800000 sur l’adresse04800008 produit
04000008, donc byte12000020 devient10000020 (**moins**32MiB). Le contrat et
le commentaire du modèle disaient plus32MiB ; le test reste un refus des bits
d’adresse hauts, sans enroulement silencieux. La sortie originale est conservée.

Les sourcesRTL et les oracles ne sont pas modifiés ; seules des copies
jetables de connexions/terminal sont mutées. Les données et commandes réelles
sont comparées par le banc protégé. Le modèle a produit234lignes de code revu.

Mission MiniMax interrompue par sa limite18étapes avant le rapport et le dernier
appel officiel de tests. Son état reste INSUFFICIENT_EXECUTION_EVIDENCE, sans
score technique de livraison complète. Il avait exécuté les tests via exec ;
le superviseur a ensuite exécuté les deux commandes fixes sur les derniers
octets, toutes PASS. Ce rapport est de Codex, pas attribué à MiniMax. Aucun
rejeu artificiel pour changer le statut de la mission. Logs et preuves conservés.

Ce résultat valide la sensibilité de ces oracles à cinq fautes choisies ; il ne
localise aucune panne physique et n’est pas une preuve exhaustive de la DDR.

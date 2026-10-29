# Readback R19 : ce qui est établi et ce qui reste ouvert

Le lecteur ILM a terminé32/32charges, cache désactivé, sans exception. Les128B
restent exactement le motif initial : les8mots centraux n’ont pas été effacés,
les24mots de sentinelles restent intacts. Les snapshots NGDB sont frais et le
GPU reste done1/busy1, opcode1c, ext_active1, blitter SETUP ; les compteurs
errors/lost/rejected restent0. La restauration R19 est confirmée. Ceci ne prouve
pas que la DDR entière, l’arbitre ou tous les chemins GPU sont fonctionnels.

## Comparaison aux scénarios logiciels bornés

- Cas1, commande native constamment indisponible : incompatible avec32lectures
  acceptées et rendues pendant cette même fenêtre sous les hypothèses du modèle.
- Cas2, GPU VALID sélectionné et écriture constamment indisponible : incompatible
  avec cette fenêtre de lectures dans ce modèle d’arbitre. Le signal réel n’a pas
  été capturé, donc on ne déduit pas lequel de ces termes est absent.
- Cas4, file arbitre restant pleine sans retour : incompatible avec les32lectures
  pendant toute la fenêtre. Une file temporairement pleine n’est pas éliminée.
- Cas3, seul retour d’acceptation GPU perdu après écritures correctes : notre
  scénario écrit bien la couleur. Le motif intact contredit cette version simple,
  mais n’exclut pas une acceptation apparente sans effet, mauvaise adresse, masque
  erroné ou problème situé au-delà du terminal DDR idéal utilisé en simulation.
- Cas5/7, requête GPU absente de l’arbitre : compatible avec CPU32PASS et motif
  intact. Compatibilité ne signifie pas preuve ; v1_pending, nativeVALID/READY
  ne sont pas directement exposés par le snapshot R19.
- Cas6, retours CPU constamment retenus : incompatible avec le lecteur terminé ;
  une défaillance sporadique hors de cette fenêtre n’est pas éliminée.

## Un seul prochain test

CLEAR avec flags0, après le même TARGET. Le chemin passe par décodage,
RECT_BOUNDS, RECT_CLIP, RECT_SETUP, puis FINISH sans aucune requête DDR GPU.
L’échec orientera vers l’amont de cette bifurcation ou la chaîne de completion ;
il ne prouvera pas une faute DDR puisque cette commande ne la sollicite pas.
Le succès montrera que la branche de contrôle termine, en laissant ouverts
les états suivants, la préparation/passage de la requête native, le retour
acceptation et la DDR. Il ne permettra pas d’identifier seul le composant.

Paquet et tests dans ../zero_clear_01/DELIVERY.json. Aucun nouveau bitstream,
aucune action matérielle de cet agent. Les observations de mémoire sont32loads
séquentiels, non un instantané atomique ; le trafic CPU peut changer l’arbitrage.

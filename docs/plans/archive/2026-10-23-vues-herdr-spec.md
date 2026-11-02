# Vues Herdr avant captures

Mission autorisée : lot vues, priorité 1 complète, priorité 2 limitée à Colonnes et Courtier, une demande de fusion. Budget de trois heures.

## Comportement attendu

Les vues Accueil, Décisions et Tableau agent partagent les mêmes attentes : validations, permissions du terminal, blocages/go/questions, propositions, signalements, documents à lire/décider et fusions. Les compteurs distinguent propriétaire et agent ; une lecture compte pour un document. Une décision liée explicitement à une validation ou une fusion disparaît quand cet objet est résolu. Un rapport plus récent sans lien ne résout rien. Les propositions techniques sans type mémoire/skill ou marquées comme essais ne sont pas des décisions.

Accueil montre trois fusions récentes et le total, avec des lignes adaptées à la largeur et un statut inconnu explicite. Courtier utilise deux lignes par appel (résultat sur la seconde), regroupe les appels identiques et réserve la priorité aux refus du jour. Tokens conserve le tableau large et empile les détails en dessous de 100 colonnes. Les états vides invitent brièvement, sans chemin personnel. Colonnes utilise toute la largeur, compacte les sections vides et les livraisons lorsque la hauteur manque.

## Architecture et limites

Réutiliser `decisions()` comme source commune des vues, sans modifier le courtier, les autorisations ni l’exécution des validations. La résolution reste une lecture d’état. Les liens documentaires sont explicites : `Décision liée : validation:<numéro>` ou `Décision liée : fusion:<projet>/<sujet>` ; état manuel `Décision résolue : <motif>`. Un lien invalide reste en attente.

Le jeu public réutilise le constructeur jetable des tests et ajoute des données fictives françaises : HOME, BERGER_DIR, faux Herdr et horloge figée. Il ne charge aucune configuration installée. Le script produit les textes Accueil, Colonnes et Courtier à 140 colonnes (80 aussi pour contrôle).

## Plan et preuves

1. Ajouter `tests/vues-herdr.py` : largeur ANSI/Unicode, fusions récentes, résolutions liées et non liées, absence des sondes, compteurs, refus/groupement et livraisons ; constater les échecs.
2. Modifier les seules fonctions de collecte d’affichage dans `bin/berger`, les vues et leurs schémas. Tester les régressions puis les contrats existants.
3. Ajouter `docs/scripts/demo-vues.py`, documenter la commande et vérifier deux générations identiques dans deux dossiers jetables.
4. Conserver les références historiques des vues non modifiées ; documenter les nouveaux comportements et tester les vues révisées explicitement.
5. Jouer verify/tests/pret, relire le diff, commits courts, mise à jour depuis main, retests puis une demande de fusion avec preuves et limites.

Hors périmètre : production, authentification, droits, secrets, services extérieurs, fusion et installation. Risques : anciens rapports sans lien impossible à résoudre sûrement ; ne pas les masquer par heuristique. Hauteur insuffisante : conserver le total et le détail dans les données, limiter le texte affiché.

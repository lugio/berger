# verifier-depot lit le contenu décodé des data URI, au lieu de leur encodage base64 (spec)

Règle de go : cas 1 (une garde : la neutralité du dépôt). Go du propriétaire à inscrire sur CE fichier avant le code.
Rien de propre à un moteur ni à une installation.

## Constat (08/11/2026)

L'installation de v0.4.0 est refusée par `verifier-depot` : « docs/apercu/interface.html — nom du propriétaire ». Les 3 occurrences sont
toutes dans le texte base64 de 3 images PNG embarquées (data URI). Le nom n'est dans **aucun** contenu décodé, et hors data URI le
fichier ne le contient pas : c'est une suite de lettres tirée au hasard dans l'encodage. La CI ne le voit pas, puisqu'elle ne connaît
pas le nom du propriétaire d'une installation. Référencer le logo par un chemin (première correction) contredit l'exigence d'un aperçu
autonome (`tests/interface-logo.py`) : elle est abandonnée.

**Cause racine.** `verifier_depot` cherche les valeurs du coffre et les marques dans le texte lu tel quel. Le base64 d'une data URI
n'est pas un texte lisible : une marque courte y apparaît par hasard.

## Comportement

- Avant la recherche des valeurs du coffre et des marques, chaque `data:<type>;base64,<données>` du texte lu est remplacé par son
  **contenu décodé** (octets décodés en texte, erreurs ignorées).
- Une marque, un hôte ou une valeur du coffre **présents dans le contenu décodé** (texte encodé, métadonnées d'une image) restent
  refusés : pour ce cas, la garde devient plus stricte qu'avant.
- Un base64 **invalide** reste tel quel dans le texte : aucune exemption.
- Les **valeurs du coffre** sont cherchées dans le texte brut **et** dans le contenu décodé : une valeur faite de caractères base64,
  écrite telle quelle comme données d'une data URI, reste trouvée. Les **marques**, plus courtes, ne sont cherchées que dans le texte
  où chaque data URI est décodée : c'est là que le hasard de l'encodage les faisait apparaître. (Ajouté après la relecture du 113.)
- Rien d'autre ne change : chemins interdits, marques, exception `depot_public`, message.

## Refus

Toute exemption : un fichier n'est jamais ignoré, une data URI jamais retirée sans être lue. La garde n'est relâchée nulle part.

## Tests (rouges d'abord, dans la suite qui couvre verifier-depot)

1. Une data URI dont le base64 contient la marque par hasard, et dont le décodé ne la contient pas : propre.
2. Une data URI dont le **décodé** contient la marque : refusée.
3. La marque en clair, hors data URI : refusée.
4. Une valeur du coffre dans un décodé : refusée.
5. Un base64 invalide qui contient la marque : refusé.
6. Une valeur du coffre faite de caractères base64, écrite telle quelle comme données d'une data URI : refusée (« VALEUR DU COFFRE »).

Puis la suite complète, comme la CI.

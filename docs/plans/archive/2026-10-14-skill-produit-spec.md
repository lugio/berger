# La méthode du produit prime sur un homonyme du catalogue

Spec, 14/10/2026 (mission de master). Hors règle de go (ni secret, ni droits, ni logiciel métier, ni production, ni pare-feu, ni
appel extérieur) : décidé par le coordinateur.

## Constat

`methode(nom)` (`bin/berger`) cherche d'abord dans le **catalogue de l'installation** (`[skills] dossier`, défaut
`skills/`, ignoré par git), puis dans les **méthodes du produit** (`commun/skills/<nom>`, versionnées). Une copie
`berger` déposée au catalogue (constaté : `~/berger/skills/berger` du 08/10, différente de `commun/skills/berger`)
**masque donc la méthode versionnée** chez tout agent qui a `skills = berger` (ou une équipe `[equipes.*] skills`) :
il lit une méthode périmée, sans que rien ne le dise. La vue Catalogue, de son côté, marquait « berger (absente) » —
elle ne regardait que le catalogue.

## Comportement attendu

Ordre, du plus fort au plus faible, pour une méthode nommée dans `skills =` :
1. `skills-agent/<nom>` de l'agent (inchangé) ;
2. **`commun/skills/<nom>` du produit** ;
3. le catalogue `<skills.dossier>/<nom>`.

- Un homonyme du catalogue (même nom qu'une méthode du produit) est **ignoré** ; `berger regenerer` le dit par une
  ligne par agent concerné : `⚠ <agent> : méthode « <nom> » — celle du produit (commun/skills/<nom>) prime ;
  homonyme du catalogue ignoré : <chemin>`.
- Une méthode absente du produit vient toujours du catalogue.
- Les autres lectures suivent le même ordre : `controler_proposition` (via `methode`), la fiche Capacités (« de son
  rôle » : lien vers le produit ou le catalogue, inchangé), la vue Catalogue (une méthode du produit n'y est plus
  marquée « absente »). Le **texte** de la vue Catalogue reste identique pour le jeu de données figé (`tests/interface.py`,
  règle « octet pour octet ») : l'homonyme ignoré est signalé par `regenerer`, pas par une ligne de plus dans la vue.

## Refus

Rien de neuf : une méthode qui cite le coffre ou un motif `skills.interdits` reste refusée, quelle que soit sa source ;
une méthode absente des deux reste signalée et non donnée.

## Tests (`tests/skill-produit.py`, installation jetable)

- catalogue/berger ≠ commun/skills/berger → `.claude/skills/berger` et `.agents/skills/berger` pointent vers
  `commun/skills/berger`, et l'avertissement nomme l'agent, la méthode et le chemin ignoré (ÉCHOUE avant la correction) ;
- méthode présente seulement au catalogue → liée depuis le catalogue ;
- `skills-agent/berger` → prime sur le produit et le catalogue ;
- fiche Capacités et vue Catalogue : `berger` compté « de son rôle », jamais « absente » (même seulement au produit).

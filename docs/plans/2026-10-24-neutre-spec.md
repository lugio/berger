# Noms de logiciels métier neutralisés : spécification courte

Date : 2026-10-24. Go du propriétaire (lot court, une fusion). Le dépôt public montrait les noms réels de logiciels métier et d'un éditeur, relevés par un contrôle extérieur.

## Comportement
- Les exemples, les tests, le manuel et les specs utilisent un éditeur fictif :
  - les hôtes sont `client.editeur.example`, `depot.editeur.example` et `docs.editeur.example` ;
  - les logiciels sont `GESTEX` et `COMPTAEX` ;
  - les outils d'exemple sont `[outils.veille-editeur]` et `[outils.gestion-lecture]` ;
  - la base est `X:\EXEMPLE\base.db`, avec les vues `EX.VueProduction` et `EX.VueVersion`.
- Les motifs, les verbes et les tests restent les mêmes, sous des noms neutres.
- Dans la règle de go (`commun/REGLES.md` et ses copies), « écriture dans <éditeur> » devient « écriture dans un logiciel métier ». C'est plus large, donc le cas réel reste couvert.
- La configuration réelle d'une installation (`config.toml`, hors dépôt) n'est pas touchée.

## Garde : verifier-depot
- Une **marque privée** (`marques_privees`) est maintenant refusée même collée à un point, un tiret ou un souligné : nom d'hôte, nom d'outil composé, nom de fichier.
- Elle reste un mot : collée à une lettre ou à un chiffre, ce n'est plus elle.
- Le nom du propriétaire, le dossier personnel, les réglages des outils et les marques fixes du produit gardent la règle actuelle.
- Les noms neutralisés ne vont **pas** dans une liste de base du produit : ils y seraient republiés, même en fragments. Ils vont dans les `marques_privees` des installations, posées par le propriétaire.

## Tests
- `tests/marques-produit.py` : 4 refus nouveaux (nom d'outil composé, hôte, nom de fichier avec souligné, verbe composé) et 1 acceptation (marque prolongée d'une lettre).
- `tests/pages-publiques.py`, `tests/sql-lecture.py` et `tests/memoire-equipe.py` : les mêmes contrôles, sur les noms neutres.

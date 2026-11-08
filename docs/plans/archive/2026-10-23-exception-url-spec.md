# Spec — exception d'URL du dépôt public dans verifier-depot

## Constat
L'URL publique du dépôt porte l'identifiant du propriétaire, qui est une marque privée : `verifier-depot` refuse donc tout
document qui donne la commande de clone, et l'installation qui le contient revient en arrière.

## Comportement
- Nouveau réglage facultatif `depot_public` (config.toml) : l'URL exacte du dépôt public, `https://…/….git`.
- `verifier-depot` retire du texte les seules occurrences exactes de cette URL (casse comprise, bornées) avant de chercher
  les marques ; la recherche des valeurs du coffre se fait sur le texte complet.

## Refus (inchangés)
Toute autre mention d'une marque : seule, dans une autre URL du même compte, URL prolongée, sans `.git`, en `http`, en
majuscules ; un `depot_public` absent ou qui n'a pas la forme d'une URL de dépôt n'ouvre aucune exception.

## Tests
`tests/marques-produit.py` : deux acceptations (URL exacte, entre parenthèses) et huit refus listés ci-dessus.

Go du propriétaire : « go exception URL » (2026-10-23) — modification d'une garde.

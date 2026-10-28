# Alignement après une mise en production

## Déclaration du projet

Spec : `docs/plans/2026-10-16-alignement-spec.md`. Le projet déclare dans
`[equipes.<projet>]` ce qui doit suivre une mise en production — `alignement = ["changelog", "wiki", "memoire", "skills",
"versions"]`, `prod_outil` (l'action de mise en production), `compte_rendu_outil` et `version_servie_outil` (des lectures),
`wiki` (son arborescence au wiki) et `[equipes.<projet>.modules]` (chemins → pages et skills à relire) ; modèle commenté
dans `config.exemple.toml`. Une déclaration fautive arrête le courtier au chargement (élément inconnu, action ou lecture
introuvable, `wiki` vide, avec `..` ou hors des zones de l'outil wiki — `[wiki] lecture`, défaut `wikijs-lecture` —, `relire`
qui n'est pas `wiki:` / `skill:` / `memoire:`) ; sans ces lignes, rien ne change. Test : `tests/alignement.py`.

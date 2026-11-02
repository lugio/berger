"""Le socle commun de Berger (modulaire, lot 1).

config → transport → affichage → agents → herdr → lectures : chaque module ne dépend que de ceux d'avant.
Ce que les modules de `vues/` (puis `commandes/`, `moteurs/`) ont le droit d'employer est la liste nommée de `noyau/api.py`.
Un noyau qui ne charge pas arrête `berger` en nommant le fichier : il n'est pas écartable (spec docs/plans/2026-10-27-modulaire-spec.md)."""

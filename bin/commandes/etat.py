"""Commandes « etat » (modulaire, lot 3 bis) : l'état d'ensemble et les écritures en attente (lecture seule).

Code déplacé de bin/berger (lot 3 bis) : aucun comportement changé. Contrat : FAMILLE, VERBES {verbe: fonction(args, prive=False)}, AIDE, DROITS.
Une fonction de verbe rend NotImplemented quand la forme demandée n'est pas la sienne (« commande inconnue » comme avant).
Ce module n'emploie que l'API du noyau et la bibliothèque standard : voir commandes/__init__.py."""


# ─── Les verbes (corps déplacés de bin/berger, inchangés) ───

def verbe_etat(args, prive=False): etat(en_json="--json" in args)

def verbe_validations(args, prive=False): validations(en_json="--json" in args)


FAMILLE = "etat"
VERBES = {"etat": verbe_etat, "validations": verbe_validations}
AIDE = {
    "etat": "berger etat [--json]                vue d'ensemble de tous les agents (--json : ses données)",
    "validations": "berger validations [--json]         écritures demandées par les agents, en attente de ta décision",
}
DROITS = {v: {"prive": False, "cas_go": None} for v in VERBES}

"""Les dictionnaires partagés des vues, moteurs et familles de commandes écartés (modulaire, lot 3 bis).

Aucun import, volontairement : bin/commandes/ et bin/moteurs/ les chargent sans lire config.toml. Remplis par le cœur (VUES, VUES_REFUSEES : charger_vues)
et par bin/moteurs/ et bin/commandes/ (MOTEURS_REFUSES, COMMANDES_REFUSEES) ; lus par `berger etat` (noyau/registre.py)."""

VUES, VUES_REFUSEES = {}, {}                          # type -> module de vue ; type -> « Type: message »
MOTEURS_REFUSES, COMMANDES_REFUSEES = {}, {}            # {fichier: « Type: message »}


class Refus(ValueError):
    """Le refus d'usage voulu d'un verbe (entrée invalide, mauvaise forme) : seul ce que le verbe LÈVE par `Refus` passe tel quel, sans écarter sa famille
    (et seulement si la famille le déclare dans PASSE). Une ValueError ordinaire est un défaut : elle écarte la famille."""

"""Les dictionnaires partagés des vues, moteurs et familles de commandes écartés (modulaire, lot 3 bis).

Aucun import, volontairement : bin/commandes/ et bin/moteurs/ les chargent sans lire config.toml. Remplis par le cœur (VUES, VUES_REFUSEES : charger_vues)
et par bin/moteurs/ et bin/commandes/ (MOTEURS_REFUSES, COMMANDES_REFUSEES) ; lus par `berger etat` (noyau/registre.py)."""

VUES, VUES_REFUSEES = {}, {}                          # type -> module de vue ; type -> « Type: message »
MOTEURS_REFUSES, COMMANDES_REFUSEES = {}, {}            # {fichier: « Type: message »}


class Refus(ValueError):
    """Le refus d'usage voulu d'un verbe (entrée invalide, mauvaise forme) : seul ce que le verbe LÈVE par `Refus` passe tel quel, sans écarter sa famille
    (et seulement si la famille le déclare dans PASSE). Une ValueError ordinaire est un défaut : elle écarte la famille."""


class ErreurService(Exception):
    """Ce qui sort du CŒUR par un service d'action (noyau/actions.py, lot 4a) : l'exception d'origine est gardée en cause (`raise … from e`). Une famille qui
    la déclare dans PASSE n'est pas écartée pour une panne du geste ; commandes.lancer ressort l'exception d'origine, telle qu'avant le déplacement.
    Une erreur DANS la famille, hors service, n'est pas enveloppée : elle écarte la famille, nommée ; deux exceptions : l'endroit où un verbe lit et décode
    l'entrée que le cœur lui passe sur stdin (messages : delegation-suivi, echange, renvoi n° 89), dont l'erreur de lecture ou de décodage sort telle qu'avant,
    et l'appel d'une lecture des équipes (equipes : `_lire`, renvoi n° 93), dont l'erreur, venue d'une donnée d'équipe illisible, sort telle qu'avant. `origine` (lot 4b) : l'exception d'origine, lisible par
    une famille (qui n'a pas droit aux attributs spéciaux comme __cause__) quand l'ancien corps de son verbe attrapait ce que levait le geste."""

    def __init__(self, texte, origine=None):
        super().__init__(texte); self.origine = origine

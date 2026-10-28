"""Le registre des vues et des écarts, et les données qu'il enveloppe (modulaire, lot 3 bis).

Code déplacé de bin/berger : aucun comportement changé. VUES / VUES_REFUSEES sont remplis par le cœur (charger_vues) ; MOTEURS_REFUSES et
COMMANDES_REFUSEES le sont par bin/moteurs/ et bin/commandes/ (mêmes dictionnaires, définis dans noyau/ecarts.py pour que `berger etat` les lise sans importer ces paquets)."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata
import importlib.util
import shutil as _sh, textwrap
from pathlib import Path
from noyau.config import *
from noyau.transport import *
from noyau.affichage import *
from noyau.agents import *
from noyau.herdr import *
from noyau.lectures import *


from noyau.ecarts import VUES, VUES_REFUSEES, MOTEURS_REFUSES, COMMANDES_REFUSEES, Refus   # les dictionnaires, sans import lourd (voir ecarts.py)


SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"      # bin/schemas


def enveloppe(nom, schema, d):
    """{vue, version, genere, donnees} : la version est celle du schéma (x-version)."""
    try: version = json.loads(Path(schema).read_text()).get("x-version", 1)
    except (OSError, ValueError): version = None
    return {"vue": nom, "version": version, "genere": datetime.datetime.now().isoformat(timespec="seconds"), "donnees": d}


def liste_vues():
    """berger vues --json : ce que charger_vues() sait de chaque vue."""
    return {"vues": [{"type": t, "titre": m.TITRE, "icone": m.ICONE, "onglet": m.ONGLET, "ordre": m.ORDRE,
                      "donnees": hasattr(m, "donnees")} for t, m in sorted(VUES.items(), key=lambda x: (x[1].ORDRE, x[0]))],
            "ecartees": [{"vue": n, "cause": e} for n, e in sorted(VUES_REFUSEES.items())]}


def ecartes_moteurs():
    """Moteurs écartés pour `berger etat` : [{moteur, cause}]."""
    return [{"moteur": n, "cause": e} for n, e in sorted(MOTEURS_REFUSES.items())]


def ecartes_commandes():
    """Familles de commandes écartées pour `berger etat` : [{commandes, cause}]."""
    return [{"commandes": n, "cause": e} for n, e in sorted(COMMANDES_REFUSEES.items())]


__all__ = ('VUES', 'VUES_REFUSEES', 'MOTEURS_REFUSES', 'COMMANDES_REFUSEES', 'Refus', 'SCHEMAS', 'enveloppe', 'liste_vues', 'ecartes_moteurs', 'ecartes_commandes',)

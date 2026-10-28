#!/usr/bin/env python3
"""Démonstration : installations indépendantes, sorties stables et bornées."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import re
import importlib.util
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('demo', SRC / 'docs/scripts/demo-vues.py')
demo = importlib.util.module_from_spec(spec); spec.loader.exec_module(demo)
a, b = demo.generer(), demo.generer()
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + texte)


dire(a == b and len(a) == 6, 'six rendus identiques dans deux installations jetables')
for n, t in a.items():
    w = int(n.rsplit('-', 1)[1])
    largeur = lambda l: sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in l)
    dire(all(largeur(l) <= w for l in t.splitlines()), n + ' respecte la largeur')
    dire('/home/' not in t and '/tmp/' not in t and '\x1b' not in t and 'ERREUR' not in t, n + ' sans chemin hôte ni erreur')
for w in (80, 140):
    c, accueil = a[f'courtier-{w}'], a[f'accueil-{w}']
    dire('en service' in c and 'ARRÊTÉ' not in c, f'courtier actif dans la démo à {w}')
    dire('Équipe demo' in accueil and 'ÉQUIPE DEMO' not in accueil, f'titre équipe respecté à {w}')
    dire('SAUVEGARDE' in c and c.index('ÉCRITURES À VALIDER') < c.index('SAUVEGARDE') < c.index('archive envoyée'), f'sauvegarde dans sa section à {w}')
for n, t in a.items():
    dire('(s)' not in t and not re.search(r'\b1 (?:propositions|écritures|documents|refusés|appels|agents|blocages|lectures|fusions|questions)\b', t), n + ' accords corrects')
dire('×4'  in a['courtier-140'] and 'action absente' in a['courtier-140'], 'courtier fictif : refus et appels regroupés')
dire('fusionnés (6)' in a['accueil-140'], 'accueil fictif : historique de fusions')
with tempfile.TemporaryDirectory() as t:
    p = Path(t) / 'existant'; p.mkdir(); (p/'temoin').write_text('conserver')
    r = subprocess.run([sys.executable, str(SRC/'docs/scripts/demo-vues.py'), str(p)], capture_output=True, text=True)
    dire(r.returncode != 0 and (p/'temoin').read_text() == 'conserver', 'sortie existante refusée sans écrasement')
print(f'---- {ko} échec(s)')
sys.exit(bool(ko))

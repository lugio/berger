#!/usr/bin/env python3
"""La porte communautaire reste légère et détecte réellement les fichiers invalides."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import contextlib
import io
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import patch

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + texte)


def jouer(mutation=None):
    sortie = io.StringIO()
    original_run = subprocess.run
    original_read = Path.read_text
    original_file = Path.is_file
    appels = []

    def commande(args, *a, **kw):
        appels.append(args)
        if args[:4] != ['git', '-C', str(SRC), 'check-ignore']:
            raise AssertionError('sous-processus inattendu dans la porte communautaire')
        return original_run(args, *a, **kw)

    def lire(p, *a, **kw):
        if mutation == 'licence' and p == SRC / 'LICENSE':
            return 'Licence invalide\n'
        return original_read(p, *a, **kw)

    def present(p):
        if mutation == 'absent' and p == SRC / 'SECURITY.md':
            return False
        return original_file(p)

    code = 0
    with contextlib.redirect_stdout(sortie), patch.object(subprocess, 'run', commande), \
            patch.object(Path, 'read_text', lire), patch.object(Path, 'is_file', present):
        try:
            runpy.run_path(str(SRC / 'tests/communaute.py'), run_name='__main__')
        except SystemExit as e:
            code = e.code
        except AssertionError as e:
            code = 1
            sortie.write(str(e))
    return code, sortie.getvalue(), appels


code, texte, appels = jouer()
dire(code == 0, 'porte communautaire réussie sans sous-processus de rejeu')
dire(len(appels) == 9 and all(a[:4] == ['git', '-C', str(SRC), 'check-ignore'] for a in appels),
     'seuls les neuf contrôles Git légers sont exécutés, aucun clone frais')
dire(sum(l.startswith('ok    ') for l in texte.splitlines()) == 30,
     'les trente contrôles de fichiers communautaires sont toujours exécutés')
code, texte, _ = jouer('licence')
dire(code == 1 and 'ÉCHEC licence MIT complète' in texte,
     'témoin : contenu de licence invalide réellement refusé')
code, texte, _ = jouer('absent')
dire(code == 1 and 'ÉCHEC fichier communautaire présent : SECURITY.md' in texte,
     'témoin : fichier communautaire absent réellement refusé')
print(f'==== {ko} échec(s)')
sys.exit(1 if ko else 0)

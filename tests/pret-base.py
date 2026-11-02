#!/usr/bin/env python3
"""tests/pret.sh compare à une base EXPLICITE quand on la donne (CI : branche cible de la PR), sans repli silencieux sur origin/main."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
from pathlib import Path
import os
import subprocess
import tempfile

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok
    print(('ok    ' if ok else 'ÉCHEC ') + texte)


def git(dossier, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_AUTHOR_NAME='essai', GIT_AUTHOR_EMAIL='essai@exemple.invalid',
               GIT_COMMITTER_NAME='essai', GIT_COMMITTER_EMAIL='essai@exemple.invalid')
    return subprocess.run(['git', '-C', str(dossier), *args], capture_output=True, text=True, env=env)


def pret(depot, base=None):
    env = {k: v for k, v in os.environ.items() if k != 'BERGER_PRET_BASE'}
    if base is not None:
        env['BERGER_PRET_BASE'] = base
    return subprocess.run(['bash', str(depot / 'tests/pret.sh')], capture_output=True, text=True, env=env)


with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR') or None) as t:
    d = Path(t) / 'depot'
    (d / 'tests').mkdir(parents=True)
    git(d, 'init', '-q')
    (d / 'tests/pret.sh').write_text((SRC / 'tests/pret.sh').read_text())
    (d / 'tests/suites.sh').write_text('')
    (d / 'tests/tout.sh').write_text('')
    (d / 'tests/_gabarit.py').write_text('')                           # pour que le motif tests/*.py de pret.sh trouve un fichier
    git(d, 'add', '-A'); git(d, 'commit', '-qm', 'base')
    git(d, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
    (d / 'bin').mkdir(); (d / 'bin/outil').write_text('echo x \n')       # code + espace final, sans test ni doc
    git(d, 'add', '-A'); git(d, 'commit', '-qm', 'code seul')
    git(d, 'update-ref', 'refs/remotes/origin/cible', 'HEAD')           # la branche cible contient déjà ce commit
    (d / 'LISEZMOI').write_text('seulement un fichier sans lien avec du code\n')
    git(d, 'add', '-A'); git(d, 'commit', '-qm', 'neutre')
    r = pret(d)
    dire(r.returncode != 0 and 'sans test' in r.stdout, 'par défaut : base origin/main (le code sans test est vu, rouge)')
    r = pret(d, 'origin/cible')
    dire(r.returncode == 0 and r.stdout.startswith('ok pret : 1 fichier(s)'),
         'base explicite = branche cible : seul le diff de la PR est jugé (1 fichier), vert')
    r = pret(d, 'origin/absente')
    dire(r.returncode != 0 and 'pas de origin/absente' in r.stdout, 'base explicite absente : échec nommé, aucun repli sur origin/main')
    for douteuse in ('--option', 'a b', 'x;echo y', ''):
        r = pret(d, douteuse) if douteuse else None
        if r is not None:
            dire(r.returncode != 0 and 'refusée' in r.stdout, f'base explicite douteuse « {douteuse} » refusée')
print(f'==== {ko} échec(s)')
raise SystemExit(1 if ko else 0)

#!/usr/bin/env python3
"""Propriétaire seulement, hors bac sans AF_UNIX : python3 tests/sonde-herdr-argv.py <agent> [moteur].
BERGER_DIR doit viser l'installation qui possède l'agent. Charge le code de CETTE copie.
Envoie un message d'essai réel à un agent au repos ; aucune installation ou relance.
Ne prouve que l'acceptation par Herdr et les argv réels du processus émetteur.
RECETTE RÉELLE : connectée au VRAI Herdr EXPRÈS (n'importe pas tests/_herdr_isole.py). Les suites de tests/suites.sh, elles, sont isolées.
"""
import os
from pathlib import Path
import secrets
import string
import subprocess
import sys

LANCEUR = '''import os,runpy,sys
from pathlib import Path
texte=sys.stdin.buffer.read().decode('utf-8')
if texte.encode() in Path('/proc/self/cmdline').read_bytes():raise SystemExit('échec argv')
g=runpy.run_path(sys.argv[1],run_name='sonde')
a=sys.argv[2];m=sys.argv[3] if len(sys.argv)>3 else next(iter(g['herdr_ids'](a).get('agents',{})),None)
p=g['herdr_ids'](a).get('agents',{}).get(m)
if not p or not g['au_repos'](p):raise SystemExit('agent absent ou occupé')
if g['HERDR']!='herdr':raise SystemExit('Herdr réel requis')
g['parler'](a,texte,moteur=m,de=False)
print('ok socket Herdr réelle ; texte absent des argv du noyau')
'''


def main():
    if len(sys.argv) not in (2, 3) or not os.environ.get('BERGER_DIR'):
        raise ValueError('agent requis et BERGER_DIR explicite requis')
    temoin = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(32))
    texte = 'Message technique de recette locale. Réponds seulement reçu. temoin : ' + temoin
    r = subprocess.run([sys.executable, '-c', LANCEUR,
                        str(Path(__file__).resolve().parents[1] / 'bin/berger'), *sys.argv[1:]],
                       input=texte, text=True, capture_output=True, timeout=40)
    if r.returncode or temoin in r.stdout + r.stderr:
        raise ValueError('socket réelle non admise ; aucun contenu affiché')
    print('ok socket Herdr réelle et capture argv du noyau ; aucune valeur affichée')


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print('ÉCHEC sonde Herdr réelle ; aucun contenu affiché', file=sys.stderr)
        sys.exit(1)

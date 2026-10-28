#!/usr/bin/env python3
"""Capture MANUELLE du vrai Codex, propriétaire seulement, hors bac à sable.

Utilise le profil strict déjà généré de l'installation, sans régénération,
sans message et sans touche envoyée. Aucune sortie Herdr ni session existante.
La sortie neutralisée est exclusive, en 600, dans la copie de cette sonde.
"""
import argparse
import contextlib
import io
import os
from pathlib import Path
import re
import runpy
import shlex
import signal
import sys
import shutil
import subprocess
import tempfile
import time
import tomllib

COPIE = Path(__file__).resolve().parents[1]


def lancement_strict(installation, agent):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", agent): raise ValueError("agent invalide")
    os.environ['BERGER_DIR'] = str(installation)
    # Le produit fait foi pour le profil, les arguments et l'environnement.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        g = runpy.run_path(str(installation / 'bin/berger'), run_name='sonde')
        if not (g['dossier'](agent) / 'agent.conf').is_file() or g['ouvert'](agent):
            raise ValueError("agent strict requis")
        profil = g['CODEX_HOME'] / (agent + '.config.toml')
        texte = profil.read_text()
        p = tomllib.loads(texte)
        commun = tomllib.loads((g['CODEX_HOME'] / 'config.toml').read_text())
        if (not texte.startswith('# GÉNÉRÉ par berger regenerer')
                or p.get('default_permissions') != agent or p.get('approval_policy') != 'never'):
            raise ValueError("profil strict généré requis")
        for dossier in (g['dossier'](agent), g['travail'](agent)):
            if commun.get('projects', {}).get(str(dossier), {}).get('trust_level') != 'untrusted':
                raise ValueError("dossier non approuvé requis")
        g['exiger_bac_a_sable'](agent)
        g['exiger_tmp'](agent)
        commande = [shutil.which('codex') or 'codex', *g['moteurs'].args_moteur(agent, 'codex')]
        environnement = g['env_agent'](agent, g['env_codex'](agent))
        environnement.pop('TMUX', None)
        environnement.pop('TMUX_PANE', None)
        return commande, g['travail'](agent), environnement


def capturer_tmux(commande, dossier, environnement, attente=15,
                  executer=subprocess.run, pause=time.sleep):
    """Serveur tmux privé et jetable ; fermer aussi sur erreur/interruptions."""
    with tempfile.TemporaryDirectory(prefix='codex-confiance-', dir='/tmp') as t:
        base = ['tmux', '-f', '/dev/null', '-S', str(Path(t) / 'tmux.sock')]
        def appel(args, verifier=True):
            return executer([*base, *args], env=environnement, text=True,
                            capture_output=True, timeout=10, check=verifier)
        try:
            appel(['new-session', '-d', '-s', 'sonde', '-x', '120', '-y', '50',
                   '-c', str(dossier), 'exec ' + shlex.join(commande)])
            pause(attente)
            return appel(['capture-pane', '-p', '-t', 'sonde:0.0']).stdout
        finally:
            for args in (['kill-session', '-t', 'sonde'], ['kill-server']):
                try: appel(args, verifier=False)
                except (OSError, subprocess.SubprocessError): pass


def neutraliser(texte, chemins):
    # Ne pas archiver un éventuel écran d'authentification portant un code/jeton.
    if re.search(r'device code|auth\.openai\.com|access_token|refresh_token|Bearer |\bsk-', texte, re.I):
        raise ValueError("capture d'authentification refusée")
    for chemin in sorted({str(p) for p in chemins}, key=len, reverse=True):
        texte = texte.replace(chemin, '/dossier/agent-essai')
    return re.sub(r'(?<!\w)(?:~/|/)[^\s│<>"\']+', '/dossier/agent-essai', texte)


def ecrire_capture(sortie, texte, copie=COPIE):
    sortie = sortie.resolve()
    if not sortie.is_relative_to(copie.resolve()) or not texte.strip():
        raise ValueError("sortie non conforme")
    sortie.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(sortie, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(texte)
    return sortie


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--agent', required=True)
    parser.add_argument('--sortie', type=Path, default=COPIE / '.preuves/codex-confiance-0.163.0.txt')
    parser.add_argument('--attente', type=int, default=15, choices=range(1, 46), metavar='1..45')
    a = parser.parse_args()
    signaux = {n: signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGHUP)}
    def interrompre(*_): raise KeyboardInterrupt()
    for n in signaux: signal.signal(n, interrompre)
    try:
        installation = a.installation.resolve()
        commande, dossier, environnement = lancement_strict(installation, a.agent)
        brut = capturer_tmux(commande, dossier, environnement, a.attente)
        texte = neutraliser(brut, [Path.home(), installation, dossier, installation / 'agents' / a.agent])
        sortie = ecrire_capture(a.sortie, texte)
        print(f'{sortie} ({len(texte.splitlines())} lignes)')
        return 0
    except (Exception, SystemExit, KeyboardInterrupt):
        print('ÉCHEC : capture réelle impossible ; aucun écran inventé.', file=sys.stderr)
        return 1
    finally:
        for n, precedent in signaux.items(): signal.signal(n, precedent)


if __name__ == '__main__': raise SystemExit(main())
